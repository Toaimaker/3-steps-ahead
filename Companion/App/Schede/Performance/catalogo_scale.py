"""UpgradePlan01, passo 3b: il catalogo delle scale (Autore, 20 nov 2026: «da Player.log anche i dati di ogni categoria dovrebbero essere scomposti da
macro a micro per incastrarsi nelle situazioni di discesa automatica», poi «si»; il piano: Note/UpgradePlan01.md, passo 3b; la misura:
Note/UpgradePlan01_Passo3b.md).

La discesa del passo 3 (discesa.py) aveva 4 scale e 10 voci scritte a mano, col board letto a inizio turno e le carte lanciate contate su tutto il turno.
Qui ogni categoria dei dati del log e' una scala dal macro al micro, e ogni fase di ogni turno porta tutti i livelli di tutte le scale, letti NELLA
fase: il board all'inizio della fase (la foto di fine del turno prima per la prima fase principale, i confini di mana_aperto per il combattimento e la
seconda fase principale), le carte lanciate, l'attacco, le abilita', le occasioni che Arena offriva in quella fase.

  CONTESTO    evento > rango
  PARTITA     play o draw > mulligan > terre nella mano tenuta
  TEMPO       chi gioca > tratto > turno > fase
  BOARD       creature (Hero dietro, pari, avanti) > forza in campo > creature dell'Hero > carte in mano > cimitero > vite
  MANA        terre dell'Hero > sue terre stappate > terre stappate dell'Opponent
  AZIONI      il ruolo delle magie dell'Hero nella fase > l'attacco (nel suo combattimento) > abilita' attivate
  MAZZO       la meccanica lanciata > il tipo > la carta (nella fase)
  RIMOZIONI   l'Hero lancia una rimozione > l'Opponent lancia una rimozione (nella fase)
  AVVERSARIO  archetipo > colori > il ruolo delle sue magie nella fase
  OCCASIONI   cosa Arena offriva all'Hero nella fase > cosa ha fatto

Le voci di una fase che non si leggono (la foto manca, la fase «inizio» che e' il cambio di chi tocca e non ha azioni) sono None: la fase non entra
nelle celle di quella voce. Ogni voce ha 2-5 valori (fasce), perche' una cella vuole almeno discesa.MINIMO partite.

Le coppie: con ~30 voci le coppie di tutte con tutte sono ~450 e il test a permutazione costa troppo; servono le coppie per attraversare un livello che da
solo vale zero, cioe' il tempo (la chiave del solito). Quindi le coppie sono tempo x ogni altra voce, e le voci della stessa scala fra loro.

Uso: CATALOGO (lo passa discesa.scendi(cat=...)); unita(r, base) -> le fasi con le voci.
    py -I -X utf8 Companion/App/Schede/Performance/catalogo_scale.py --prova
"""
import os
import sys
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402
import ev_partita as EV  # noqa: E402

SCALE = {
    "contesto": ("evento", "rango"),
    "partita": ("partenza", "mulligan", "terre_mano"),
    "tempo": ("chi", "tratto", "turno", "fase"),
    "board": ("creature", "forza", "mie_creature", "mano", "cimitero", "vite"),
    "mana": ("terre", "aperte", "aperte_opp"),
    "azioni": ("ruolo", "attacco", "abilita"),
    "mazzo": ("meccanica", "tipo", "carta"),
    "rimozioni": ("rim_mia", "rim_sua"),
    "avversario": ("archetipo", "colori", "ruolo_opp"),
    "occasioni": ("offerta",),
}
ORDINE = ("contesto", "partita", "tempo", "board", "mana", "azioni", "mazzo", "rimozioni", "avversario", "occasioni")
NOMI = {"evento": "event", "rango": "rank", "partenza": "play or draw", "mulligan": "mulligans", "terre_mano": "lands kept in the opening hand",
        "chi": "whose turn", "tratto": "part of the game", "turno": "turn", "fase": "phase",
        "creature": "creatures at the start of the phase", "forza": "power on the battlefield", "mie_creature": "Hero's creatures",
        "mano": "cards in hand", "cimitero": "cards in the graveyard", "vite": "life",
        "terre": "Hero's lands", "aperte": "Hero's untapped lands", "aperte_opp": "Opponent's untapped lands",
        "ruolo": "what the Hero casts in the phase", "attacco": "Hero's attack", "abilita": "Hero's activated abilities",
        "meccanica": "mechanic cast", "tipo": "type cast", "carta": "card cast",
        "rim_mia": "Hero casts a removal", "rim_sua": "Opponent casts a removal",
        "archetipo": "opponent's deck", "colori": "opponent's colors", "ruolo_opp": "what the Opponent casts in the phase",
        "offerta": "what Arena offered the Hero"}
