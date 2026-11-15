"""I leak dei giocatori di 17Lands (15 nov 2026, Autore: «aggiungi il confronto», dopo «How you compare with other players needs the shared data»).

I replay pubblici di 17Lands (17lands.com/public_datasets, licenza CC BY 4.0, la citazione sta nella cartella Leaks e in Help) hanno, per ogni partita
del Premier Draft e per ogni turno dei due giocatori: le terre giocate, la mano di chi usa 17Lands a fine turno (gli id di Arena), le terre in campo, il mana
speso (anche nel turno dell'altro), le abilita' attivate, i combattimenti (chi attacca, chi blocca, chi muore), le vite; e le mani dei mulligan. Su quei
dati si misurano 7 dei 15 leak di leak.py, con la stessa regola o con una regola vicina (scritto per ognuno in REGOLE); gli altri vogliono le terre tappate
o la fase della magia, che 17Lands non scrive. Il Constructed non ha replay pubblici: il confronto li' aspetta i dati condivisi.

calcola() legge i replay sul disco (Dati/17lands/replay_<SET>/, fuori da git) e scrive Regole/leak_17lands.json: per ogni leak la quota delle partite in cui
succede, il win rate con e senza, per tutti e per i giocatori di rango Mythic. carica() lo legge (l'app, anche la pubblica: il file entra nel pacchetto).

    py -I -X utf8 Companion/App/Schede/Performance/leak_17lands.py              # rifa' il file (qualche minuto)
    py -I -X utf8 Companion/App/Schede/Performance/leak_17lands.py --prova      # i casi a mano, con le negative
"""
import os
import sys

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")) and os.path.dirname(_casa) != _casa:
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import json  # noqa: E402

RADICE = percorsi.ROOT
FILE = os.path.join(RADICE, "Regole", "leak_17lands.json")
SET = ("ECL", "HOB", "MSH", "SOS", "TLA", "TMT")
PER_SET = 25000          # partite lette per set: 150.000 in tutto
TURNI = 20
# quanto la regola su 17Lands e' la stessa della nostra: «same» stessa regola, «close» vicina (e perche')
REGOLE = {"l1": ("same", ""),
          "l2": ("close", "their data has no tapped lands: untapped = lands in play minus mana spent; colors counted on all your lands"),
          "l4": ("close", "the attack's power is the printed power of the attackers"),
          "l5": ("same", ""),
          "l12": ("same", ""), "l13": ("same", ""),
          "l15": ("close", "the lands open on their turn are your lands minus the mana you spent on your turn before (their data has no tapped lands)")}
FONTE = ("17Lands public replay data (CC BY 4.0, 17lands.com/public_datasets), Premier Draft of " + ", ".join(SET))


def carica():
    """Il file dei leak di 17Lands, o None se non c'e'."""
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ le carte, dagli id di Arena
_INFO = {}


def info(g):
    """(nome, terra, tipo, testo, cmc, costo in simboli, colori prodotti se terra) di un id di Arena; None se non si conosce. Una volta per id."""
    if g in _INFO:
        return _INFO[g]
    import dati_analizzatore as DA
    import leak as LK
    try:
        n = DA.nome_grp(int(g))
    except (TypeError, ValueError):
        n = None
    out = None
    if n:
        c = LK._carta(n)
        terra = DA.e_terra(n)
        out = dict(n=n, terra=terra, tipo=c.get("tipo") or "", testo=c.get("testo") or "", cmc=c.get("cmc") or 0, costo=LK._costo(n) or [],
                   colori=LK._colori_terra(int(g)) if terra else set())
    _INFO[g] = out
    return out


def _ids(v):
    return [x for x in (v or "").split("|") if x]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _paga(costo, terre_colori, n_aperte):
    """La carta col suo costo si paga con n_aperte terre, i simboli colorati contati su tutte le terre (regola vicina: non si sa quali sono tappate)."""
    if len(costo) > n_aperte:
        return False
    for sym in set(s for s in costo if s != "1" and s != "C"):
        alternative = set(sym.split("/"))
        if sum(1 for col in terre_colori if col & alternative) < sum(1 for s in costo if s == sym):
            return False
    return True


