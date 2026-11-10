"""Il calendario degli eventi limited di Arena, letto dalla pagina ufficiale di Wizards (Autore, 6 nov 2026: «spostiamo da performance a drafter il calendario degli eventi limited e li
mettiamo tutti e sempre aggiornati dal sito originale, incolonnati per titolo e start end con i giorni rimasti per capire quanto si puo' ancora giocarli»).

La pagina «<set>-event-schedule» ha la sezione «Full Event Calendar»: un titolo per formato e sotto una riga per periodo, «November 7–18: Bloomburrow». Si tengono i formati limited, si butta il
constructed, e si scrive Regole/calendario_eventi.json. La finestra lo legge e lo rifa' in sottofondo se ha piu' di 24 ore: se la pagina non risponde o non si legge resta il file di prima.
La pagina cambia a ogni set: PAGINE dice dove guardare, si prova la prima che risponde e ha eventi futuri. Un set nuovo vuole la sua riga, e la finestra lo dice quando il calendario finisce.
Regole/calendario_set.json resta quello del drafter e del Farmer: e' scritto a mano, set per set.

    py -I -X utf8 Companion/App/Schede/Drafter/calendario_eventi.py           scarica e scrive
    py -I -X utf8 Companion/App/Schede/Drafter/calendario_eventi.py --prova   i casi, con la prova negativa
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime, html, json, re, ssl, urllib.request

PAGINE = ("https://magic.wizards.com/en/news/mtg-arena/star-trek-event-schedule",)
FILE = os.path.join(percorsi.ROOT, "Regole", "calendario_eventi.json")
FILE_ESCLUSI = os.path.join(percorsi.ROOT, "Log_Arena", "calendario_esclusi.json")
ALTRO = "Special events"
MESI = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
LIMITED = ("Premier Draft", "Flashback Premier Draft", "Pick-Two Draft", "Traditional Draft", "Quick Draft", "Sealed and Traditional Sealed", "Cube", "Contender Draft", "Arena Direct")
ALTRI = ("Metagame Challenge", "Midweek Magic", "Arena Championship Qualifier Events", "Arena Limited Championship Events", "Other Events")
RX_DATA = re.compile(r"^(" + "|".join(MESI) + r") (\d{1,2})(?:[–-](?:(" + "|".join(MESI) + r") )?(\d{1,2}))?: *(.*)$")
RX_LIMITED_IN_ALTRI = re.compile(r"Draft|Sealed|Cube|Limited Championship", re.I)


def pulisci(t):
    """Il nome del set senza marchi e senza il prefisso di Universes Beyond."""
    t = re.sub(r"\s+", " ", t.replace("®", "").replace("™", "")).strip()
    t = re.sub(r"Magic: The Gathering ?(\| ?|— ?)", "", t)
    return t.strip(" ·-")


def testo_pagina(pagina):
    x = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", pagina)
    x = html.unescape(re.sub(r"<[^>]+>", "\n", x))
    return [r.strip() for r in x.split("\n") if r.strip()]


def data(mese, giorno, oggi):
    """L'anno non e' scritto: la data piu' vicina a oggi, una pagina non parla di piu' di qualche mese."""
    d = datetime.date(oggi.year, MESI.index(mese) + 1, int(giorno))
    if (d - oggi).days < -183:
        d = d.replace(year=oggi.year + 1)
    elif (d - oggi).days > 183:
        d = d.replace(year=oggi.year - 1)
    return d


def leggi(pagina, oggi):
    """Dal testo della pagina: [dict(tipo, titolo, inizio, fine)]."""
    r = testo_pagina(pagina)
    if "Full Event Calendar" not in r:
        return []
    r = r[r.index("Full Event Calendar") + 1:]
    fine_pag = next((i for i, x in enumerate(r) if x in ("MTG Arena", "Magic: The Gathering Footer")), len(r))
    r = r[:fine_pag]
    voci, tipo, corrente = [], None, None
    for x in r:
        if x in LIMITED or x in ALTRI:
            tipo, corrente = x, None
            continue
        m = RX_DATA.match(x)
        if m and tipo:
            mese_a, gg_a, mese_b, gg_b, resto = m.groups()
            a = data(mese_a, gg_a, oggi)
            b = data(mese_b or mese_a, gg_b or gg_a, oggi)
            corrente = dict(tipo=tipo, titolo=resto, inizio=a.isoformat(), fine=b.isoformat())
            voci.append(corrente)
        elif corrente is not None:
            corrente["titolo"] += " " + x
    out = []
    for v in voci:
        t = pulisci(v["titolo"])
        tipo = v["tipo"]
        if tipo == "Arena Championship Qualifier Events":      # i qualificatori hanno un formato per mese, spesso constructed: non sono un evento da scegliere
            continue
        if tipo == "Sealed and Traditional Sealed":
            tipo = "Traditional Sealed" if t.endswith("Traditional Sealed") else "Sealed"
            t = re.sub(r" ?(Traditional )?Sealed$", "", t)
        if tipo in ALTRI:
            if not RX_LIMITED_IN_ALTRI.search(t):     # fra gli altri eventi si tengono solo quelli limited
                continue
            tipo, t = t, ""
        elif tipo == "Arena Direct":
            t = re.sub(r"^Arena Direct:? ?(for )?", "", t)
        out.append(dict(v, tipo=tipo, titolo=t))
    return out


def scarica(url):
    import certifi
    c = ssl.create_default_context(cafile=certifi.where())
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), context=c, timeout=30).read().decode("utf-8", "ignore")


def carica():
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def unisci(voci, oggi):
    """La pagina del set nuovo parte dal suo primo giorno: quel che e' aperto gia' adesso viene dal calendario dei set (Regole/calendario_set.json). Il Premier di Reality Fracture la pagina lo dice dal
    10 nov, ed e' aperto dal 29 set; il Quick che chiude oggi non c'e' proprio."""
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "calendario_set.json"), encoding="utf-8") as f:
            cal = json.load(f)["set"]
    except (OSError, ValueError, KeyError):
        return voci
    for s_ in cal.values():
        for k, tipo in (("quick", "Quick Draft"), ("premier", "Premier Draft")):
            for a, b in s_.get(k) or []:
                if b < oggi.isoformat():
                    continue
                gemella = next((v for v in voci if v["tipo"] == tipo and v["titolo"] == s_.get("nome") and v["fine"] == b), None)
                if gemella:
                    gemella["inizio"] = min(gemella["inizio"], a)
                elif a <= oggi.isoformat():
                    voci.append(dict(tipo=tipo, titolo=s_.get("nome"), inizio=a, fine=b))
    return voci


