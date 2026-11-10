"""Le fonti di mana per colore che un mazzo da 40 carte deve avere, dalla tabella di Frank Karsten, e quanto costa stare sotto.

Fonte, letta il 10 ott 2026 dall'articolo originale (API di TCGplayer, non a memoria):
    Frank Karsten, «How Many Sources Do You Need to Consistently Cast Your Spells? A 2022 Update», TCGplayer
    (gia' ChannelFireball), 2 ago 2022. Colonna «40-card deck» della tabella riassuntiva.
Le ipotesi dell'articolo: 17 terre su 40; «lanciare con costanza» = almeno 89 + M % di probabilita' di avere le fonti
del colore entro il turno M, sul play, sapendo di avere almeno M terre (90% per un costo 1, 91% per un costo 2, ...);
mulligan di Londra ragionevole; solo terre come fonti, niente selezione. Carte d'oro: +1 fonte per ogni colore
(«an imprecise hack, but it generally leads to good results»). Lo splash l'articolo non lo tratta.

Il conto di Karsten dice quanto spesso si lancia una carta in curva; non dice quante partite si perdono. Per questo
--taratura lo misura sui game data di 17Lands (Premier, 6 set): per ogni partita il deficit di fonti nei colori
principali, e quanto vince un mazzo con quel deficit oltre l'atteso (stesso modello di Companion/Comune/mazzo_perfetto.py:
qualita' delle carte, bravura, chi comincia, mulligan). Correlazione, non causa; Premier, non Quick.

    python -I -X utf8 Companion/Drafter/fonti_mana.py "Sphinx's Approach" "Teyo, Lightshield Expert"   # cosa chiede una carta
    python -I -X utf8 Companion/Drafter/fonti_mana.py --taratura      # Note/Fonti_Mana_Karsten.md e Regole/fonti_mana_karsten.json
    python -I -X utf8 Companion/Drafter/fonti_mana.py --prova         # collaudo della tabella e del lettore dei costi
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import percorsi  # la casa del Companion: i percorsi stanno in Companion/percorsi.py (13 ott 2026)
import progetto as PR  # i file del set e del formato: Espansioni/<SET>/<Formato>/progetto.json (16 ott 2026)
import glob
import gzip
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = percorsi.ROOT
OUTJ = os.path.join(ROOT, "Regole", "fonti_mana_karsten.json")
NOTA = os.path.join(ROOT, "Note", "Fonti_Mana_Karsten.md")
FONTE = ("Frank Karsten, «How Many Sources Do You Need to Consistently Cast Your Spells? A 2022 Update», "
         "TCGplayer, 2 ago 2022, colonna 40-card deck (17 terre)")
COLORI = "WUBRG"
BASE = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}

# (mana generico, simboli del colore) -> fonti del colore. Le 18 righe della tabella, colonna 40 carte, con l'esempio
# dell'articolo accanto per poterle ricontrollare.
KARSTEN_40 = {
    (5, 1): 6,   # 5C   Drowner of Hope
    (4, 1): 6,   # 4C   Doubling Season
    (3, 1): 7,   # 3C   Collected Company
    (2, 1): 8,   # 2C   Reckless Stormseeker
    (5, 2): 8,   # 5CC  Hullbreaker Horror
    (1, 1): 9,   # 1C   Ledger Shredder
    (4, 2): 9,   # 4CC  Primeval Titan
    (0, 1): 9,   # C    Monastery Swiftspear
    (3, 2): 10,  # 3CC  Baneslayer Angel
    (4, 3): 10,  # 4CCC Nyxbloom Ancient
    (2, 2): 11,  # 2CC  Wrath of God
    (3, 3): 11,  # 3CCC Massacre Wurm
    (1, 2): 12,  # 1CC  Narset, Parter of Veils
    (2, 3): 13,  # 2CCC Garruk, Primal Hunter
    (0, 2): 14,  # CC   Lord of Atlantis
    (1, 3): 14,  # 1CCC Cryptic Command
    (1, 4): 15,  # 1CCCC Unnatural Growth
    (0, 3): 16,  # CCC  Goblin Chainwhirler
}


def fonti_richieste(generico, simboli):
    """Fonti del colore per lanciare in curva. Fuori tabella: si prende la riga piu' vicina con lo stesso numero di
    simboli (piu' mana generico = meno fonti, quindi oltre l'ultima riga si tiene l'ultima: e' prudente)."""
    if simboli <= 0:
        return 0
    if (generico, simboli) in KARSTEN_40:
        return KARSTEN_40[(generico, simboli)]
    righe = sorted(g for g, s in KARSTEN_40 if s == simboli)
    if not righe:
        return max(KARSTEN_40.values())
    g = min(max(generico, righe[0]), righe[-1])
    return KARSTEN_40[(g, simboli)]


_SF = None


def _scryfall():
    """nome minuscolo -> (costo della faccia davanti, tipo della faccia davanti, testo, colori prodotti)."""
    global _SF
    if _SF is not None:
        return _SF
    f = sorted(glob.glob(os.path.join(ROOT, "Dati", "scryfall", "oracle_cards", "oracle-cards-*.jsonl.gz")))
    if not f:
        sys.exit("Manca il bulk di Scryfall in Dati/scryfall/oracle_cards/")
    _SF = {}
    with gzip.open(f[-1], "rt", encoding="utf-8") as fh:
        for r in fh:
            r = r.strip().rstrip(",")
            if not r.startswith("{"):
                continue
            c = json.loads(r)
            if c.get("layout") in ("art_series", "token", "double_faced_token", "emblem"):
                continue
            facce = c.get("card_faces") or [c]
            costo = facce[0].get("mana_cost") if c.get("card_faces") else c.get("mana_cost")
            testo = " ".join((x.get("oracle_text") or "") for x in facce).lower()
            rec = (costo or "", facce[0].get("type_line") or c.get("type_line") or "", testo,
                   "".join(ch for ch in (c.get("produced_mana") or []) if ch in COLORI))
            for nm in (c["name"], facce[0].get("name") or c["name"]):
                _SF.setdefault(nm.lower(), rec)
    return _SF


def _rec(nome):
    s = _scryfall()
    return s.get(nome.lower()) or s.get(nome.lower().split(" // ")[0])


def richiesta(nome):
    """{colore: fonti} che la carta chiede (vuoto per terre e incolori). Ibridi e phyrexiani contano come generico."""
    r = _rec(nome)
    if not r or "Land" in r[1]:
        return {}
    simboli = re.findall(r"\{([^}]+)\}", r[0])
    gen, col = 0, {}
    for s in simboli:
        if s.isdigit():
            gen += int(s)
        elif s in COLORI:
            col[s] = col.get(s, 0) + 1
        elif s != "X":
            gen += 1          # ibrido, phyrexiano, {C}: si paga anche senza quel colore
    oro = len(col) > 1
    out = {}
    for c, n in col.items():
        altri = sum(v for k, v in col.items() if k != c)
        out[c] = fonti_richieste(gen + altri, n) + (1 if oro else 0)
    return out


def produce(nome, basi_nel_mazzo=COLORI):
    """I colori che una terra produce. Una terra che cerca una base conta per i colori delle basi nel mazzo."""
    if nome in BASE:
        return BASE[nome]
    r = _rec(nome)
    if not r or "Land" not in r[1]:
        return ""
    if "search your library for a basic land" in r[2]:
        return "".join(c for c in COLORI if c in basi_nel_mazzo)
    return r[3]


def conto(mazzo):
    """mazzo = {nome: copie} delle 40. -> {colore: dict(serve, ha, deficit, carta)} per ogni colore che il mazzo chiede."""
    basi = "".join(BASE[n] for n in mazzo if n in BASE)
    fonti = {c: 0 for c in COLORI}
    for n, q in mazzo.items():
        for c in produce(n, basi):
            fonti[c] += q
    out = {}
    for n, q in mazzo.items():
        for c, f in richiesta(n).items():
            if c not in out or f > out[c]["serve"]:
                out[c] = {"serve": f, "carta": n}
    for c, v in out.items():
        v["ha"] = fonti[c]
        v["deficit"] = max(0, v["serve"] - fonti[c])
        v["carte"] = sum(q for n, q in mazzo.items() if c in richiesta(n))
    return out


def _pesato(mazzo, fonti):
    """Deficit pesato: per ogni copia di ogni carta, le fonti che mancano alla tabella, sommate."""
    return sum(q * max(0, f - fonti.get(c, 0)) for n, q in mazzo.items() for c, f in richiesta(n).items())


def divisione(mazzo):
    """La divisione delle basi fra i colori del mazzo, contro la migliore con lo stesso numero di basi (le altre terre
    ferme). -> dict(vero, meglio, scarto, basi_vere, basi_meglio). Stessa misura di --taratura."""
    basi = {BASE[n]: q for n, q in mazzo.items() if n in BASE}
    nb = sum(basi.values())
    fisse = {c: 0 for c in COLORI}
    for n, q in mazzo.items():
        if n not in BASE:
            for c in produce(n, "".join(basi)):
                fisse[c] += q
    chiesti = sorted({c for n in mazzo for c in richiesta(n)} | set(basi), key=COLORI.index)
    def fonti_di(div):
        return {c: fisse[c] + div.get(c, 0) for c in COLORI}
    vero = _pesato(mazzo, fonti_di(basi))
    meglio, div_m = vero, basi
    def riparti(i, resto, acc):
        nonlocal meglio, div_m
        if i == len(chiesti) - 1:
            d = dict(acc, **{chiesti[i]: resto})
            v = _pesato(mazzo, fonti_di(d))
            if v < meglio - 1e-9:
                meglio, div_m = v, d
            return
        for a in range(resto + 1):
            riparti(i + 1, resto - a, dict(acc, **{chiesti[i]: a}))
    if chiesti and len(chiesti) <= 3:
        riparti(0, nb, {})
    return {"vero": vero, "meglio": meglio, "scarto": vero - meglio, "basi_vere": basi,
            "basi_meglio": {c: q for c, q in div_m.items() if q}}


# ---------------------------------------------------------------- taratura sui game data di 17Lands
def taratura():
    import numpy as np
    import pandas as pd
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mazzo_perfetto as MP
    tutte = []
    for s in MP.SET:
        t0 = time.time()
        path = PR.game_data(s)
        testa = pd.read_csv(path, nrows=0).columns
        deck = [c for c in testa if c.startswith("deck_")]
        nomi = [c[5:] for c in deck]
        base = ["draft_id", "won", "on_play", "num_mulligans", "main_colors", "splash_colors",
                "user_n_games_bucket", "user_game_win_rate_bucket"]
        df = pd.read_csv(path, usecols=base + deck, dtype={c: np.int8 for c in deck}, low_memory=False)
        M = df[deck].to_numpy(np.int8)
        w = (df["won"].astype(str) == "True").to_numpy(np.float64)
        tipi = [(_rec(n) or ("", "", "", ""))[1] for n in nomi]
        terra = np.array(["Land" in t for t in tipi])
        # fonti: per ogni colore quante terre del mazzo lo producono (le terre che cercano una base: tutti i colori)
        F = np.zeros((len(df), 5), np.int16)
        for j in np.where(terra)[0]:
            p = produce(nomi[j])
            for i, c in enumerate(COLORI):
                if c in p:
                    F[:, i] += M[:, j]
        # richiesta: per ogni colore la carta piu' esigente presente nel mazzo
        R = np.zeros((len(nomi), 5), np.int16)
        for j, n in enumerate(nomi):
            if not terra[j]:
                for c, f in richiesta(n).items():
                    R[j, COLORI.index(c)] = f
        S = np.zeros((len(df), 5), np.int16)
        pres = M > 0
        for i in range(5):
            col = R[:, i]
            idx = np.where(col > 0)[0]
            if len(idx):
                S[:, i] = (pres[:, idx] * col[idx]).max(1)
        D = np.maximum(0, S - F)
        main = df["main_colors"].astype(str).to_numpy()
        spl = df["splash_colors"].fillna("").astype(str).to_numpy()
        mm = np.array([[c in m for c in COLORI] for m in main])
        ms = np.array([[c in m for c in COLORI] for m in spl])
        dmain = np.where(mm, D, 0).max(1)
        # la divisione delle basi: deficit pesato (copie x fonti mancanti) della divisione vera contro la migliore
        # possibile con le stesse basi dei due colori principali, le altre terre ferme
        H = np.zeros((len(df), 5, 19), np.int16)      # copie di carte che chiedono f fonti del colore i
        for i in range(5):
            for f in range(1, 19):
                idx = np.where(R[:, i] == f)[0]
                if len(idx):
                    H[:, i, f] = M[:, idx].sum(1)
        lv = np.arange(19)
        DEF = np.zeros((len(df), 5, 19), np.float32)   # deficit pesato con s fonti
        for s_ in range(19):
            DEF[:, :, s_] = (H * np.maximum(0, lv - s_)).sum(2)
        jb = {c: nomi.index(n) for n, c in BASE.items() if n in nomi}
        Bm = np.zeros((len(df), 5), np.int16)
        for c, j in jb.items():
            Bm[:, COLORI.index(c)] = M[:, j]
        vero = np.full(len(df), np.nan); meglio = np.full(len(df), np.nan); carte_dif = np.zeros(len(df))
        due = np.where(mm.sum(1) == 2)[0]
        if len(due):
            ord_ = np.argsort(~mm[due], axis=1, kind="stable")
            i1, i2 = ord_[:, 0], ord_[:, 1]
            n = Bm[due, i1] + Bm[due, i2]
            f1, f2 = F[due, i1] - Bm[due, i1], F[due, i2] - Bm[due, i2]
            best = np.full(len(due), np.inf)
            for a in range(int(n.max()) + 1):
                s1 = np.clip(f1 + a, 0, 18); s2 = np.clip(f2 + n - a, 0, 18)
                t = DEF[due, i1, s1] + DEF[due, i2, s2]
                best = np.where(a <= n, np.minimum(best, t), best)
            meglio[due] = best
            vero[due] = DEF[due, i1, np.minimum(F[due, i1], 18)] + DEF[due, i2, np.minimum(F[due, i2], 18)]
            carte_dif[due] = ((H[due, i1, :] * (lv[None, :] > F[due, i1][:, None])).sum(1)
                              + (H[due, i2, :] * (lv[None, :] > F[due, i2][:, None])).sum(1))
        # la qualita' del mazzo e l'atteso: come Companion/Comune/mazzo_perfetto.py (carte con 200+ partite, partita esclusa)
        cop = M[:, ~terra].astype(np.float32)
        pr = (cop > 0).astype(np.float32)
        G = pr.sum(0); W = (pr * w[:, None].astype(np.float32)).sum(0)
        ok = G >= 200
        inv = np.where(ok, 1.0 / np.maximum(G - 1, 1), 0).astype(np.float32)
        a = cop[:, ok] @ (W[ok] * inv[ok]); b_ = cop[:, ok] @ inv[ok]; n_ok = cop[:, ok].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            qual = (a - w * b_) / n_ok * 100
        nb = pd.to_numeric(df["user_n_games_bucket"], errors="coerce")
        br = pd.to_numeric(df["user_game_win_rate_bucket"], errors="coerce")
        d = pd.DataFrame({
            "set": s, "draft": df["draft_id"].to_numpy(), "won": w, "qual": qual,
            "on_play": (df["on_play"].astype(str) == "True").astype(float),
            "mull": pd.to_numeric(df["num_mulligans"], errors="coerce").fillna(0).to_numpy(),
            "bravo": np.where(nb >= 50, br, np.nan), "terre": M[:, terra].sum(1), "magie": M[:, ~terra].sum(1),
            "colori": mm.sum(1), "splash": ms.any(1), "dmain": dmain,
            "dsplash": np.where(ms, D, 0).max(1),
            "divisione": vero - meglio, "carte_dif": carte_dif,
        })
        d = d[(d["magie"] >= 20) & (d["magie"] <= 26) & (d["colori"] == 2) & d["qual"].notna()].copy()
        mb = d["bravo"].mean()
        X = np.column_stack([np.ones(len(d)), d["qual"], d["bravo"].fillna(mb), d["bravo"].isna().astype(float),
                             d["on_play"], d["mull"]])
        beta = np.linalg.lstsq(X, d["won"].to_numpy(), rcond=None)[0]
        d["res"] = d["won"] - X @ beta
        tutte.append(d)
        print(f"{s}: {len(d)} partite bicolori, {time.time() - t0:.0f}s", file=sys.stderr)
    d = pd.concat(tutte, ignore_index=True)

    def tab(maschera, col, fasce=((0, 0), (1, 1), (2, 2), (3, 3), (4, 99))):
        x = d[maschera]
        righe = []
        for lo, hi in fasce:
            v = str(lo) if lo == hi else (f"{lo}+" if hi >= 99 else f"{lo}-{hi}")
            y = x[(x[col] >= lo) & (x[col] <= hi)]
            if len(y) < 200:
                continue
            # errore standard per draft (le partite dello stesso mazzo non sono indipendenti)
            g = y.groupby("draft")["res"].agg(["sum", "count"])
            m = g["sum"].sum() / g["count"].sum()
            se = np.sqrt(((g["sum"] - m * g["count"]) ** 2).sum()) / g["count"].sum()
            righe.append({"deficit": v, "partite": int(len(y)), "quota": round(len(y) / len(x) * 100, 1),
                          "win": round(y["won"].mean() * 100, 2), "oltre": round(m * 100, 2), "se": round(se * 100, 2)})
        return righe
    senza = ~d["splash"]
    out = {
        "fonte": FONTE, "tabella_40": {f"{g}+{s}": f for (g, s), f in KARSTEN_40.items()},
        "data": time.strftime("%Y-%m-%d %H:%M"), "set": MP.SET, "partite": int(len(d)),
        "principali_senza_splash": tab(senza, "dmain"),
        "principali_con_splash": tab(~senza, "dmain"),
        "splash": tab(~senza, "dsplash"),
        "divisione_senza_splash": tab(senza, "divisione", ((0, 0), (0.5, 2), (2.5, 5), (5.5, 9), (9.5, 999))),
        "carte_in_difetto_senza_splash": tab(senza, "carte_dif", ((0, 0), (1, 2), (3, 5), (6, 9), (10, 99))),
    }
    json.dump(out, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def md(righe):
        r = ["| deficit di fonti | partite | quota | win rate | oltre l'atteso (punti) | ±1 e.s. |",
             "| :--- | ---: | ---: | ---: | ---: | ---: |"]
        r += [f"| {x['deficit']} | {x['partite']:,} | {x['quota']}% | {x['win']}% | {x['oltre']:+.2f} | {x['se']:.2f} |"
              for x in righe]
        return "\n".join(r)
    testo = f"""# Fonti di mana: Karsten e quanto costa stare sotto