# ------------------------------------------------------------------ i leak di una partita di 17Lands
def leak_partita(d):
    """d: la riga del replay (colonna -> valore). -> {l1, l2, l4, l5, l12, l13, l15: bool}, o None se la partita non si legge."""
    import leak as LK
    on_play = d.get("on_play") == "True"
    out = {k: False for k in REGOLE}
    # i mulligan: la tabella del Limited (dati_analizzatore.mull_tabella)
    try:
        mull = int(float(d.get("num_mulligans") or 0))
    except ValueError:
        return None
    prima = [info(g) for g in _ids(d.get("candidate_hand_1"))]
    if len(prima) != 7 or any(c is None for c in prima):
        return None
    terre7 = sum(1 for c in prima if c["terra"])
    if mull == 0:
        out["l12"] = not (1 <= terre7 <= 5)
    else:
        out["l13"] = 2 <= terre7 <= 5
    vita_prima = 20.0
    for n in range(1, TURNI + 1):
        u, o = f"user_turn_{n}_", f"oppo_turn_{n}_"
        # il turno dell'avversario dopo il tuo turno n: lo stesso numero se sei on the play, il dopo se sei on the draw
        dopo = f"oppo_turn_{n if on_play else n + 1}_"
        # e quello prima del tuo turno n (per la vita prima del suo attacco): on the draw il suo turno n viene prima del tuo
        if _num(d.get(u + "eot_user_life")) is not None:
            mano = [info(g) for g in _ids(d.get(u + "eot_user_cards_in_hand"))]
            terre_campo = [info(g) for g in _ids(d.get(u + "eot_user_lands_in_play"))]
            if not _ids(d.get(u + "lands_played")) and any(c and c["terra"] for c in mano):
                out["l1"] = True
            colori = [c["colori"] for c in terre_campo if c]
            spesa = _num(d.get(u + "user_mana_spent")) or 0
            aperte = max(0, len(terre_campo) - int(spesa))
            spesa_dopo = _num(d.get(dopo + "user_mana_spent")) or 0
            abil_dopo = bool(_ids(d.get(dopo + "user_abilities")))
            tenuti = [c for c in mano if c and not c["terra"] and c["costo"] and ("Instant" in c["tipo"] or "Flash" in c["testo"])
                      and _paga(c["costo"], colori, aperte)]
            creature = [c for c in mano if c and "Creature" in c["tipo"] and "Flash" not in c["testo"] and c["costo"]]
            if not abil_dopo and not (spesa_dopo == 0 and tenuti):
                if any(_paga(c["costo"], colori, aperte - int(spesa_dopo)) for c in creature):
                    out["l2"] = True
            vita_prima = _num(d.get(u + "eot_user_life")) or vita_prima
        for pre in (u, o):
            persi_miei = [info(g) for g in _ids(d.get(pre + "user_creatures_killed_combat"))]
            persi_suoi = [info(g) for g in _ids(d.get(pre + "oppo_creatures_killed_combat"))]
            if persi_miei and persi_suoi:
                if sum(c["cmc"] for c in persi_miei if c) >= sum(c["cmc"] for c in persi_suoi if c) + 2:
                    out["l5"] = True
        # il suo turno n: chump block a vita alta (prima del suo turno la vita a fine del tuo turno prima, o 20)
        if _num(d.get(o + "eot_user_life")) is not None:
            vita = vita_prima if on_play else (_num(d.get(f"user_turn_{n - 1}_eot_user_life")) if n > 1 else 20.0)
            bloccanti = set(_ids(d.get(o + "creatures_blocking")))
            morti = set(_ids(d.get(o + "user_creatures_killed_combat")))
            att = [info(g) for g in _ids(d.get(o + "creatures_attacked"))]
            forza = 0
            for c in att:
                try:
                    forza += int(str(LK._carta(c["n"]).get("forza") or 0)) if c else 0
                except ValueError:
                    pass
            if (bloccanti & morti and not _ids(d.get(o + "oppo_creatures_killed_combat")) and vita is not None and vita >= LK.VITA_ALTA
                    and forza < vita):
                out["l4"] = True
            # L15: a fine del suo turno, niente speso da te e in mano un istantaneo da fine turno o un flash che le tue terre pagavano
            if not _num(d.get(o + "user_mana_spent")) and not _ids(d.get(o + "user_instants_sorceries_cast")):
                terre_o = [info(g) for g in _ids(d.get(o + "eot_user_lands_in_play"))]
                col_o = [c["colori"] for c in terre_o if c]
                # le terre tappate nel tuo turno restano tappate nel suo: aperte = terre meno il mana speso nel tuo turno prima (on the play il tuo turno n,
                # on the draw il n-1)
                prima_t = f"user_turn_{n if on_play else n - 1}_"
                aperte_o = max(0, len(terre_o) - int(_num(d.get(prima_t + "user_mana_spent")) or 0))
                for c in (info(g) for g in _ids(d.get(o + "eot_user_cards_in_hand"))):
                    if not c or not c["cmc"] or c["cmc"] > aperte_o:
                        continue
                    flash = "Creature" in c["tipo"] and "Flash" in c["testo"]
                    fine = "Instant" in c["tipo"] and "counter target" not in c["testo"].lower() and (LK._guarda(c["n"]) or _rimozione(c["n"]))
                    if (flash or fine) and _paga(c["costo"], col_o, aperte_o):
                        out["l15"] = True
                        break
    return out