def aggiorna(oggi=None):
    """Riscarica. -> True se ha scritto il file; se niente si legge, il file di prima resta."""
    oggi = oggi or datetime.date.today()
    for url in PAGINE:
        try:
            voci = leggi(scarica(url), oggi)
        except Exception as e:
            print("calendario eventi:", url, type(e).__name__, e)
            continue
        if len(voci) >= 5 and any(v["fine"] >= oggi.isoformat() for v in voci):
            voci = unisci(voci, oggi)
            with open(FILE, "w", encoding="utf-8") as f:
                json.dump(dict(fonte=url, letto=datetime.datetime.now().isoformat(timespec="minutes"), eventi=voci), f, ensure_ascii=False, indent=1)
            return True
    return False


def tipi(rr):
    """Le voci della tendina: i tipi degli eventi nell'ordine della pagina, gli eventi senza un tipo loro in fondo."""
    noti = ["Quick Draft", "Premier Draft", "Flashback Premier Draft", "Traditional Draft", "Pick-Two Draft", "Sealed", "Traditional Sealed", "Contender Draft", "Cube", "Arena Direct"]
    presenti = {r["tipo"] for r in rr}
    return [t for t in noti if t in presenti] + sorted(presenti - set(noti) - {ALTRO}) + ([ALTRO] if ALTRO in presenti else [])


def leggi_esclusi():
    """I tipi che hai tolto dal calendario. Si tiene chi hai tolto e non chi hai scelto: un tipo nuovo della pagina si vede."""
    try:
        with open(FILE_ESCLUSI, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError, TypeError):
        return set()


def salva_esclusi(esclusi):
    with open(FILE_ESCLUSI, "w", encoding="utf-8") as f:
        json.dump(sorted(esclusi), f)


def righe(cal, oggi=None):
    """Quel che la finestra mostra: gli eventi non finiti, prima quelli aperti dal piu' vicino a chiudere, poi i prossimi dal piu' vicino ad aprire.
    -> [dict(nome, inizio, fine, aperto, giorni)]; giorni: quanti ne restano se e' aperto, oggi compreso; fra quanti apre se no."""
    oggi = oggi or datetime.date.today()
    out = []
    for v in (cal or {}).get("eventi") or []:
        a, b = datetime.date.fromisoformat(v["inizio"]), datetime.date.fromisoformat(v["fine"])
        if b < oggi:
            continue
        aperto = a <= oggi
        out.append(dict(tipo=v["tipo"] if v["titolo"] else ALTRO, nome=v["tipo"] + (" · " + v["titolo"] if v["titolo"] else ""), inizio=a, fine=b, aperto=aperto, giorni=(b - oggi).days + 1 if aperto else (a - oggi).days))
    return sorted(out, key=lambda x: (not x["aperto"], x["fine"] if x["aperto"] else x["inizio"], x["nome"]))


