"""Le voci di combattimento e di interazione della pagella (14 nov 2026, Autore: «lo strumento deve rispondere per obbligo a ogni domanda»; la pagella delle
371 domande di Note/Enciclopedia_Domande_Performance.md, capitoli 7-10, voci V1, V2, V3, V9, V10, V13, V18, V19, V24, V26, V30, V31). Tutte dai dati che
mana_aperto salva gia' (momenti di combattimento, magie con la fase, azioni, foto di fine turno), per te («io») e dove ha senso per l'avversario («lui»).

  primo_att_*   il tuo primo attacco della partita, nel tuo turno N (o Never);
  n_att_*       quanti attacchi nella partita;
  non_att_*     i turni con un attaccante pronto e nessun attacco (mana_aperto.finestre_non_att, tutte le finestre);
  tutto_n_*     gli attacchi con tutto (2+ creature potevano), parte_n_* quelli con una parte;
  att_pw_*      gli attacchi a un planeswalker o a una battaglia (il bersaglio non e' un giocatore);
  esposto_*     i tuoi fine turno «morto sul tavolo»: la sua forza, tolti i bloccanti che ti restano stappati (ognuno ferma la sua creatura piu' forte),
                arriva alle tue vite (grado C: non vede volare, minaccia, i suoi trucchi; il numero e' un massimo);
  trucco_comb_* le magie lanciate nel combattimento dell'altro (la fase Combat di Arena: un trucco, un flash, una rimozione in combattimento);
  pericolo_io   i suoi attacchi senza un tuo blocco dopo i quali sei finito a portata del suo letale (vite <= la sua forza in campo);
  rim_lanciate_* le rimozioni lanciate (le regole VERA di variabili_c sul testo), rim_prima_lui la sua prima rimozione;
  rim_quando_io in che turno lanci le rimozioni (solo nel tuo, solo nel suo, tutti e due);
  rim_fine_io   una rimozione rimasta in mano fino alla fine;
  lui_prima_crea l'avversario ha tolto la tua prima creatura (la sua magia o abilita' l'ha tolta dal campo).

campi(x) -> {chiave: valore} (ricordato per partita); conta(x, k) -> quante volte (per DA.episodi) o None.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401


class _DA:
    """L'analizzatore preso quando serve: dati_analizzatore importa questo modulo mentre si carica."""
    def __getattr__(self, k):
        import dati_analizzatore
        return getattr(dati_analizzatore, k)


DA = _DA()
CONTI = ("0", "1", "2+")
CONTI3 = ("0", "1", "2", "3+")
PRIMO = ("Turn 1-2", "Turn 3", "Turn 4", "Turn 5", "Turn 6-7", "Turn 8+", "Never")
NOMI, ORDINE = {}, {}
for _c, _tu, _lui in (("io", "You", "the opponent"), ("lui", "Opponent", "you")):
    NOMI[f"primo_att_{_c}"] = f"{_tu} · first attack of the game"
    NOMI[f"n_att_{_c}"] = f"{_tu} · attacks in the game"
    NOMI[f"non_att_{_c}"] = f"{_tu} · turns with an attacker ready and no attack"
    NOMI[f"tutto_n_{_c}"] = f"{_tu} · attacks with everything (2+ creatures could attack)"
    NOMI[f"parte_n_{_c}"] = f"{_tu} · attacks with some of the creatures that could attack"
    NOMI[f"att_pw_{_c}"] = f"{_tu} · attacks on a planeswalker or battle"
    NOMI[f"esposto_{_c}"] = f"{_tu} · turns ended dead on board (their power through your untapped blockers reaches your life)" if _c == "io" else \
        f"{_tu} · turns ended dead on board (your power through their untapped blockers reaches their life)"
    NOMI[f"trucco_comb_{_c}"] = f"{_tu} · spells cast during {_lui}'s combat" if _c == "io" else f"{_tu} · spells cast during your combat"
    NOMI[f"rim_lanciate_{_c}"] = f"{_tu} · removal spells cast"
    # dalla VERSIONE 18 di mana_aperto (14 nov 2026): scarti, magie contrastate, scry
    NOMI[f"scarti_{_c}"] = f"{_tu} · cards discarded"
    NOMI[f"contrastate_{_c}"] = f"{_tu} · spells countered" if _c == "lui" else "You · your spells countered"
    NOMI[f"scry_{_c}"] = f"{_tu} · scries in the game"
    NOMI[f"scry_giu_{_c}"] = f"{_tu} · cards sent to the bottom with scry"
    NOMI[f"surveil_{_c}"] = f"{_tu} · cards put into the graveyard with surveil"
    ORDINE.update({f"primo_att_{_c}": PRIMO, f"n_att_{_c}": ("0", "1-2", "3-5", "6+"), f"non_att_{_c}": CONTI3, f"tutto_n_{_c}": CONTI,
                   f"parte_n_{_c}": CONTI, f"att_pw_{_c}": CONTI, f"esposto_{_c}": CONTI, f"trucco_comb_{_c}": CONTI, f"rim_lanciate_{_c}": CONTI3,
                   f"scarti_{_c}": CONTI, f"contrastate_{_c}": CONTI, f"scry_{_c}": ("0", "1-2", "3+"), f"scry_giu_{_c}": ("0", "1-2", "3+"), f"surveil_{_c}": ("0", "1-2", "3+")})