TIPI = {"C": "Creature", "I": "Instant", "S": "Sorcery", "E": "Enchantment", "A": "Artifact", "P": "Planeswalker", "B": "Battle"}
FASI = {"inizio": "the turn passing", "main1": "main phase 1", "comb": "combat", "main2": "main phase 2", "turn": "the whole turn"}
# le fasi di Arena dentro le fasi della spina (ev_partita._fasi): la prima fase principale prende anche stap, mantenimento e pescata, la seconda il passo finale
FASE_ARENA = {"Phase_Beginning": "main1", "Phase_Main1": "main1", "Phase_Combat": "comb", "Phase_Main2": "main2", "Phase_Ending": "main2"}


def coppie(voci):
    """I gruppi di due voci da provare insieme: tempo x ogni altra, e quelle della stessa scala."""
    scala = {v: s for s, vv in SCALE.items() for v in vv}
    out = []
    for k, a in enumerate(voci):
        for b in voci[k + 1:]:
            if scala[a] == "tempo" or scala[b] == "tempo" or scala[a] == scala[b]:
                out.append((a, b))
    return out


CATALOGO = dict(scale=SCALE, ordine=ORDINE, nomi=NOMI, coppie=coppie)


def _trio(d, soglia=0):
    return "behind" if d < -soglia else ("ahead" if d > soglia else "even")


def _fascia(v, soglie, nomi):
    for s, n in zip(soglie, nomi):
        if v <= s:
            return n
    return nomi[-1]


_TERRA = {}


def _e_terra(g):
    if g not in _TERRA:
        _TERRA[g] = bool(DA.e_terra(DA.nome_grp(g) or ""))
    return _TERRA[g]


def _lato(f, i):
    c = (f.get("c") or [[], []])[i] or []
    crea = [z for z in c if len(z) > 4 and z[3] is not None and not _e_terra(z[0])]
    terre = [z for z in c if _e_terra(z[0])]
    return dict(c=len(crea), f=sum(max(0, z[3] or 0) for z in crea), t=len(terre), s=sum(1 for z in terre if not z[1]),
                m=(f.get("n") or [None, None])[i], g=len((f.get("g") or [[], []])[i] or []), v=(f.get("v") or [None, None])[i],
                crea_id={z[5] for z in crea if len(z) > 5 and not z[1]})


_RUOLO = {}


def _ruolo(g):
    if g not in _RUOLO:
        try:
            _RUOLO[g] = DA.ruolo_magia(DA.nome_grp(g))
        except Exception:       # noqa: BLE001 - una carta che non si legge
            _RUOLO[g] = "Other spell"
    return _RUOLO[g]


def voci_board(f, a, b, chi_tocca_hero):
    """Le voci del board e del mana da una foto, dal lato dell'Hero (a) contro l'Opponent (b). Chi e' di turno all'inizio del suo turno ha appena
    stappato: lo dice chi chiama, con la foto di fine del turno prima (chi_tocca_hero True/False per stappare le sue terre, None se la foto e' gia' nella fase)."""
    A, B = _lato(f, a), _lato(f, b)
    if chi_tocca_hero is True:
        A["s"] = A["t"]
    elif chi_tocca_hero is False:
        B["s"] = B["t"]
    v_a = A["v"] if A["v"] is not None else 20
    v_b = B["v"] if B["v"] is not None else 20
    return dict(creature=_trio(A["c"] - B["c"]), forza=_trio(A["f"] - B["f"], 1), mie_creature=_fascia(A["c"], (0, 2), ("none", "1-2", "3+")),
                mano=_trio((A["m"] or 0) - (B["m"] or 0)) if A["m"] is not None and B["m"] is not None else None,
                cimitero=_trio(A["g"] - B["g"], 1), vite=_trio(v_a - v_b, 4),
                terre=_fascia(A["t"], (2, 4, 6), ("0-2", "3-4", "5-6", "7+")), aperte=_fascia(A["s"], (0, 1, 2), ("0", "1", "2", "3+")),
                aperte_opp=_fascia(B["s"], (0, 1, 2), ("0", "1", "2", "3+")))