def _rimozione(n):
    import variabili_c as VC
    try:
        return bool(VC.rimozione(n))
    except Exception:      # noqa: BLE001
        return False


# ------------------------------------------------------------------ il conto
def calcola(per_set=PER_SET, stampa=print):
    import csv
    import datetime
    import gzip
    conti = {"tutti": {}, "mythic": {}}
    partite = {"tutti": 0, "mythic": 0}
    vinte = {"tutti": 0, "mythic": 0}
    letti = []
    for s in SET:
        p = os.path.join(RADICE, "Dati", "17lands", f"replay_{s}", f"replay_data_public.{s}.PremierDraft.csv.gz")
        if not os.path.isfile(p):
            stampa(f"  {s}: replay non trovato, salto")
            continue
        csv.field_size_limit(10 ** 7)
        with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            h = next(r)
            serve = [i for i, c in enumerate(h) if not c.startswith("deck_") and not c.startswith("sideboard_")]
            nomi = [h[i] for i in serve]
            fatte = 0
            for riga in r:
                d = {nomi[j]: riga[i] for j, i in enumerate(serve) if i < len(riga) and riga[i] != ""}
                lk = leak_partita(d)
                if lk is None:
                    continue
                vinta = d.get("won") == "True"
                gruppi = ["tutti"] + (["mythic"] if (d.get("rank") or "").lower() == "mythic" else [])
                for g in gruppi:
                    partite[g] += 1
                    vinte[g] += vinta
                    for k, v in lk.items():
                        c = conti[g].setdefault(k, [0, 0, 0, 0])      # partite col leak, vinte col leak, senza, vinte senza
                        if v:
                            c[0] += 1
                            c[1] += vinta
                        else:
                            c[2] += 1
                            c[3] += vinta
                fatte += 1
                if fatte >= per_set:
                    break
        letti.append(s)
        stampa(f"  {s}: {fatte:,} partite")
    out = dict(fonte=FONTE, data=datetime.date.today().isoformat(), set=letti, regole={k: list(v) for k, v in REGOLE.items()}, gruppi={})
    for g in conti:
        n = partite[g]
        if not n:
            continue
        out["gruppi"][g] = dict(partite=n, wr=round(100 * vinte[g] / n, 1),
                                leak={k: dict(tasso=round(100 * c[0] / n, 1), con=c[0], wr_con=round(100 * c[1] / c[0], 1) if c[0] else None,
                                              wr_senza=round(100 * c[3] / c[2], 1) if c[2] else None) for k, c in conti[g].items()})
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FILE)
    return out