NOMI.update(pericolo_io="You · their attacks you did not block that left you within their lethal", rim_prima_lui="Opponent · their first removal",
            rim_quando_io="You · when you cast your removal", rim_fine_io="You · removal still in your hand at the end",
            lui_prima_crea="Opponent · removed your first creature")
ORDINE.update(pericolo_io=CONTI, rim_prima_lui=("By their turn 3", "By their turn 5", "Later", "Never"),
              rim_quando_io=("Your turn only", "Their turn only", "Both", "None"), rim_fine_io=("Yes", "No"), lui_prima_crea=("Yes", "No"))
_MEMO = {}


def _fascia(n, valori):
    return valori[min(n, len(valori) - 1)] if valori in (CONTI, CONTI3) else None


def _passa(forze, b):
    """La forza che passa contro b bloccanti: ognuno ferma la creatura piu' forte."""
    return sum(sorted(forze, reverse=True)[b:])


def _crea(lato):
    return [c for c in lato or [] if len(c) > 5 and c[3] is not None]


def _conti(x):
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    mom = d.get("momenti")
    if not mom or seat not in (1, 2):
        return None
    firma = (x.get("partita"), len(mom))
    if firma in _MEMO:
        return _MEMO[firma]
    import mana_aperto as MA
    import variabili_c as VC
    chi = lambda s: "io" if s == seat else "lui"
    k = {f"{n}_{c}": 0 for n in ("n_att", "non_att", "tutto_n", "parte_n", "att_pw", "esposto", "trucco_comb", "rim_lanciate", "scarti", "contrastate",
                                 "scry", "scry_giu", "surveil") for c in ("io", "lui")}
    k["pericolo_io"] = 0
    primo = {"io": None, "lui": None}
    attivo = {}
    for m in mom:
        if m[0] in ("fine", "comb", "spell"):
            attivo.setdefault(m[1], m[2])
    for m in mom:
        if m[0] == "comb" and m[4] and m[4].get("att"):
            c, info = chi(m[2]), m[4]
            k[f"n_att_{c}"] += 1
            if primo[c] is None:
                primo[c] = (m[1] + 1) // 2
            pot = info.get("pot")
            if pot and pot >= 2:
                k[f"tutto_n_{c}" if len(info["att"]) >= pot else f"parte_n_{c}"] += 1
            if any(b_ not in (1, 2) for _i, b_ in info["att"]):
                k[f"att_pw_{c}"] += 1
            if c == "lui" and not info.get("blocchi"):      # V19: un suo attacco senza un tuo blocco
                dopo = next((m2[3] for m2 in mom if m2[0] == "fine" and m2[1] == m[1] and isinstance(m2[3], dict)), None)
                if dopo:
                    vita = (dopo.get("v") or [None, None])[seat - 1]
                    forza = sum(max(0, c_[3] or 0) for c_ in _crea((dopo.get("c") or [[], []])[2 - seat]))
                    if vita is not None and 0 < vita <= forza:
                        k["pericolo_io"] += 1
    for s in (1, 2):
        k[f"non_att_{chi(s)}"] = len(MA.finestre_non_att(d, s) or [])
    # «morto sul tavolo» a fine turno: la forza dell'altro (si stappa) tolti i tuoi bloccanti stappati, contro le tue vite
    for m in mom:
        if m[0] == "fine" and isinstance(m[3], dict):
            f, s = m[3], m[2]
            v = (f.get("v") or [None, None])[s - 1]
            mie = [c_ for c_ in _crea((f.get("c") or [[], []])[s - 1]) if not c_[1]]
            sue = [max(0, c_[3] or 0) for c_ in _crea((f.get("c") or [[], []])[2 - s])]
            if v is not None and v > 0 and sue and _passa(sue, len(mie)) >= v:
                k[f"esposto_{chi(s)}"] += 1
    for t, s_, g, fase in d.get("fasi") or []:
        if fase == "Phase_Combat" and attivo.get(t) not in (None, s_):
            k[f"trucco_comb_{chi(s_)}"] += 1
    rim_t = {"io": [], "lui": []}
    for t, s_, cosa, g, tp in d.get("azioni") or []:
        if cosa == "scarta":
            k[f"scarti_{chi(s_)}"] += 1
        elif cosa == "contrastata":
            k[f"contrastate_{chi(s_)}"] += 1
        elif cosa == "surveil":
            k[f"surveil_{chi(s_)}"] += 1
        elif cosa == "scry":
            k[f"scry_{chi(s_)}"] += 1
            k[f"scry_giu_{chi(s_)}"] += int(tp or 0)
        if cosa == "magia" and g not in DA.SENZA_FACCIA and VC.rimozione(DA.nome_grp(g) or ""):
            rim_t[chi(s_)].append(t)
            k[f"rim_lanciate_{chi(s_)}"] += 1
    out = {kk: _fascia(n, ORDINE[kk]) for kk, n in k.items()}
    for c in ("io", "lui"):
        for kk in (f"scry_{c}", f"scry_giu_{c}", f"surveil_{c}"):
            out[kk] = "0" if k[kk] == 0 else "1-2" if k[kk] <= 2 else "3+"
    for c in ("io", "lui"):
        n = k[f"n_att_{c}"]
        out[f"n_att_{c}"] = "0" if n == 0 else "1-2" if n <= 2 else "3-5" if n <= 5 else "6+"
    out["_conti"] = dict(k)
    for c in ("io", "lui"):
        n = primo[c]
        out[f"primo_att_{c}"] = ("Never" if n is None else "Turn 1-2" if n <= 2 else "Turn 6-7" if 6 <= n <= 7 else "Turn 8+" if n >= 8 else f"Turn {n}")
    sue_t = sorted((t + 1) // 2 for t in rim_t["lui"])
    out["rim_prima_lui"] = "Never" if not sue_t else "By their turn 3" if sue_t[0] <= 3 else "By their turn 5" if sue_t[0] <= 5 else "Later"
    mio_t = {attivo.get(t) == seat for t in rim_t["io"]}
    out["rim_quando_io"] = "None" if not mio_t else "Both" if len(mio_t) == 2 else "Your turn only" if True in mio_t else "Their turn only"
    ult = (d.get("ultima") or [None])[-1]
    if isinstance(ult, dict):
        mano = [DA.nome_grp(g) or "" for g in (ult.get("m") or [[], []])[seat - 1]]
        out["rim_fine_io"] = "Yes" if any(n_ and not DA.e_terra(n_) and VC.rimozione(n_) for n_ in mano) else "No"
    # la tua prima creatura: la prima che compare nelle foto di fine turno; tolta da una sua magia o abilita'?
    prima_id = None
    for m in mom:
        if m[0] == "fine" and isinstance(m[3], dict):
            cr = _crea((m[3].get("c") or [[], []])[seat - 1])
            if cr:
                prima_id = cr[0][5]
                break
    if prima_id is not None:
        tolta = any(m[0] == "spell" and m[4] and m[4].get("chi") not in (None, seat) and prima_id in ((m[4].get("colpiti") or []) + (m[4].get("fatti") or []))
                    for m in mom)
        out["lui_prima_crea"] = "Yes" if tolta else "No"
    _MEMO[firma] = out
    return out


def valore(x, k):
    c = _conti(x)
    return None if c is None else c.get(k)


def conta(x, k):
    """Quante volte, per le voci che contano episodi (DA.episodi); None per le altre."""
    c = _conti(x)
    return None if c is None else c["_conti"].get(k)


def prova():
    casi = []
    import mana_aperto as MA  # noqa: F401
    import dati_analizzatore as DAm
    vecchi = (DAm.nome_grp,)
    DAm.nome_grp = lambda g: {900: "Shock", 901: "Grizzly Bears"}.get(g)
    try:
        bear = lambda i, tap=0: [901, tap, 0, 2, 2, i]
        # turno 1 (tu, posto 1): Grizzly Bears; turno 2 (lui): Shock sulla tua prima creatura; turno 3: attacchi con 2 su 2; turno 4 lui attacca, non blocchi
        f1 = dict(c=[[bear(11)], []], m=[[], []], v=[20, 20])
        f2 = dict(c=[[], [bear(21), bear(22)]], m=[[], []], v=[20, 20])
        f3 = dict(c=[[bear(12), bear(13)], [bear(21), bear(22)]], m=[[900], []], v=[20, 20])
        f4 = dict(c=[[bear(12), bear(13)], [bear(21, 1), bear(22, 1)]], m=[[900], []], v=[3, 20])
        mom = [["fine", 1, 1, f1, None], ["spell", 2, 2, f1, dict(g=900, chi=2, ab=False, bers=[11], colpiti=[11])], ["fine", 2, 2, f2, None],
               ["comb", 3, 1, f3, dict(att=[[12, 2], [13, 2]], blocchi=[[21, [12]]], pot=2, aperte=0)], ["fine", 3, 1, f3, None],
               ["comb", 4, 2, f4, dict(att=[[21, 1], [22, 1]], blocchi=[], pot=2, aperte=2)], ["fine", 4, 2, f4, None]]
        DAm._MANA["vp1"] = dict(momenti=mom, fasi=[[2, 2, 900, "Phase_Combat"]], azioni=[[1, 1, "magia", 901, "C"], [2, 2, "magia", 900, "I"]],
                                foto=[[1, 1, f1], [2, 2, f2], [3, 1, f3], [4, 2, f4]], fine=[[1, 1, 0, 0], [2, 2, 0, 0], [3, 1, 0, 0], [4, 2, 0, 0]],
                                attacchi=[], ultima=[f4])
        x = dict(partita="vp1", seat=1)
        c = _conti(x)
        casi.append(("il primo attacco al tuo turno 2 (Arena 3), uno con tutto, nessuno a metà", c["primo_att_io"] == "Turn 1-2" and c["tutto_n_io"] == "1"
                     and c["parte_n_io"] == "0" and c["n_att_io"] == "1-2"))
        casi.append(("lui: il suo primo attacco, con tutto; nessun attacco a un planeswalker", c["primo_att_lui"] == "Turn 1-2" and c["tutto_n_lui"] == "1"
                     and c["att_pw_lui"] == "0"))
        casi.append(("Shock nella fase di combattimento del turno 2 (il suo turno): non e' un trucco nel tuo combattimento", c["trucco_comb_lui"] == "0"))
        casi.append(("la sua rimozione: una, al suo turno 1; ha tolto la tua prima creatura", c["rim_lanciate_lui"] == "1" and c["rim_prima_lui"] == "By their turn 3"
                     and c["lui_prima_crea"] == "Yes"))
        casi.append(("il suo attacco senza blocco ti lascia a 3 vite contro 4 di forza: a portata del suo letale", c["pericolo_io"] == "1"))
        casi.append(("Shock in mano alla fine: una rimozione rimasta in mano", c["rim_fine_io"] == "Yes"))
        casi.append(("negativa: le tue rimozioni lanciate sono 0, quindi «None»", c["rim_lanciate_io"] == "0" and c["rim_quando_io"] == "None"))
        casi.append(("a fine del suo turno 4 sei a 3 vite, lui ha 4 di forza e tu due bloccanti stappati: passa 0, non sei morto sul tavolo", c["esposto_io"] == "0"))
        casi.append(("conta: gli attacchi con tutto sono 1", conta(x, "tutto_n_io") == 1 and conta(x, "esposto_io") == 0))
    finally:
        DAm.nome_grp = vecchi[0]
        DAm._MANA.pop("vp1", None)
        _MEMO.clear()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