def unita(r, base):
    """Le fasi dei turni delle partite r con lo scarto contro il solito del loro mazzo (dalle partite base), e le voci di tutte le scale, lette nella fase."""
    out = []
    per_partita = collections.defaultdict(list)
    for z in EV.turni_con_scarto(r, base):
        per_partita[z["partita"]].append(z)
    righe = {x["partita"]: x for x in r}
    for pid, turni in per_partita.items():
        x = righe.get(pid)
        if x is None:
            continue
        d = DA._MANA.get(pid) or {}
        seat = x.get("seat")
        a, b = (seat - 1, 2 - seat) if seat in (1, 2) else (0, 1)
        fine = {t: f for t, _a, f in d.get("foto") or []}
        confini = {(m[0], m[2]): m[3] for m in d.get("confini") or [] if len(m) > 3 and isinstance(m[3], dict)}
        # le magie per turno e fase della spina, di chi
        magie = collections.defaultdict(list)          # (t, fase, mio) -> [grp]
        for t, s_, g_, fa in d.get("fasi") or []:
            magie[(t, FASE_ARENA.get(fa, "main1"), s_ == seat)].append(g_)
        tipi_g = {}
        for az in d.get("azioni") or []:
            if len(az) >= 5 and az[2] == "magia":
                tipi_g[az[3]] = az[4] or ""
        abil = collections.Counter((t, FASE_ARENA.get(fa, "main1")) for t, s_, _g, fa, *_r in d.get("attivate") or [] if s_ == seat)
        offerte = collections.defaultdict(set)         # (t, fase) -> grp delle magie pagabili offerte all'Hero
        for t, s_, fa, lst, *_r in d.get("disponibili") or []:
            if s_ == seat:
                for g_, kind, pag in lst or []:
                    if kind == "C" and pag:
                        offerte[(t, FASE_ARENA.get(fa, "main1"))].add(g_)
        attacchi = {}
        for m in d.get("momenti") or []:
            if m[0] == "comb" and len(m) > 4 and m[4] and m[2] == seat:
                attacchi[m[1]] = len(m[4].get("att") or [])
        vs = DA.vs_di(x)
        partenza = x.get("partenza") or ("play" if x.get("inizia") else "draw")
        mull = x.get("mulligan") if x.get("mulligan") is not None else x.get("mull")
        terre_m = x.get("terre")
        base_v = dict(evento=x.get("evento") or None, rango=(str(x.get("rango") or "").split(" ")[0] or None),
                      partenza=str(partenza) if partenza is not None else None,
                      mulligan=None if mull is None else ("none" if not mull else "1+"),
                      terre_mano=None if terre_m is None else _fascia(terre_m, (2, 3, 4), ("0-2", "3", "4", "5+")),
                      archetipo=x.get("suo") or None, colori=DA.nome_vs(vs) if vs else None)
        for z in turni:
            t, mio = z["t"], z["mio"]
            tempo = dict(chi="Hero" if mio else "Opponent",
                         tratto="turns 1-3" if z["giro"] <= 3 else ("turns 4-6" if z["giro"] <= 6 else "turns 7+"),
                         turno=f"turn {z['giro']}" if z["giro"] <= 7 else "turn 8+")
            for ph in z.get("fasi") or []:
                fs = ph["f"]
                if fs in ("inizio", "main1", "turn"):
                    f, tocca = (fine.get(t - 1) if t > 1 else d.get("mano0")), mio
                else:
                    f, tocca = confini.get((t, "comb" if fs == "comb" else "m2")), None
                vv = dict(base_v, **tempo, fase=FASI.get(fs, fs))
                if f:
                    vv.update(voci_board(f, a, b, tocca))
                if fs == "inizio":      # il cambio di chi tocca: nessuna azione
                    out.append(dict(partita=pid, scarto=ph["scarto"], voci=vv))
                    continue
                fasi_a = ("main1", "comb", "main2") if fs == "turn" else (fs,)
                mie = [g_ for fa in fasi_a for g_ in magie.get((t, fa, True), [])]
                sue = [g_ for fa in fasi_a for g_ in magie.get((t, fa, False), [])]
                ruoli = {_ruolo(g_) for g_ in mie}
                ruoli_o = {_ruolo(g_) for g_ in sue}
                nomi = {DA.nome_intero(DA.nome_grp(g_) or "") for g_ in mie} - {""}
                mecc = set()
                for nn in nomi:
                    try:
                        mecc |= set(EV.tag_carta(nn)[0])
                    except Exception:       # noqa: BLE001
                        pass
                tipi = {TIPI[c] for g_ in mie for c in tipi_g.get(g_, "") if c in TIPI}
                vv.update(ruolo=ruoli or {"nothing"}, ruolo_opp=ruoli_o or {"nothing"},
                          rim_mia="yes" if "Removal" in ruoli else "no", rim_sua="yes" if "Removal" in ruoli_o else "no",
                          abilita="yes" if any(abil.get((t, fa)) for fa in fasi_a) else "no")
                if mio:
                    vv.update(meccanica=mecc or {"nothing cast"}, tipo=tipi or {"nothing cast"}, carta=nomi or {"nothing cast"})
                    off = set().union(*(offerte.get((t, fa), set()) for fa in fasi_a))
                    vv["offerta"] = "nothing castable" if not off else ("cast something" if mie else "held a castable spell")
                    if fs in ("comb", "turn"):
                        n_att = attacchi.get(t, 0)
                        pron = len(_lato(f, a)["crea_id"]) if f else None
                        vv["attacco"] = "no attack" if not n_att else ("all" if pron is not None and n_att >= pron else "some")
                out.append(dict(partita=pid, scarto=ph["scarto"], voci=vv))
    return out


