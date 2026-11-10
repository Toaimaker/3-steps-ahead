"""La verifica dei piani del Farmer (Autore, 9 nov 2026: «i piani, controllali e verificali tutti / controlla che tutti i piani estraggano il massimo valore reale dal gold/gemme.
che siano iper affidabili»).

Per ogni goal, mix, spunta delle buste, modo del cambio e win rate, il piano di risorse.Risorse.piano si mette contro un ottimizzatore a forza bruta scritto a parte: prova OGNI combinazione
di Quick, Premier (prima coi token), eventi constructed, buste in oro (solo con la spunta) e ingressi pagati in gemme (una via, fino a MAX_EVENTI), con gli stessi valori di ogni evento
(Risorse.rese: premi medi al tuo win rate, buste, carte, jolly) e gli stessi vincoli: l'oro del mese, le gemme mai sotto zero, i token che hai, i posti del calendario, il ROI non negativo.
Il metro e' lo stesso del piano (quota di ogni obiettivo, guadagno sul non fare niente nel mix): se la forza bruta trova di meglio, il piano non estrae il massimo.

Controlli su ogni piano:
- obiettivo: il piano arriva al migliore della forza bruta, o resta dentro il 3% voluto (a parita' di risultato entro il 3% il piano sceglie chi guadagna di piu' tolta la varianza:
  «spesa vs varianza vs % win rate», 6 nov 2026). Sotto il 3% e' ROSSO.
- la roadmap esegue tutto il piano (niente fuori: cassa di ogni giorno e calendario);
- oro speso <= oro del mese, gemme mai sotto zero (i Premier oltre i token si pagano in oro: simula li chiama «token mancati», non e' un errore);
- ROI non negativo; nessuna gemma in buste; buste in oro solo con la spunta;
- il conto del piano e' quello della finestra: simula sulle voci del piano da' le stesse gemme a fine mese.

    py -I -X utf8 Companion/App/Schede/Resources/verifica_piani.py            tutti i casi, una riga per caso, esce 1 su un rosso
    py -I -X utf8 Companion/App/Schede/Resources/verifica_piani.py --prova    la prova negativa: un piano peggiorato apposta deve essere rosso
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import itertools
import time

import risorse as RS  # noqa: E402

TOLL = 0.03            # la fascia voluta del piano: entro il 3% del migliore sceglie il guadagno piu' sicuro
GOAL = [("gemme", {"gemme": 1.0}), ("valore", {"valore": 1.0}), ("jolly", {"jolly": 1.0}), ("carte TRK", {"carte": 1.0}), ("carte FRA", {"carte": 1.0}),
        ("gemme 50 + carte TRK 50", {"gemme": 0.5, "carte": 0.5}), ("gemme 70 + carte TRK 30", {"gemme": 0.7, "carte": 0.3}),
        ("jolly 50 + carte TRK 50", {"jolly": 0.5, "carte": 0.5}), ("gemme 50 + jolly 50", {"gemme": 0.5, "jolly": 0.5}),
        ("gemme 34 + jolly 33 + carte TRK 33", {"gemme": 0.34, "jolly": 0.33, "carte": 0.33})]


def set_del(nome):
    return "FRA" if "FRA" in nome else "TRK"


def forza_bruta(R, pesi, win, win_c, set_, oro_buste, pi):
    """Il miglior piano per forza bruta, con lo stesso metro del piano. -> dict(punti, n, via, g, tp, pass, bil) del migliore e la lista ordinata dei candidati (per la roadmap)."""
    rese, v = R.rese(win, win_c), R.valori()
    oggi, cal = RS.datetime.date.today(), RS._calendario()
    ap = dict(pi["aperti"])
    posti = {}
    for k in ("quick", "premier"):
        set_goal = set_ if "carte" in pesi else None
        posti[k] = RS.capienza(k, oggi, cal, set_goal)
        if not posti[k] and set_goal and len(pesi) > 1:
            posti[k] = RS.capienza(k, oggi, cal)
        if not ap.get(k):
            posti[k] = 0
    nuovo = RS.set_costruiti()
    set_di = {"buste": set_, "quick": ap.get("quick"), "premier": ap.get("premier"), "costruiti": nuovo}
    sa, b0, sp0 = R.saldo(), R.base(False), R.scatto_pass()
    mese = (RS.GIORNI_ROADMAP - 1) * 12 / 365.25
    esce = sp0["costo"] and any(s_.get("premier") and s_.get("inizio") and 0 <= (RS.datetime.date.fromisoformat(s_["inizio"]) - oggi).days < RS.GIORNI_ROADMAP for s_ in cal.values())
    tok = sa.get("token", 0)
    g_v = R.cambio_oro(win, win_c)["gpo"] if R.via_cambio == "busta" else R.gpo
    cq, cp, cc, cb = (rese[k]["oro"] for k in ("quick", "premier", "costruiti", "buste"))
    solo_gemme, solo_carte = list(pesi) == ["gemme"], list(pesi) == ["carte"]
    costr_set = nuovo == set_
    tutti = []
    for con_pass in ([True, False] if esce else [False]):
        oro_m = sa["oro"] + b0["oro"] * mese + (sp0["oro"] if con_pass else 0)
        gem_in = sa["gem"] + b0["gemme"] * mese + (sp0["gem"] - sp0["costo"] if con_pass else 0)
        q_ = RS.PASS_ANNO / 12 if con_pass else 0.0
        c_pass, v_pass = sp0["costo"] * q_, (sp0["gem"] + sp0["oro"] * g_v + sp0["bu"] * v["busta"]) * q_
        vie = [None] + [k for k in ("quick", "premier", "costruiti") if (k == "costruiti" and (not solo_carte or costr_set)) or (k != "costruiti" and ap.get(k))]
        for q in range(min(int(oro_m // cq), posti["quick"]) + 1):
            for p in range(min(int(oro_m // cp) + tok, posti["premier"]) + 1):
                tp = min(p, tok)
                oro = q * cq + (p - tp) * cp
                if oro > oro_m:
                    break
                for c in range(1 if solo_carte and not costr_set else int((oro_m - oro) // cc) + 1):
                    if solo_carte and not costr_set and c:
                        break
                    oro_c = oro + c * cc
                    for b in range(0, (int((oro_m - oro_c) // cb) if oro_buste and not solo_gemme else 0) + 1):
                        oro_b = oro_c + b * cb
                        n = dict(quick=q, premier=p, costruiti=c, buste=b)
                        premi = sum(n[k] * rese[k]["gemme"] for k in n)
                        for via in vie:
                            g_max = 0
                            if via:
                                ent, gain = rese[via]["gemme_in"], rese[via]["gemme"]
                                cap = RS.MAX_EVENTI if via == "costruiti" else min(RS.MAX_EVENTI, max(0, posti[via] - n[via]))
                                # ogni ingresso si paga prima del suo premio: per il (k+1)-esimo servono ent gemme in cassa dopo k ingressi (cassa - k * (ent - gain) >= ent)
                                disp = gem_in + premi
                                g_max = 0 if disp < ent else min(cap, (int((disp - ent) // (ent - gain)) + 1) if gain < ent else cap)
                            for g in range(0 if via else 0, g_max + 1):
                                if via and not g:
                                    continue
                                gem_fine = gem_in + premi + (g * (rese[via]["gemme"] - rese[via]["gemme_in"]) if via else 0)
                                if gem_fine < -1e-6:
                                    continue
                                t = {k: sum(n[x] * rese[x][k] for x in n) + (g * rese[via][k] if via else 0) for k in ("buste", "carte", "jolly_r", "jolly_m", "valore")}
                                carte = sum(n[k] * rese[k]["carte"] for k in n if set_di[k] == set_) + (g * rese[via]["carte"] if via and set_di[via] == set_ else 0)
                                resto = oro_m - oro_b
                                valore = t["valore"] + gem_in - (g * rese[via]["gemme_in"] if via else 0) + resto * R.gpo
                                mete = dict(gemme=gem_fine, carte=carte, jolly=RS.VALORE_JOLLY["R"] * t["jolly_r"] + RS.VALORE_JOLLY["M"] * t["jolly_m"], valore=valore, buste=t["buste"])
                                sp = c_pass + tp * min(rese["premier"]["gemme_in"], rese["premier"]["valore"]) + (p - tp) * cp * g_v + q * cq * g_v + c * cc * g_v + b * cb * g_v + (g * rese[via]["gemme_in"] if via else 0)
                                ott = v_pass + sum(n[k] * rese[k]["valore"] for k in n) + (g * rese[via]["valore"] if via else 0)
                                tutti.append(dict(mete=mete, n=n, via=via, g=g, tp=tp, con_pass=con_pass, sp=sp, ott=ott, oro=oro_b, oro_m=oro_m, gem_in=gem_in, premi=premi))
    sani = [x for x in tutti if x["ott"] - x["sp"] >= -1e-6] or tutti
    if len(pesi) > 1:
        b0_ = R.base(False)
        g0, o0 = sa["gem"] + b0_["gemme"] * mese, sa["oro"] + b0_["oro"] * mese
        zero = dict(jolly=0.0, buste=0.0, carte=0.0, gemme=g0, valore=g0 + o0 * R.gpo)

        def guad(x, g):
            bu_p = R.base(x["con_pass"])["buste"] - b0_["buste"]
            extra = dict(jolly=bu_p * (RS.VALORE_JOLLY["R"] * v["jolly_r"] + RS.VALORE_JOLLY["M"] * v["jolly_m"]), buste=bu_p, valore=bu_p * v["busta"], gemme=0.0, carte=0.0)
            return x["mete"][g] + extra[g] - zero[g]
    else:
        # col goal solo, il pass conta anche le buste che mette nella base, come risorse._scegli_pass (jolly e buste)
        def guad(x, g):
            bb = R.base(x["con_pass"])["buste"]
            return x["mete"][g] + {"jolly": bb * (RS.VALORE_JOLLY["R"] * v["jolly_r"] + RS.VALORE_JOLLY["M"] * v["jolly_m"]), "buste": bb}.get(g, 0.0)
    top = {g: max(guad(x, g) for x in sani) for g in pesi}
    for x in sani:
        x["punti"] = min((guad(x, g) / top[g] if top[g] > 0 else 1.0) / pesi[g] for g in pesi)
    sani.sort(key=lambda x: -x["punti"])
    return sani, top, guad


def eseguibile(R, x, win, win_c, solo):
    pg = dict(quick="oro", premier="token" if x["tp"] else "oro", costruiti="oro", buste="oro", mitiche="oro")
    e = R.simula(x["n"]["quick"], x["n"]["premier"], x["n"]["buste"], 0, pg, win, x["oro_m"], costruiti=x["n"]["costruiti"], win_c=win_c, gemme_mese=x["gem_in"],
                 gemme_voci={x["via"]: x["g"]} if x["via"] else None, con_pass=x["con_pass"])
    return not R.roadmap(e, win=win, win_c=win_c, solo_set=solo)["fuori"], e


def controlla(R, nome, pesi, win, win_c, oro_buste, pi=None):
    """-> (rosso, riga)."""
    set_ = set_del(nome)
    pi = pi or R.piano(pesi, win, set_, win_c=win_c, oro_buste=oro_buste)
    if pi is None:
        return True, f"ROSSO {nome}: nessun piano"
    vo, gv = pi["voci"], pi["gemme_voci"]
    via, g = (next(iter(gv.items())) if gv else (None, 0))
    sani, top, guad = forza_bruta(R, pesi, win, win_c, set_, oro_buste, pi)
    # il piano col metro della forza bruta
    mio = next((x for x in sani if x["n"] == dict(quick=vo["quick"], premier=vo["premier"], costruiti=vo["costruiti"], buste=vo["buste"]) and x["via"] == via and x["g"] == g
                and x["con_pass"] == bool(pi.get("pass"))), None)
    rossi = []
    if mio is None:
        rossi.append("il piano non e' fra le combinazioni lecite (budget, gemme, token, calendario o ROI)")
    # il migliore che la roadmap esegue, cercato in tutta la lista (9 nov 2026: coi primi 400 soli, se erano tutti piani col pass fuori dal calendario, si prendeva il primo non eseguibile
    # e «jolly 50 + carte TRK 50» al 75% risultava 4,7% sotto, quando il migliore eseguibile era a 1,4%)
    best = next((x for x in sani if eseguibile(R, x, win, win_c, pi.get("solo"))[0]), None)
    if best is None:
        rossi.append("nessun piano lecito sta nella roadmap")
        best = sani[0]
    gap = (best["punti"] - mio["punti"]) / abs(best["punti"]) if mio and best["punti"] else 0.0
    if mio and gap > TOLL + 1e-6:
        rossi.append(f"obiettivo {100 * gap:.1f}% sotto il migliore ({best['n']}, via {best['via']} {best['g']})")
    ok_r, e = eseguibile(R, mio or best, win, win_c, pi.get("solo"))
    if not ok_r:
        rossi.append("la roadmap non esegue tutto il piano")
    if mio:
        if mio["oro"] > mio["oro_m"] + 1e-6:
            rossi.append("oro speso oltre l'oro del mese")
        if mio["ott"] - mio["sp"] < -1e-6:
            rossi.append(f"ROI negativo {mio['ott'] - mio['sp']:.0f}")
    if vo.get("buste_gemme"):
        rossi.append("gemme in buste")
    if vo["buste"] and not oro_buste:
        rossi.append("buste in oro con la spunta spenta")
    # simula riceve le gemme del mese gia' con la cassa di oggi (come nel piano): la cassa la conta due volte, si toglie
    g_fin = e["gem_fine"] - R.saldo()["gem"]
    if abs(g_fin - pi["esito"]["gemme"]) > 1.0:
        rossi.append(f"gemme a fine mese: piano {pi['esito']['gemme']:.0f}, simula {g_fin:.0f}")
    roi_mio, roi_best = (mio["ott"] - mio["sp"]) if mio else 0, best["ott"] - best["sp"]
    riga = (f"{'ROSSO' if rossi else 'ok   '} {nome:36} spunta {'si' if oro_buste else 'no'} wr {100 * win:.0f}/{100 * win_c:.0f} {R.via_cambio or 'wr':9} | piano Q{vo['quick']} P{vo['premier']} C{vo['costruiti']} B{vo['buste']}"
            f"{' +' + str(g) + ' ' + via + ' in gemme' if via else ''} | {'= migliore' if gap <= 1e-6 else f'{100 * gap:.1f}% sotto'} | ROI {roi_mio:,.0f} (migliore per obiettivo {roi_best:,.0f})"
            + ("" if not rossi else " | " + "; ".join(rossi)))
    return bool(rossi), riga


def casi(R):
    win_l, win_c = RS.win_stimato(*R.__dict__.get("_wr_l", (0.39, 149))), RS.win_stimato(*R.__dict__.get("_wr_c", (0.48, 1215)))
    wr = [(round(win_l, 3), round(win_c, 3)), (0.30, 0.30), (0.55, 0.55), (0.75, 0.75)]
    for (w, wc), busta, ob, (nome, pesi) in itertools.product(wr, (False, True), (False, True), GOAL):
        yield w, wc, busta, ob, nome, pesi


def main():
    R = RS.carica()
    t0, rossi, n = time.time(), 0, 0
    for w, wc, busta, ob, nome, pesi in casi(R):
        R.imposta_cambio(w, wc, busta=busta)
        r, riga = controlla(R, nome, pesi, w, wc, ob)
        rossi += r; n += 1
        print(riga, flush=True)
    print(f"{n} casi, {rossi} rossi, {time.time() - t0:.0f} s")
    return 1 if rossi else 0


def prova():
    """La negativa: un piano con un Quick in meno o con una via in gemme sbagliata deve essere rosso; il piano vero dello stesso caso verde."""
    R = RS.carica()
    w, wc = 0.42, 0.48
    R.imposta_cambio(w, wc)
    pi = R.piano({"carte": 1.0}, w, "TRK", win_c=wc, oro_buste=False)
    r_vero, riga_v = controlla(R, "carte TRK", {"carte": 1.0}, w, wc, False, pi)
    import copy
    peggio = copy.deepcopy(pi)
    peggio["voci"]["quick"] = max(0, peggio["voci"]["quick"] - 1)
    r_p, riga_p = controlla(R, "carte TRK", {"carte": 1.0}, w, wc, False, peggio)
    bustine = copy.deepcopy(pi); bustine["voci"]["buste_gemme"] = 2
    r_b, riga_b = controlla(R, "carte TRK", {"carte": 1.0}, w, wc, False, bustine)
    casi_ = [("il piano vero e' verde", not r_vero), ("un Quick in meno e' rosso", r_p), ("gemme in buste e' rosso", r_b)]
    # i tre difetti trovati il 9 nov 2026, ognuno rosso col piano di prima: ingressi in gemme a griglia nel mix (mancava il 9), solo il massimo col goal solo (fuori dalla roadmap),
    # i massimi del mix presi dal solo piano senza pass quando il pass non sta nella roadmap
    for nome, pesi, w_, wc_, ob in (("gemme 50 + jolly 50", {"gemme": 0.5, "jolly": 0.5}, w, wc, False), ("carte FRA", {"carte": 1.0}, 0.55, 0.55, False),
                                    ("gemme 34 + jolly 33 + carte TRK 33", {"gemme": 0.34, "jolly": 0.33, "carte": 0.33}, 0.30, 0.30, True)):
        R.imposta_cambio(w_, wc_)
        r_, riga_ = controlla(R, nome, pesi, w_, wc_, ob)
        casi_.append((f"{nome} al {100 * w_:.0f}% e' verde", not r_))
        print(riga_)
    for t, ok in casi_:
        print(("  ok   " if ok else "  ROSSO ") + t)
    print(riga_v); print(riga_p); print(riga_b)
    return 0 if all(ok for _, ok in casi_) else 1


if __name__ == "__main__":
    sys.exit(prova() if "--prova" in sys.argv else main())
