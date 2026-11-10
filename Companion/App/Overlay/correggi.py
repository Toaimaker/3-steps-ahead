"""Fix: il mazzo inviato corretto quanto basta perche' il cancello diventi verde (Autore, 7 nov 2026: «finche' il gate e' rosso,
esiste un pulsante sotto al deck che dice fix, se lo premo riappare l'hud che mi aiuta a correggere»).

Non cambia il cancello e non sceglie un mazzo nuovo: parte dal mazzo inviato e fa solo gli scambi che tolgono i rossi.
- le rimozioni vere dei tuoi colori in sideboard entrano al posto delle carte che fanno perdere meno voto, provando tutte le
  combinazioni col giudice dei mazzi (mai un'altra rimozione: uscendo farebbe un altro rosso). Il punteggio del cancello non
  basta: il 7 nov 2026 toglieva Bloodline Recollector e Murmuring Volume, 2,32 vittorie contro le 2,85 del mazzo con 3 Tether;
- meno o piu' di 40 carte, o un colore senza fonti: si riparte dal primo dei 3 mazzi proposti, se e' fatto delle carte del pool.
Scrive Log_Arena/mazzo_fix.json nel formato di mazzi_costruzione.json, cosi' l'overlay lo segue come un mazzo proposto, con gli
scambi, l'esito del cancello sul mazzo corretto e il suo voto. Il voto gira in un processo a parte, come in controlla_mazzo:
rating_mazzi accende all'import il giudice validato, che qui dentro cambierebbe il punteggio del cancello.

    py -I -X utf8 Companion/App/Overlay/correggi.py            il mazzo inviato di adesso -> Log_Arena/mazzo_fix.json
    py -I -X utf8 Companion/App/Overlay/correggi.py --prova    i casi, senza scrivere niente
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import itertools
import json
import subprocess
import time

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
import rimozioni as RIM  # noqa: E402

FIX_JSON = os.path.join(RADICE, "Log_Arena", "mazzo_fix.json")
MAZZI_JSON = os.path.join(RADICE, "Log_Arena", "mazzi_costruzione.json")
BASI = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def rimozioni_fuori(CM, main, side):
    """Le stesse carte per cui il cancello dice rosso: rimozioni vere dei colori del mazzo rimaste in sideboard."""
    col = CM.colori_mazzo(main)
    return [(n, q) for n, q in side.items() if RIM.classifica(n)[0] == "vera" and set(CM.FM.richiesta(n)) <= set(col) and not RIM.vincolata(n)]


def peggiore(CM, main, entra):
    """La carta da togliere per far entrare `entra`: quella che col punteggio del cancello fa guadagnare di piu' allo scambio."""
    ME = CM.ME
    carte = [CM.carta_eq(n) for n, q in main.items() if not CM.e_terra(n) for _ in range(q)]
    s = tuple(sum(c) for c in zip(*(ME.contributo(x) for x in carte)))
    y = CM.carta_eq(entra)
    uscibili = [x for x in {c["n"]: c for c in carte}.values() if x["n"] != entra and RIM.classifica(x["n"])[0] != "vera"]
    if not uscibili:
        return None
    return max(uscibili, key=lambda x: ME.punteggio(tuple(a - b + c for a, b, c in zip(s, ME.contributo(x), ME.contributo(y))), len(carte)))["n"]


def lista_proposta(mazzi_json=MAZZI_JSON):
    """Il primo dei 3 mazzi proposti come {nome: copie}, None se il file non c'e'."""
    try:
        d = json.load(open(mazzi_json, encoding="utf-8"))
        m = next(x for x in d["mazzi"] if x.get("n") == 1)
    except (OSError, ValueError, StopIteration):
        return None
    out = {}
    for _c, carte in m.get("costi") or []:
        for q, n in carte:
            out[n] = out.get(n, 0) + int(q)
    for q, n in m.get("terre") or []:
        out[n] = out.get(n, 0) + int(q)
    return out


def migliore_uscita(CM, main, entrano, giudice):
    """Quali carte togliere per far entrare `entrano`, provando tutte le combinazioni. giudice(liste) -> un voto per lista, piu' alto e' meglio."""
    uscibili = [n for n, q in main.items() if not CM.e_terra(n) and RIM.classifica(n)[0] != "vera" for _ in range(q)]
    prove = sorted({tuple(sorted(c)) for c in itertools.combinations(uscibili, len(entrano))})
    if not prove:
        return None
    liste = []
    for esce in prove:
        l = dict(main)
        for n in entrano:
            l[n] = l.get(n, 0) + 1
        for n in esce:
            l[n] -= 1
        liste.append({n: q for n, q in l.items() if q > 0})
    voti = giudice(liste)
    return max(zip(voti, prove), key=lambda x: x[0])[1]