def prova():
    casi = []
    f = dict(c=[[[1, 0, 0, 2, 2, 11, None], [2, 0, 0, None, None, 12, None], [2, 1, 0, None, None, 13, None]],
                [[3, 0, 0, 4, 4, 21, None]]], n=[4, 2], v=[18, 20], g=[[5, 6], []])
    global _TERRA
    _TERRA.update({1: False, 2: True, 3: False})
    v = voci_board(f, 0, 1, None)
    casi.append(("creature pari 1-1, forza dietro 2-4", v["creature"] == "even" and v["forza"] == "behind"))
    casi.append(("le terre stappate dell'Hero: 1 su 2", v["terre"] == "0-2" and v["aperte"] == "1"))
    casi.append(("mano avanti 4-2, cimitero avanti 2-0, vite pari entro 4", v["mano"] == "ahead" and v["cimitero"] == "ahead" and v["vite"] == "even"))
    v2 = voci_board(f, 0, 1, True)
    casi.append(("all'inizio del suo turno l'Hero ha stappato tutto", v2["aperte"] == "2"))
    v3 = voci_board(f, 1, 0, None)
    casi.append(("negativa: dal lato dell'Opponent la forza e' avanti, le creature pari", v3["forza"] == "ahead" and v3["creature"] == "even"))
    cp = coppie(["chi", "fase", "creature", "forza", "terre", "archetipo"])
    casi.append(("le coppie: il tempo con tutte, la stessa scala fra loro", ("chi", "archetipo") in cp and ("creature", "forza") in cp))
    casi.append(("negativa: niente coppie fra scale diverse senza il tempo", ("creature", "terre") not in cp and ("forza", "archetipo") not in cp))
    casi.append(("ogni voce ha il suo nome e la sua scala", all(v_ in NOMI for vv in SCALE.values() for v_ in vv) and set(SCALE) == set(ORDINE)))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    R = [x for x in DA.righe() if x["tipo"] == ("Limited" if "--limited" in sys.argv else "Constructed")]
    m = sys.argv[sys.argv.index("--mazzo") + 1] if "--mazzo" in sys.argv else collections.Counter(x.get("mio") for x in R).most_common(1)[0][0]
    G = [x for x in R if (x.get("mio") or "").strip() == m.strip()]
    U = unita(G, R)
    print(m, len(G), "partite,", len(U), "fasi")
    for s in ORDINE:
        for v_ in SCALE[s]:
            c = collections.Counter(val for u in U for val in ((u["voci"].get(v_),) if not isinstance(u["voci"].get(v_), set) else u["voci"][v_])
                                    if val is not None)
            print(f"  {s:10s} {v_:13s} {dict(c.most_common(6))}")
