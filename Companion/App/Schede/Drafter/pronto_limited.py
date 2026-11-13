"""Il pulsante Launch della sezione Play limited (Autore, 6 nov 2026: «quando nessun evento limited e' stato avviato, la sezione this draft deve essere: play limited e ci deve essere dentro un
pulsante launch, appena pronto la chat comunica che il companion limited e' pronto e si puo' scegliere e iscriversi a un evento, il companion poi capira' per quale evento stiamo giocando e si setta su
quel motore»). La finestra accende il companion se e' spento, poi lancia questo programma: guarda i draft aperti oggi sul calendario di Arena, prova per ognuno l'obbligo del drafter
(vivo.obbliga_valori, lo stesso del primo pick), rinfresca i valori se sono vecchi (aggiorna_vivo --valori, un minuto) e scrive una riga LIMITED nel diario: la chat la mostra anche con --solo-claude.
Il motore lo sceglie poi il companion dal nome dell'evento (Companion.nuovo_draft): qui non si fissa niente.

    py -I -X utf8 Companion/App/Schede/Drafter/pronto_limited.py --diario FILE    scrive la riga in quel diario
    py -I -X utf8 Companion/App/Schede/Drafter/pronto_limited.py                  la stampa soltanto
    py -I -X utf8 Companion/App/Schede/Drafter/pronto_limited.py --prova          i casi, con la prova negativa
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime, json, subprocess

import risorse as RS

ROOT = percorsi.ROOT
NOMI = dict(quick="Quick Draft", premier="Premier Draft")
FORMATI = ("quick", "premier")


def aperti(oggi, cal):
    """I draft aperti: [dict(k, set, nome, chiude)]."""
    out = []
    for k in FORMATI:
        x = RS._aperto(k, oggi, cal)
        if x:
            out.append(dict(k=k, set=x["set"], nome=cal.get(x["set"], {}).get("nome") or x["set"], chiude=x["chiude"]))
    return out


def motore_pronto(set_, formato):
    """-> None se il drafter parte su quel set e formato, se no il perche'."""
    import vivo
    try:
        valori = json.load(open(vivo._F, encoding="utf-8")).get("valori", {})
    except (OSError, ValueError):
        valori = {}
    for k, v in valori.items():
        os.environ.setdefault(k, str(v))
    os.environ["MAGIC_FORMATO"], os.environ["MAGIC_SET"] = formato, set_
    try:
        m = vivo.obbliga_valori(set_, formato, ferma=False)
    except Exception as e:      # un set senza quaderno leggibile: non e' pronto, e lo si dice
        return f"{type(e).__name__}: {e}"
    return m if m.startswith("⛔") else None


def giudica(voci, prova):
    """Aggiunge a ogni voce «no», il perche' se il motore non e' pronto."""
    for v in voci:
        v["no"] = prova(v["set"], v["k"])
    return voci


def vecchi(voci):
    """Valori vecchi: si rimettono a posto da soli con aggiorna_vivo --valori. Un set senza progetto o senza quaderno no."""
    return any(v["no"] and "aggiorna_vivo.py --valori" in v["no"] for v in voci)


def riga(voci):
    """La riga LIMITED: «titolo | voce | voce», come le righe di Claude."""
    pronte = [v for v in voci if not v["no"]]
    giorno = lambda d: f"{datetime.date.fromisoformat(d).day} {datetime.date.fromisoformat(d):%b}"
    testi = [f"{NOMI[v['k']]} · {v['nome']} ({v['set']}) · until {giorno(v['chiude'])}" + (": no engine for this event yet" if v["no"] else "") for v in voci]
    if pronte:
        return "LIMITED: Limited companion ready | " + " | ".join(testi) + " | Pick an event in Arena and join it: the companion reads it and sets itself on that engine"
    if voci:
        return "LIMITED: Limited companion not ready | " + " | ".join(testi)
    return "LIMITED: Limited companion ready | No draft on the calendar today | Join any limited event in Arena: the companion reads it and sets itself on that engine"


def scrivi(testo, diario=None):
    print(testo, flush=True)
    if diario:
        with open(diario, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"{datetime.datetime.now():%H:%M:%S} {testo}\n")


def main():
    if "--prova" in sys.argv:
        return prova()
    diario = sys.argv[sys.argv.index("--diario") + 1] if "--diario" in sys.argv else None
    cal = RS._calendario()
    voci = giudica(aperti(datetime.date.today(), cal), motore_pronto)
    if vecchi(voci):            # lo stesso comando che il drafter stampa quando si rifiuta di partire
        subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(ROOT, "Motore", "aggiorna_vivo.py"), "--valori"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        voci = giudica(voci, motore_pronto)
    scrivi(riga(voci), diario)
    return 0


def prova():
    d = datetime.date(2026, 11, 8)
    cal = {"AAA": {"nome": "Set A", "quick": [["2026-11-01", "2026-11-09"]], "premier": [["2026-11-01", "2026-12-01"]]}, "BBB": {"nome": "Set B", "quick": [["2026-11-20", "2026-11-25"]]}}
    casi = []
    v = aperti(d, cal)
    casi.append(("due draft aperti", [(x["k"], x["set"], x["chiude"]) for x in v] == [("quick", "AAA", "2026-11-09"), ("premier", "AAA", "2026-12-01")]))
    casi.append(("niente fuori finestra", aperti(datetime.date(2026, 10, 1), cal) == []))
    r = riga(giudica(aperti(d, cal), lambda s, f: None))
    casi.append(("pronto", r.startswith("LIMITED: Limited companion ready | Quick Draft · Set A (AAA) · until 9 Nov | Premier Draft") and "no engine" not in r))
    r = riga(giudica(aperti(d, cal), lambda s, f: "⛔ manca" if f == "quick" else None))
    casi.append(("un motore manca e si dice", "ready" in r.split(" | ")[0] and "Quick Draft · Set A (AAA) · until 9 Nov: no engine" in r and "Premier Draft · Set A (AAA) · until 1 Dec |" in r))
    r = riga(giudica(aperti(d, cal), lambda s, f: "⛔ manca"))
    casi.append(("nessun motore: non e' pronto", r.startswith("LIMITED: Limited companion not ready") and "Pick an event" not in r))
    casi.append(("calendario vuoto: si puo' giocare lo stesso", "No draft on the calendar" in riga([])))
    casi.append(("i valori vecchi si rinfrescano", vecchi([dict(no="⛔ il drafter non parte: GIH vecchio. Lancia: py -I -X utf8 Motore/aggiorna_vivo.py --valori   (un minuto)")])))
    casi.append(("un set senza progetto no", not vecchi([dict(no="⛔ il drafter non parte. Lancia: py -I -X utf8 Companion/progetto.py --nuovo X")])))
    # il vero: FRA e' aperto, quindi il suo motore deve dire qualcosa di leggibile; la prova negativa: un set che non esiste non e' mai pronto
    casi.append(("prova negativa: un set inesistente non e' pronto", motore_pronto("ZZZ", "quick") is not None))
    ok = True
    for n, x in casi:
        print(("  ok " if x else "  ROSSO ") + n)
        ok = ok and x
    print("verde" if ok else "ROSSO")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