def correggi(CM, mz, proposta=None, giudice=None):
    """-> dict(main, side, scambi, rossi): il mazzo corretto, gli scambi fatti [[esce, entra], ...] e i rossi che restano.
    giudice: vedi migliore_uscita; senza, una carta alla volta col punteggio del cancello (le prove non lanciano il giudice)."""
    main, side = dict(mz["main"]), dict(mz["side"])
    pool = dict(side)
    for n, q in main.items():
        pool[n] = pool.get(n, 0) + q
    chiavi = {k for liv, k, _ in CM.controlla(dict(mz, main=main, side=side), stampa=False) if liv == "rosso"}
    scambi = []
    if chiavi & {"quaranta", "fonti"} and proposta:
        faccia = {n.split(" // ")[0]: n for n in pool}
        nuova = {faccia.get(n.split(" // ")[0], n): q for n, q in proposta.items()}
        if all(n in BASI or pool.get(n, 0) >= q for n, q in nuova.items()):      # la proposta e' di questo pool: i file dei mazzi possono essere di un draft di prima
            main = nuova
            side = {n: q - main.get(n, 0) for n, q in pool.items() if q > main.get(n, 0) and n not in BASI}
    def scambia(esce, entra):
        for d, n, k in ((main, entra, 1), (side, entra, -1), (main, esce, -1), (side, esce, 1)):
            d[n] = d.get(n, 0) + k
            if d[n] <= 0:
                del d[n]
        scambi.append([esce, entra])
    for _ in range(sum(side.values()) + 1):
        fuori = rimozioni_fuori(CM, main, side)
        if not fuori:
            break
        entrano = [n for n, q in fuori for _ in range(q)]
        if giudice and len(entrano) <= 3:       # oltre 3 le combinazioni sono troppe: una alla volta
            uscite = migliore_uscita(CM, main, entrano, giudice)
            if uscite is None:
                break
            for esce, entra in zip(uscite, entrano):
                scambia(esce, entra)
            continue
        entra = entrano[0]
        esce = peggiore(CM, main, entra)
        if esce is None:
            break
        scambia(esce, entra)
    rossi = [t for liv, _, t in CM.controlla(dict(mz, main=main, side=side), stampa=False) if liv == "rosso"]
    return dict(main=main, side=side, scambi=scambi, rossi=rossi)


def voti(liste, ids):
    """I voti delle liste, in un processo a parte. ids: {nome: cardId}. -> lista di dict di voto_inviato."""
    tmp = FIX_JSON + ".prove"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump([{str(ids[n]): q for n, q in l.items()} for l in liste], f)
    try:
        cmd = [sys.executable, "-I", "-X", "utf8", os.path.abspath(__file__), "--voti", tmp]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240, env=dict(os.environ, PYTHONIOENCODING="utf-8")).stdout
    finally:
        os.remove(tmp)
    riga = next((r for r in out.splitlines() if r.startswith("VOTI_FIX ")), None)
    return json.loads(riga[len("VOTI_FIX "):]) if riga else None


def solo_voti(file):
    """Dentro il processo a parte: voto_inviato di rating_mazzi su ogni lista, con lo stesso giudice e la stessa scala del mazzo inviato."""
    sys.path.insert(0, os.path.join(RADICE, "Companion", "Drafter"))
    argv, sys.argv = sys.argv, sys.argv[:1]
    import rating_mazzi as RM
    sys.argv = argv
    finto = {}
    RIM.ultimo_mazzo = lambda *_a, **_k: finto
    out = []
    for lista in json.load(open(file, encoding="utf-8")):
        finto.clear()
        finto.update(InternalEventName="", CourseDeck={"MainDeck": [{"cardId": int(k), "quantity": q} for k, q in lista.items()]})
        out.append(RM.voto_inviato())
    print("VOTI_FIX " + json.dumps(out, ensure_ascii=False))


def ids_del_corso(c):
    """{nome: cardId} del mazzo e della sideboard del corso, con le terre base (Arena le ha in lista solo se sono nel mazzo)."""
    import controlla_mazzo as CM
    out = {}
    for k in ("MainDeck", "Sideboard"):
        for x in c["CourseDeck"].get(k) or []:
            out[CM.CD.DB.get(str(x["cardId"]), {}).get("n", str(x["cardId"]))] = x["cardId"]
    return out