Generato da `python -I -X utf8 Companion/Drafter/fonti_mana.py --taratura` il {out['data']}. Dati: `Regole/fonti_mana_karsten.json`.

**La tabella.** {FONTE}. Ipotesi dell'articolo: 17 terre su 40, probabilita' 89 + M % di avere le fonti al turno M sul play
sapendo di avere M terre, mulligan di Londra, solo terre come fonti. Carte d'oro +1 fonte per colore. Lo splash non e' trattato.

**La misura.** {out['partite']:,} partite di mazzi bicolori del Premier Draft di 17Lands ({', '.join(MP.SET)}). Per ogni
partita il deficit e' il massimo, sui colori principali, di (fonti chieste dalla carta piu' esigente − fonti nel mazzo).
«Oltre l'atteso» = vittorie in piu' o in meno a parita' di qualita' delle carte, bravura del giocatore, play/draw e mulligan
(modello di `Companion/Comune/mazzo_perfetto.py`). Errore standard raggruppato per draft. Correlazione, non causa; Premier, non Quick.

## Colori principali, mazzi senza splash
{md(out['principali_senza_splash'])}

## Colori principali, mazzi con splash
{md(out['principali_con_splash'])}

## Il colore dello splash (deficit contro la tabella, che per lo splash non e' scritta)
{md(out['splash'])}

