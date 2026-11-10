"""Cosa fare di ogni carta vista nella schermata di costruzione: il mazzo 1 dei proposti contro quello che c'e' a schermo
(3 nov 2026, Magic 07). Logica pura, senza finestre: la usano l'overlay (overlay.py) e la prova sul campione.

Il mazzo 1 e' il primo di `Log_Arena/mazzi_costruzione.json` (Companion/Drafter/rating_mazzi.py): `costi` =
[[costo, [[copie, nome], ...]], ...] e `terre` = [[copie, nome], ...]. Per ogni barra riconosciuta (riconosci.py):
- nel mazzo e il mazzo 1 le vuole tutte: VERDE «tieni»;
- nel mazzo e il mazzo 1 non la vuole: ROSSO «togli»;
- nel mazzo con piu' copie di quante ne vuole il mazzo 1: GIALLO «tieni N/M» (si tolgono le altre);
- fuori dal mazzo (in alto) e il mazzo 1 la vuole: VERDE «aggiungi»;
- fuori e non voluta: niente segno.
Le terre base si cambiano dal menu delle terre di Arena: la barra dice «porta a N» e il riquadro le elenca.

    py -I -X utf8 Companion/App/Overlay/confronto.py --prova    il caso vero del 3 nov 2026 sul campione (esce 1 se diverso)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
MAZZI_JSON = os.path.join(RADICE, "Log_Arena", "mazzi_costruzione.json")
BASI = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def faccia(nome):
    """Il nome come lo mostra la barra di Arena: la faccia davanti (l'anagrafe e i mazzi a volte hanno «A // B»)."""
    return nome.split(" // ")[0].strip()


def mazzo_obiettivo(file=MAZZI_JSON, n=1):
    """-> (descrizione, {nome: copie}) del mazzo n dei proposti, magie e terre."""
    d = json.load(open(file, encoding="utf-8"))
    m = next(x for x in d["mazzi"] if x.get("n") == n)
    voluto = {}
    for _costo, carte in m.get("costi", []):
        for q, nome in carte:
            voluto[faccia(nome)] = voluto.get(faccia(nome), 0) + int(q)
    for q, nome in m.get("terre", []):
        voluto[faccia(nome)] = voluto.get(faccia(nome), 0) + int(q)
    desc = dict(n=m.get("n"), nome=m.get("nome"), coppia=m.get("coppia"), splash=m.get("splash") or "", tier=m.get("tier"),
                vittorie=m.get("vittorie"), carte=sum(voluto.values()), ora=d.get("ora"))
    return desc, voluto


def decidi(lettura, voluto):
    """lettura: il risultato di riconosci.leggi_schermo. -> (segni, riepilogo).
    segni: [{zona, nome, copie, voluto, azione, colore, etichetta, barra}] una per barra; riepilogo: le liste da mostrare."""
    a_schermo = {}
    for z in ("mazzo", "fuori"):
        for b in lettura[z]:
            k = faccia(b["nome"])
            a_schermo.setdefault(k, {"mazzo": 0, "fuori": 0})[z] += b["copie"]
    segni = []
    restano = dict(voluto)      # le copie volute non ancora assegnate a una barra del mazzo
    for b in lettura["mazzo"]:
        k = faccia(b["nome"])
        v = voluto.get(k, 0)
        if k in BASI:
            if v == b["copie"]:
                az, col, et = "tieni", "verde", "tieni"
            elif v == 0:
                az, col, et = "togli", "rosso", "togli"
            else:
                az, col, et = "terre", "giallo", f"porta a {v}"
        else:
            tieni = min(b["copie"], restano.get(k, 0))
            restano[k] = restano.get(k, 0) - tieni
            if tieni == 0:
                az, col, et = "togli", "rosso", "togli" if b["copie"] == 1 else f"togli {b['copie']}"
            elif tieni == b["copie"]:
                az, col, et = "tieni", "verde", "tieni" if b["copie"] == 1 else f"tieni {tieni}"
            else:
                az, col, et = "parziale", "giallo", f"tieni {tieni}/{b['copie']}"
        segni.append(dict(zona="mazzo", nome=k, copie=b["copie"], voluto=v, azione=az, colore=col, etichetta=et, barra=b))
    for b in lettura["fuori"]:
        k = faccia(b["nome"])
        manca = max(0, voluto.get(k, 0) - a_schermo.get(k, {}).get("mazzo", 0)) if k not in BASI else 0
        if manca > 0:
            q = min(manca, b["copie"])
            segni.append(dict(zona="fuori", nome=k, copie=b["copie"], voluto=voluto[k], azione="aggiungi", colore="verde",
                              etichetta="aggiungi" if q == 1 else f"aggiungi {q}", barra=b))
    terre = [(k, a_schermo.get(k, {}).get("mazzo", 0), voluto.get(k, 0)) for k in sorted(BASI)
             if a_schermo.get(k, {}).get("mazzo", 0) != voluto.get(k, 0)]
    viste = set(a_schermo)
    non_viste = sorted(k for k in voluto if k not in viste and k not in BASI)
    riepilogo = dict(
        aggiungi=[(s["nome"], int(s["etichetta"].split()[-1]) if s["etichetta"][-1].isdigit() else 1)
                  for s in segni if s["azione"] == "aggiungi"],
        togli=[(s["nome"], s["copie"] - (int(s["etichetta"].split()[1].split("/")[0]) if s["azione"] == "parziale" else 0))
               for s in segni if s["azione"] in ("togli", "parziale") and s["nome"] not in BASI],
        terre=terre, non_viste=non_viste,
        nel_mazzo=sum(b["copie"] for b in lettura["mazzo"]))
    return segni, riepilogo


def testo_riepilogo(desc, rie):
    """Le righe del riquadro: chi e' il mazzo 1 e cosa resta da fare."""
    r = [f"{desc.get('nome') or 'MAZZO ' + str(desc.get('n') or 1)} · {desc['coppia']}{('+' + desc['splash']) if desc['splash'] else ''} · tier {desc['tier']} · "
         f"{desc['carte']} carte", f"A schermo nel mazzo: {rie['nel_mazzo']}"]
    if rie["aggiungi"]:
        r.append("AGGIUNGI dall'alto (verdi):")
        r += [f"  + {'' if q == 1 else f'{q} '}{n}" for n, q in rie["aggiungi"]]
    if rie["togli"]:
        r.append(f"TOGLI {sum(q for _, q in rie['togli'])} carte (rosse)")
    if rie["terre"]:
        r.append("TERRE:")
        r += [f"  {k} {ora} → {v}" for k, ora, v in rie["terre"]]
    if rie["non_viste"]:
        r.append("NON VISTE (scorri il mazzo):")
        r += [f"  {n}" for n in rie["non_viste"]]
    if not (rie["aggiungi"] or rie["togli"] or rie["terre"] or rie["non_viste"]):
        r.append("Il mazzo a schermo e' il mazzo 1.")
    return r


ATTESO_TOGLI = {"Artifist Acumen": 1, "Flourishing Grapple": 1, "Gallia, Tragic Host": 1, "Void Extrapolator": 1,
                "Tam's Resistance": 1, "Divining Duelist": 1, "Way of the Cryomancer": 1, "Sphinx's Approach": 1,
                "Break Under Pressure": 1, "Koth, the Geomancer": 1, "Rampart Hunter": 1,
                "Yargle, Goliath of Otaria": 1, "Apex Witchstalker": 1, "Undulating Witness": 1, "Awaken the Inferno": 1}
ATTESO_AGG = {("The Theorist, Jace Beleren", 1), ("Curse-Marred Demon", 1)}
MAZZI_CAMPIONE = os.path.join(QUI, "campioni", "mazzi_costruzione_20261102_2354.json")


def pool_campione():
    """Il pool del draft del campione, scritto qui: quello del Player.log e' dell'ultimo draft giocato, e le prove cambiavano col draft (6 nov 2026: rossa,
    51 carte su 53; 7 nov 2026: impronte.py rossa per lo stesso motivo, Arena ripartita senza draft). Lo usano tutte le prove sul campione."""
    _desc, voluto = mazzo_obiettivo(MAZZI_CAMPIONE)
    return {n: 4 for n in list(voluto) + list(ATTESO_TOGLI) + [n for n, _ in ATTESO_AGG]}


def prova():
    """Il caso vero del draft del 2 nov 2026 (QuickDraft_FRA_20261027), sul campione: il mazzo 1 UR vuole Jace Beleren e
    Curse-Marred Demon dall'alto e toglie 15 carte, 4 Swamp e 1 Forest; Island da 6 a 9, Mountain da 6 a 8 (la riga
    CLAUDE del diario delle 00:06:13 del 3 nov). Il json dei mazzi di quel draft e' copiato in campioni/."""
    sys.path.insert(0, QUI)
    import riconosci as R
    from ocr import Ocr
    from PIL import Image
    desc, voluto = mazzo_obiettivo(MAZZI_CAMPIONE)
    atteso_togli, atteso_agg = ATTESO_TOGLI, ATTESO_AGG
    atteso_terre = {("Forest", 1, 0), ("Island", 6, 9), ("Mountain", 6, 8), ("Swamp", 4, 0)}
    pool = pool_campione()
    with Ocr() as o:
        let = R.leggi_schermo(Image.open(R.CAMPIONE), o, R.Nomi(pool))
    segni, rie = decidi(let, voluto)
    ok = True
    for nome, ottenuto, atteso in (("togli", dict(rie["togli"]), atteso_togli), ("terre", set(rie["terre"]), atteso_terre),
                                   ("aggiungi", set(rie["aggiungi"]), atteso_agg), ("non viste", rie["non_viste"], []),
                                   ("carte nel mazzo", rie["nel_mazzo"], 53)):
        verde = ottenuto == atteso
        ok &= verde
        print(f"  {'VERDE' if verde else 'ROSSO'} {nome}: {ottenuto if not verde else 'come atteso'}"
              + ("" if verde else f" (atteso {atteso})"))
    # la prova negativa: lo stesso confronto con un mazzo 1 cambiato apposta deve dare rosso
    v2 = dict(voluto)
    v2["Divining Duelist"] = 1
    _s, rie2 = decidi(let, v2)
    neg = dict(rie2["togli"]) != atteso_togli
    print(f"  {'VERDE' if neg else 'ROSSO'} prova negativa (Divining Duelist voluto apposta): "
          + ("il confronto se ne accorge" if neg else "NON se ne accorge"))
    ok &= neg
    for riga in testo_riepilogo(desc, rie):
        print("    " + riga)
    print("PROVA " + ("VERDE" if ok else "ROSSA"))
    return ok


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    desc, voluto = mazzo_obiettivo()
    print(desc)
    for k, q in sorted(voluto.items()):
        print(f"  {q} {k}")