def scrivi():
    import controlla_mazzo as CM
    mz = CM.da_log()
    if not mz:
        return 1
    ids = ids_del_corso(RIM.ultimo_mazzo())

    def giudice(liste):
        vv = voti(liste, ids) if all(n in ids for l in liste for n in l) else None      # una base che il mazzo inviato non aveva: niente voto
        return [x["S"] for x in vv] if vv else [0] * len(liste)
    fix = correggi(CM, mz, lista_proposta(), giudice)
    # senza un cardId per ogni carta il voto non si puo' fare: l'hud funziona lo stesso
    v = (voti([fix["main"]], ids) or [None])[0] if all(n in ids for n in fix["main"]) else None
    terre = sorted([q, n] for n, q in fix["main"].items() if CM.e_terra(n))
    if v:
        costi = v["costi"]
    else:
        costi = [[0, sorted([q, n] for n, q in fix["main"].items() if not CM.e_terra(n))]]
    m = dict(n=1, nome="FIX", coppia=(v or {}).get("coppia", ""), splash=(v or {}).get("splash", ""), tier=(v or {}).get("tier", "?"), vittorie=(v or {}).get("vittorie"),
             percentile=(v or {}).get("percentile"), costi=costi, terre=terre)
    d = dict(titolo="Il mazzo inviato corretto per il cancello", ora=time.strftime("%Y-%m-%d %H:%M:%S"), scambi=fix["scambi"], rossi=fix["rossi"], cambiato=fix["main"] != mz["main"], mazzi=[m])
    tmp = FIX_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FIX_JSON)
    print(json.dumps({k: d[k] for k in ("scambi", "rossi", "cambiato")}, ensure_ascii=False), "voto", (v or {}).get("tier"), (v or {}).get("vittorie"), (v or {}).get("percentile"))
    return 0


def prova():
    import controlla_mazzo as CM
    fra = {'Stingerquill Charm': 2, 'Memory Trap': 1, 'Archive Arbiter': 1, 'Screeching Soulbreaker': 1, 'Karn, Argent Defender': 1, 'Bloodline Recollector': 1, 'Proft, Sinister Mastermind': 1,
           'Surgical Precision': 1, 'Hexhaven Battalion': 1, 'Gallia, Tragic Host': 1, 'Thalia, the Survivor': 1, 'Campus Crier': 1, 'Tether Technician': 1, 'Mountain': 4, 'Mabel, Bitter Recluse': 1,
           'Stingerquill Voxmancer': 1, 'Void Extrapolator': 2, 'Rank Rat': 1, 'Murmuring Volume': 1, 'Living Library': 1, 'Rise of the Deathbringer': 1, 'Swamp': 7, 'Plains': 6, 'Dark Matter Manipulator': 1}
    panca = {'Screeching Soulbreaker': 1, 'Whiplash Wordsmith': 1, 'Stingcaster Mage': 1, 'Pia, Determined Rebuilder': 1, 'Tether Technician': 2, 'Desperate Futurescribe': 1, 'Edgar, Moonlit Sovereign': 1,
             'Gallia, the Merrymaker': 1, 'Refute Destiny': 1, 'Eardrum Rattler': 1, 'Skilled Battlecarver': 1, 'Loot, the Anomaly': 1, 'Heartstring Puller': 1, 'Flourishing Grapple': 1, 'Artifist Acumen': 1, 'Jace, Reality Sculptor': 1}
    mz = dict(nome="prova", main=fra, side=panca)
    f = correggi(CM, mz)
    entrate = [e for _, e in f["scambi"]]
    uscite = [u for u, _ in f["scambi"]]
    verde = dict(mz, main=f["main"], side=f["side"])
    side_senza = {n: q for n, q in panca.items() if n != "Tether Technician"}
    gia = correggi(CM, dict(mz, side=side_senza))
    # 41 carte: la proposta e' del pool e rimette 40
    troppe = dict(fra); troppe["Whiplash Wordsmith"] = 1
    corta = {n: q for n, q in panca.items() if n != "Whiplash Wordsmith"}
    proposta = dict(fra); proposta["Tether Technician"] = 1
    pr = correggi(CM, dict(mz, main=troppe, side=corta), proposta)
    # una proposta di un altro draft non si usa
    altra = dict(proposta); altra["Carta Di Un Altro Draft"] = 1
    al = correggi(CM, dict(mz, main=troppe, side=corta), altra)
    casi = [("il caso vero: entrano le 2 Tether", entrate == ["Tether Technician"] * 2),
            ("il cancello sul mazzo corretto e' verde", not f["rossi"]),
            ("restano 40 carte, le stesse del pool", sum(f["main"].values()) == 40 and sum(f["side"].values()) == sum(panca.values())),
            ("non esce nessuna rimozione", not any(RIM.classifica(u)[0] == "vera" for u in uscite)),
            ("nessuna rimozione resta fuori", not rimozioni_fuori(CM, verde["main"], verde["side"])),
            ("niente rossi: nessuno scambio", gia["scambi"] == [] and gia["main"] == fra),
            ("41 carte: si riparte dalla proposta", sum(pr["main"].values()) == 40),
            ("proposta di un altro draft: non si usa", "Carta Di Un Altro Draft" not in al["main"] and sum(al["main"].values()) == 41 and any("carte" in r for r in al["rossi"]))]
    for n, v in casi:
        print(("  ok   " if v else "  ROSSO ") + n)
    print(f"  esce {uscite} entra {entrate}")
    print(f"{sum(1 for _, v in casi if v)}/{len(casi)}")
    return 0 if all(v for _, v in casi) else 1


if __name__ == "__main__":
    if "--voti" in sys.argv:
        solo_voti(sys.argv[sys.argv.index("--voti") + 1])
    elif "--prova" in sys.argv:
        sys.exit(prova())
    else:
        sys.exit(scrivi())