## La divisione delle basi (mazzi senza splash)
Deficit pesato = somma, carta per carta e copia per copia, delle fonti che mancano alla tabella. «Divisione» = deficit pesato
della divisione vera delle basi fra i due colori meno quello della divisione migliore con le stesse basi (0 = divise bene).
{md(out['divisione_senza_splash'])}

## Carte in difetto (mazzi senza splash)
Copie di carte dei colori principali con meno fonti di quelle che la tabella chiede.
{md(out['carte_in_difetto_senza_splash'])}

## Lettura (10 ott 2026, sui numeri della prima taratura) e cosa ne fa il cancello
- Con 17 terre la tabella non si rispetta quasi mai in un bicolore: una carta 1C per colore chiede 9 + 9 = 18 fonti. Il 92%
  dei mazzi sta sotto, e stare sotto non si accompagna a vincere di meno: le carte in difetto vanno perfino col segno piu'
  (sono i mazzi aggressivi, pieni di carte colorate a costo basso). Il deficit di Karsten non e' un rosso.
- Tre mazzi su quattro dividono gia' le basi nel modo migliore. Il costo si vede solo nelle divisioni molto sbagliate
  (scarto 10 o piu', 0,6% dei mazzi): circa −1 punto contro i mazzi divisi bene, al limite del rumore. Quindi giallo.
- Rosso resta solo il colore giocato senza nessuna fonte. La regola e' stata scritta prima di guardare i numeri:
  rosso se un deficit costa almeno 1 punto con l'intervallo che esclude lo zero, giallo se si misura sotto.
- La divisione e' tarata sui bicolori senza splash: su un mazzo a tre colori il cancello la stampa e non la giudica.
"""
    open(NOTA, "w", encoding="utf-8").write(testo)
    print(testo)


PROVA = {   # carta -> richiesta attesa, letta a mano dalla tabella
    "Teyo, Lightshield Expert": {"W": 9},          # 1W  = 1C
    "Sphinx's Approach": {"U": 12},               # 1UU = 1CC
    "Ghalta the Immovable": {"W": 6},             # 8W  -> oltre la tabella: 5C = 6
    "Yargle, Goliath of Otaria": {"U": 6},        # 4U  = 4C
    "Ruric Thar, Biomagus": {"U": 9},             # 4UU = 4CC
    "Island": {},
}


def main():
    if "--taratura" in sys.argv:
        taratura()
        return
    if "--prova" in sys.argv:
        err = 0
        for n, atteso in PROVA.items():
            r = richiesta(n)
            err += r != atteso
            print(f"{'ok' if r == atteso else 'NO'} {n:28s} {r} atteso {atteso}")
        c = conto({"Teyo, Lightshield Expert": 2, "Sphinx's Approach": 4, "Plains": 6, "Island": 11})
        print(c)
        ok = c["W"]["deficit"] == 3 and c["U"]["deficit"] == 1
        err += not ok
        print("conto del mazzo del 10 ott:", "ok" if ok else "NO")
        sys.exit(1 if err else 0)
    for n in sys.argv[1:]:
        print(n, _rec(n)[0] if _rec(n) else "?", richiesta(n))


if __name__ == "__main__":
    main()