# ------------------------------------------------------------------ le prove
def prova():
    import dati_analizzatore as DA
    casi = []
    DA._NOMI_GRP.update({811: "Plains", 814: "Healer's Hawk", 816: "Serra Angel", 818: "Raise the Alarm"})
    mano7 = "811|811|811|814|814|816|816"
    base = {"on_play": "True", "num_mulligans": "0", "candidate_hand_1": mano7, "won": "True"}
    t1 = dict(base, **{"user_turn_1_eot_user_life": "20", "user_turn_1_lands_played": "811", "user_turn_1_eot_user_cards_in_hand": "811|814",
                       "user_turn_1_eot_user_lands_in_play": "811", "user_turn_1_user_mana_spent": "1"})
    lk = leak_partita(t1)
    casi.append(("negativa: terra giocata, mana speso, niente leak", lk is not None and not any(lk.values())))
    lk = leak_partita(dict(t1, **{"user_turn_1_lands_played": ""}))
    casi.append(("L1: nessuna terra giocata con una Plains in mano", lk["l1"]))
    lk = leak_partita(dict(t1, **{"user_turn_1_user_mana_spent": "0"}))
    casi.append(("L2: una Plains aperta e Healer's Hawk in mano", lk["l2"]))
    lk = leak_partita(dict(t1, **{"user_turn_1_user_mana_spent": "0", "user_turn_1_eot_user_cards_in_hand": "811|814|818",
                                 "user_turn_1_eot_user_lands_in_play": "811|811"}))
    casi.append(("negativa L2: con Raise the Alarm pagabile in mano il mana era tenuto apposta", not lk["l2"]))
    lk = leak_partita(dict(t1, **{"user_turn_1_user_mana_spent": "0", "user_turn_1_eot_user_cards_in_hand": "811|814|818",
                                 "user_turn_1_eot_user_lands_in_play": "811|811", "oppo_turn_1_user_mana_spent": "2"}))
    casi.append(("negativa L2: il mana speso nel suo turno (2) toglie le due Plains", not lk["l2"]))
    lk = leak_partita(dict(base, num_mulligans="1", candidate_hand_1=mano7))
    casi.append(("L13: rimandata una 7 con 3 terre", lk["l13"] and not lk["l12"]))
    lk = leak_partita(dict(base, candidate_hand_1="814|814|816|816|814|814|816"))
    casi.append(("L12: tenuta una 7 senza terre; negativa: una mano illeggibile non conta", lk["l12"] and leak_partita(dict(base, candidate_hand_1="1|2")) is None))
    lk = leak_partita(dict(t1, **{"user_turn_2_eot_user_life": "20", "user_turn_2_user_creatures_killed_combat": "816",
                                 "user_turn_2_oppo_creatures_killed_combat": "814"}))
    casi.append(("L5: Serra Angel (5) per Healer's Hawk (1); negativa: senza i morti suoi non e' uno scambio", lk["l5"]
                 and not leak_partita(dict(t1, **{"user_turn_2_eot_user_life": "20", "user_turn_2_user_creatures_killed_combat": "816"}))["l5"]))
    # L15: due Island, Opt (scry) in mano a fine del suo turno 1 (on the play, dopo il tuo turno 1) e niente speso nel suo turno
    DA._NOMI_GRP.update({819: "Island", 815: "Opt"})
    t15 = dict(t1, **{"user_turn_1_eot_user_lands_in_play": "819|819", "user_turn_1_user_mana_spent": "0", "user_turn_1_eot_user_cards_in_hand": "815",
                      "oppo_turn_1_eot_user_life": "20", "oppo_turn_1_eot_user_lands_in_play": "819|819", "oppo_turn_1_eot_user_cards_in_hand": "815",
                      "oppo_turn_1_user_mana_spent": "0"})
    casi.append(("L15: mana aperto nel suo turno e Opt mai lanciato; negativa: col mana speso nel tuo turno prima le Island erano tappate",
                 leak_partita(t15)["l15"] and not leak_partita(dict(t15, user_turn_1_user_mana_spent="2"))["l15"]))
    for nome, ok in casi:
        print(("ok    " if ok else "ROSSO ") + nome)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    o = calcola()
    for g, v in o["gruppi"].items():
        print(g, v["partite"], {k: x["tasso"] for k, x in v["leak"].items()})