def prova():
    prova_pag = """<h2>Full Event Calendar</h2><h3>Premier Draft</h3><p><b>November 10–February 2: </b><em>Magic: The Gathering</em> | <em>Star Trek</em></p><p><b>November 10–December 2:</b> <em>Reality Fracture</em></p>
    <h3>Flashback Premier Draft</h3><p>November 23–30: <em>Shadows over Innistrad Remastered</em> (Abominable All-Stars)</p><h3>Quick Draft</h3><p>November 7–18: <em>Bloomburrow</em></p><p>January 30–February 10: <em>Edge of Eternities</em></p>
    <h3>Sealed and Traditional Sealed</h3><p>November 10–24: <em>Magic: The Gathering</em> | <em>Star Trek</em> Traditional Sealed</p><h3>Arena Direct</h3><p>December 25–27: Arena Direct: <em>Arena Powered Cube</em> Draft for <em>Magic: The Gathering</em> | <em>Star Trek</em> Play Booster boxes</p>
    <h3>Midweek Magic</h3><p>December 1–2: Interstellar Standard</p><p>January 26–27: Golden Pack Sealed</p><h3>Arena Championship Qualifier Events</h3><p>January 16: Best-of-One Qualifier Play-In</p><p>January 17: Sealed Bonus</p><h3>Other Events</h3><p>December 11–25: All-Access Standard Rampage</p><p>January 12–February 2: Mixed-Up Premier Draft</p><div>MTG Arena</div><p>December 30–31: finto</p>"""
    o = datetime.date(2026, 11, 6)
    v = leggi(prova_pag, o)
    nomi = [(x["tipo"], x["titolo"], x["inizio"], x["fine"]) for x in v]
    casi = [("il set di Universes Beyond senza prefisso", nomi[0] == ("Premier Draft", "Star Trek", "2026-11-10", "2027-02-02")),
            ("il periodo a cavallo dell'anno", ("Quick Draft", "Edge of Eternities", "2027-01-30", "2027-02-10") in nomi),
            ("il titolo su piu' pezzi", ("Flashback Premier Draft", "Shadows over Innistrad Remastered (Abominable All-Stars)", "2026-11-23", "2026-11-30") in nomi),
            ("il sealed tradizionale ha il suo tipo", ("Traditional Sealed", "Star Trek", "2026-11-10", "2026-11-24") in nomi),
            ("fra gli altri eventi solo i limited", ("Golden Pack Sealed", "", "2027-01-26", "2027-01-27") in nomi and ("Mixed-Up Premier Draft", "", "2027-01-12", "2027-02-02") in nomi and not any("Rampage" in x[0] or "Interstellar" in x[0] or "Bonus" in x[0] for x in nomi)),
            ("niente dopo la fine della sezione", not any("finto" in x[1] for x in nomi))]
    r = righe(dict(eventi=[dict(tipo="Quick Draft", titolo="A", inizio="2026-11-01", fine="2026-11-06"), dict(tipo="Quick Draft", titolo="B", inizio="2026-11-07", fine="2026-11-18"),
                           dict(tipo="Premier Draft", titolo="C", inizio="2026-10-01", fine="2026-12-02"), dict(tipo="Cube", titolo="", inizio="2026-10-01", fine="2026-11-05")]), o)
    casi.append(("aperti prima, chi chiude prima, poi i prossimi; il finito no", [x["nome"] for x in r] == ["Quick Draft · A", "Premier Draft · C", "Quick Draft · B"]))
    casi.append(("l'ultimo giorno vale 1, il prossimo dice fra quanto", r[0]["giorni"] == 1 and r[2]["giorni"] == 1 and not r[2]["aperto"]))
    fi = unisci([dict(tipo="Premier Draft", titolo="Reality Fracture", inizio="2026-11-10", fine="2026-12-02")], o)
    casi.append(("il calendario dei set: chi e' gia' aperto parte dal suo giorno", any(v["tipo"] == "Premier Draft" and v["titolo"] == "Reality Fracture" and v["inizio"] == "2026-09-29" for v in fi) and any(v["tipo"] == "Quick Draft" and v["titolo"] == "Reality Fracture" and v["fine"] == "2026-11-06" for v in fi)))
    tt = tipi(righe(dict(eventi=[dict(tipo="Cube", titolo="A", inizio="2026-11-01", fine="2026-12-06"), dict(tipo="Quick Draft", titolo="B", inizio="2026-11-07", fine="2026-11-18"), dict(tipo="Golden Pack Sealed", titolo="", inizio="2026-11-07", fine="2026-11-18")]), o))
    casi.append(("la tendina: i tipi in ordine, gli speciali in fondo", tt == ["Quick Draft", "Cube", ALTRO]))
    casi.append(("prova negativa: una pagina senza calendario non da' eventi", leggi("<p>November 7–18: Bloomburrow</p>", o) == []))
    ok = True
    for n, x in casi:
        print(("  ok " if x else "  ROSSO ") + n)
        ok = ok and x
    print("verde" if ok else "ROSSO")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
    fatto = aggiorna()
    c = carica()
    print("scritto" if fatto else "non aggiornato", len((c or {}).get("eventi") or []), "eventi,", (c or {}).get("letto"))
    sys.exit(0 if fatto else 1)
