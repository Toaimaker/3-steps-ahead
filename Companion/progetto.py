"""Il progetto del draft: set e formato aprono una cartella, e il drafter carica e salva solo dove il progetto dice.

Autore, 16 ott 2026 sera: «creare nelle cartelle dei formati dei file specifici sui quali il motore di draft si setta prima
di andare a fare quick o piuttosto premier o sealed per avere i dati esatti prima di cominciare... come quando setto Maya nella
cartella di progetto esatta tramite il file del sistema di cartelle» e «ogni formato potrebbe avere i dati di pick sempre
linkati e quindi aggiornati alle fonti». Disegno: Note/HANDOFF_Espansioni_Cartella_Unica.md §1.bis.

    Espansioni/<SET>/Comune/     testi delle carte (Scryfall), schede, quaderno: uguali in ogni formato
    Espansioni/<SET>/Quick/      progetto.json, fonti.json, voti del Quick (copie datate), valori, mazzi perfetti, trofei,
                                 Untapped (statistiche, ruote dei bot, modelli della citta')
    Espansioni/<SET>/Premier/    progetto.json, fonti.json, voti del Premier (copie datate), mazzi perfetti del Premier e le
                                 misure fatte sui pool veri (win condition, voto dei mazzi, motori, coppie, sinergie):
                                 valgono anche per il Quick, che le legge da qui
    Espansioni/<SET>/Sealed/     (quando ci sono i dati: --nuovo X --sealed) progetto.json e fonti.json del Sealed, per il
                                 costruttore del mazzo: niente pick, quindi niente pack, citta' e ruote. L'evento su Arena e'
                                 Sealed_<SET>_<data> (vivo.formato_da_evento). Il modello: Espansioni/_modello/Sealed/
    Espansioni/<SET>/grezzi/     i file grossi di 17Lands (S3, pack del predittivo, citta', cartelle di lavoro), fuori da git

progetto.json e' il workspace.mel di Maya: a ogni chiave il percorso, relativo alla cartella del formato. Il Companion vede
QuickDraft_DFT_... nel Player.log, scrive MAGIC_SET=DFT e MAGIC_FORMATO=quick, e chi legge un file del set lo chiede qui:

    import progetto as PR
    PR.file("anagrafe")                              # set e formato attivi (percorsi.set_attivo(), MAGIC_FORMATO)
    PR.file("win_condition", "DFT")                  # un altro set, formato attivo
    PR.file("valori", "FRA", variante="quick2")      # le chiavi con un {segnaposto} lo vogliono per nome
    PR.ultimo("voti_17lands", "FRA", "quick")        # l'ultima copia datata ({data}), o None
    PR.file("voti_17lands", "FRA", "quick", data="2026-10-16")   # dove salvare la copia di oggi

Un valore puo' essere una lista: vale il primo percorso che esiste, se no il primo (e' li' che si scrive). I mazzi perfetti
del Premier, per esempio, cercano anche nel Quick quelli che non dipendono dal formato.
fonti.json tiene i link delle fonti del formato: il giro li segue ogni giorno e salva una copia datata nella cartella; la data
dell'ultimo scarico e' quella dell'ultima copia. Un set nuovo si apre da Espansioni/_modello/ (--nuovo X), senza codice.

    py -I -X utf8 Companion/progetto.py --prova            ogni chiave di FRA e DFT, Quick e Premier, trova il suo file;
                                                           il modello Sealed e un set aperto per prova in una cartella temporanea
    py -I -X utf8 Companion/progetto.py --set DFT --formato quick    il controllo prima del primo pick, a mano
    py -I -X utf8 Companion/progetto.py --nuovo XYZ        apre Espansioni/XYZ/ dal modello (Comune, Quick, Premier)
    py -I -X utf8 Companion/progetto.py --nuovo XYZ --sealed     aggiunge Sealed/ (anche a un set gia' aperto)
"""
import glob
import json
import os
import re
import shutil
import sys


def _radice():
    d = os.path.dirname(os.path.abspath(__file__))
    while not os.path.isfile(os.path.join(d, "PUBBLICA.txt")):
        su = os.path.dirname(d)
        if su == d:
            raise RuntimeError("progetto: nessuna cartella con CLAUDE.md sopra " + __file__)
        d = su
    return d


def _set_attivo():
    """Il set dell'evento da percorsi.set_attivo(). Si importa solo qui: chi passa il set (Motore_Partita, che ha moduli
    con lo stesso nome di quelli del Companion, come tavolo.py) carica questo modulo senza toccare il sys.path."""
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import percorsi
    return percorsi.set_attivo()


ROOT = _radice()
ESPANSIONI = os.path.join(ROOT, "Espansioni")
MODELLO = os.path.join(ESPANSIONI, "_modello")
CARTELLA = {"quick": "Quick", "premier": "Premier", "sealed": "Sealed"}
# Il lucchetto del giro automatico (Motore/aggiorna_vivo.py): uno per tutti i set, perche' il giro e' uno solo e rifa' ogni
# set del drafter. Fino al 16 ott 2026 stava in Espansioni/FRA/grezzi/draft/giro_vivo.lock, come se il giro fosse di FRA.
# E' una cartella vuota (mkdir e' atomico): git non la vede.
LUCCHETTO_GIRO = os.path.join(ESPANSIONI, "giro_vivo.lock")
_APERTI = {}


def formato_attivo(predefinito="quick"):
    """Il formato del draft: --formato negli argomenti, poi MAGIC_FORMATO (lo scrive chi legge il Player.log), poi quick."""
    a = sys.argv
    if "--formato" in a and a.index("--formato") + 1 < len(a):
        return a[a.index("--formato") + 1].lower()
    return (os.environ.get("MAGIC_FORMATO") or predefinito).lower()


def cartella(set_=None, formato=None):
    s = (set_ or _set_attivo()).upper()
    f = (formato or formato_attivo()).lower()
    if f not in CARTELLA:
        raise ValueError(f"progetto: formato «{f}» sconosciuto (quick, premier, sealed)")
    return os.path.join(ESPANSIONI, s, CARTELLA[f])


def esiste(set_=None, formato=None):
    return os.path.isfile(os.path.join(cartella(set_, formato), "progetto.json"))


def apri(set_=None, formato=None):
    """Il progetto del set e del formato: {set, formato, dir, file: {chiave: valore}, obbligatori, ...}."""
    d = cartella(set_, formato)
    if d not in _APERTI:
        p = os.path.join(d, "progetto.json")
        if os.path.isfile(p):
            pj = json.load(open(p, encoding="utf-8"))
        else:
            # un set senza progetto (un evento mai visto, un set di studio): i percorsi del modello, che non esistono
            # ancora. Chi controlla se un file c'e' trova «no», come prima; il controllo prima del pick lo dice rosso.
            s = os.path.basename(os.path.dirname(d))
            m = os.path.join(MODELLO, os.path.basename(d), "progetto.json")
            pj = json.loads(open(m, encoding="utf-8").read().replace("{SET}", s).replace("{set}", s.lower()))
            pj["dal_modello"] = True
        pj["dir"] = d
        _APERTI[d] = pj
    return _APERTI[d]


def _forma(v, kw, chiave):
    try:
        return v.format(**kw)
    except KeyError as e:
        raise KeyError(f"progetto: la chiave «{chiave}» vuole il segnaposto {e} ({v})") from None


def candidati(chiave, set_=None, formato=None, **kw):
    """I percorsi interi che il progetto dichiara per la chiave, nell'ordine."""
    pj = apri(set_, formato)
    if chiave not in pj["file"]:
        raise KeyError(f"progetto: la chiave «{chiave}» non c'e' in {os.path.relpath(pj['dir'], ROOT)}/progetto.json")
    v = pj["file"][chiave]
    return [os.path.normpath(os.path.join(pj["dir"], _forma(x, kw, chiave))) for x in (v if isinstance(v, list) else [v])]


def file(chiave, set_=None, formato=None, **kw):
    """Il percorso del file (o della cartella) della chiave: il primo candidato che esiste, se no il primo."""
    cc = candidati(chiave, set_, formato, **kw)
    for c in cc:
        if os.path.exists(c):
            return c
    return cc[0]


def copie(chiave, set_=None, formato=None):
    """Le copie datate di una chiave col segnaposto {data}, dalla piu' vecchia alla piu' nuova (per nome)."""
    out = []
    for c in candidati(chiave, set_, formato, data="*"):
        out += glob.glob(c)
    return sorted(set(out), key=os.path.basename)


def ultimo(chiave, set_=None, formato=None):
    cc = copie(chiave, set_, formato)
    return cc[-1] if cc else None


def fonte(chiave, set_=None, formato=None):
    """Il link della fonte (fonti.json del formato)."""
    d = cartella(set_, formato)
    f = json.load(open(os.path.join(d, "fonti.json"), encoding="utf-8"))
    if chiave not in f["link"]:
        raise KeyError(f"progetto: la fonte «{chiave}» non c'e' in {os.path.relpath(d, ROOT)}/fonti.json")
    return f["link"][chiave]


def carte_per_pack(s):
    """Quante carte ha un pack del set: 14 di norma, 13 in Lorwyn Eclipsed e Edge of Eternities (draft data di 17Lands, 5 nov
    2026). Lo scrive Motore/apri_set.py in Comune/pack.json; senza il file vale 14, come FRA e DFT."""
    try:
        return int(json.load(open(os.path.join(ESPANSIONI, s.upper(), "Comune", "pack.json"), encoding="utf-8"))["carte"])
    except (OSError, ValueError, KeyError):
        return 14


def set_aperti():
    """I set con un progetto (Espansioni/<SET>/Quick/progetto.json), in ordine."""
    return sorted(os.path.basename(os.path.dirname(os.path.dirname(p)))
                  for p in glob.glob(os.path.join(ESPANSIONI, "*", "Quick", "progetto.json"))
                  if not os.path.basename(os.path.dirname(os.path.dirname(p))).startswith("_"))


def game_data(s):
    """Il game data del Premier di S3 di un set. I set col progetto lo tengono in Espansioni/<SET>/grezzi/; i set vecchi
    studiati solo per le misure (rimozioni, trucchi, fonti di mana: ECL, HOB, MSH, SOS, TLA, TMT) non hanno un progetto
    e il loro restano in Dati/17lands/game_<SET>/."""
    if esiste(s, "premier"):
        return file("s3_game", s, "premier")
    return os.path.join(ROOT, "Dati", "17lands", f"game_{s}", f"game_data_public.{s}.PremierDraft.csv.gz")


def controlla(set_=None, formato=None):
    """Il controllo prima del primo pick (come Maya quando non trova il progetto): il progetto c'e', e ogni file che il
    progetto dice obbligatorio c'e'. -> lista di righe che non vanno (vuota = verde). La freschezza dei voti la guarda
    vivo.obbliga_valori sulle date che il quaderno scrive (30 ore)."""
    s = (set_ or _set_attivo()).upper()
    f = (formato or formato_attivo()).lower()
    try:
        pj = apri(s, f)
    except (FileNotFoundError, ValueError) as e:
        return [str(e)]
    if pj.get("dal_modello"):
        return [f"manca il progetto {os.path.relpath(os.path.join(pj['dir'], 'progetto.json'), ROOT)} "
                + (f"(il Sealed, coi suoi dati: py -I -X utf8 Companion/progetto.py --nuovo {s} --sealed)" if f == "sealed" else
                   f"(un set nuovo: py -I -X utf8 Companion/progetto.py --nuovo {s})")]
    no = []
    for k in pj.get("obbligatori", []):
        try:
            if "{data}" in json.dumps(pj["file"].get(k, "")):
                ok = bool(copie(k, s, f))
                p = candidati(k, s, f, data="<data>")[0]
            else:
                p = file(k, s, f)
                ok = os.path.exists(p)
        except KeyError as e:
            no.append(str(e)); continue
        if not ok:
            no.append(f"manca {os.path.relpath(p, ROOT)} («{k}» del progetto {s} {CARTELLA[f]})")
    return no


# ------------------------------------------------------------------ un set nuovo, dal modello
def nuovo(s, sealed=False):
    """Apre Espansioni/<s>/ dal modello. Il Sealed solo se chiesto (sealed=True, --sealed): un progetto Sealed senza i dati
    del Sealed sarebbe un progetto vuoto (16 ott 2026: FRA e DFT non lo hanno). Un file che c'e' gia' non si tocca, quindi
    --sealed su un set aperto aggiunge solo Sealed/."""
    s = s.upper()
    dest = os.path.join(ESPANSIONI, s)
    for sotto in ("Comune", "Quick", "Premier", "grezzi") + (("Sealed",) if sealed else ()):
        os.makedirs(os.path.join(dest, sotto), exist_ok=True)
    for dirpath, _, nomi in os.walk(MODELLO):
        if not sealed and os.path.relpath(dirpath, MODELLO).split(os.sep)[0] == "Sealed":
            continue
        for n in nomi:
            src = os.path.join(dirpath, n)
            out = os.path.join(dest, os.path.relpath(src, MODELLO))
            if os.path.exists(out):
                print(f"c'e' gia': {os.path.relpath(out, ROOT)}"); continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if n.endswith((".json", ".md")):
                t = open(src, encoding="utf-8").read().replace("{SET}", s).replace("{set}", s.lower())
                open(out, "w", encoding="utf-8").write(t)
            else:
                shutil.copy2(src, out)
            print(f"scritto {os.path.relpath(out, ROOT)}")
    print(f"Ora lo scarico, in ordine: CLAUDE.md, «I set del drafter» (anagrafe_carte.py --set {s}, poi S3 e il resto).")


# ------------------------------------------------------------------ la prova
_ESEMPI = {"variante": "*", "data": "*", "meta": "*"}   # nella prova un segnaposto vale qualunque file


def prova():
    """Ogni chiave di FRA e DFT, Quick e Premier, trova il suo file; gli obbligatori ci sono; una chiave sbagliata e un
    progetto che non c'e' sono rossi. Esce 1 se qualcosa non va."""
    rossi, righe = [], []
    for s in ("FRA", "DFT"):
        for f in ("quick", "premier"):
            pj = apri(s, f)
            manca = []
            for k, v in pj["file"].items():
                kw = {x: _ESEMPI.get(x, "*") for x in re.findall(r"\{(\w+)\}", json.dumps(v))}
                cc = [c for c in candidati(k, s, f, **kw)]
                if not any(glob.glob(c) for c in cc):
                    manca.append(k)
                if any(not os.path.normpath(c).startswith(os.path.join(ESPANSIONI, s)) for c in cc):
                    rossi.append(f"{s} {f}: «{k}» punta fuori da Espansioni/{s}/ ({cc[0]})")
            no = controlla(s, f)
            rossi += [f"{s} {f}: {x}" for x in no]
            righe.append(f"{s} {CARTELLA[f]:<8} {len(pj['file'])} chiavi, obbligatori {'verdi' if not no else 'ROSSI'}"
                         + (f"; senza file (facoltativi, non ancora calcolati per {s}): {', '.join(manca)}" if manca else ""))
    try:
        file("chiave_che_non_esiste", "FRA", "quick")
        rossi.append("una chiave sbagliata non da' errore")
    except KeyError:
        righe.append("chiave sbagliata -> errore: ok")
    if not controlla("ZZZ", "quick"):
        rossi.append("un progetto che non c'e' non e' rosso")
    else:
        righe.append("progetto mancante -> rosso: ok")
    if set_aperti()[:2] != ["DFT", "FRA"] and sorted(set_aperti()) != sorted(set(set_aperti())):
        rossi.append(f"set aperti strani: {set_aperti()}")
    righe.append(f"set col progetto: {', '.join(set_aperti())}")
    rossi += prova_sealed(righe)
    print("\n".join(righe))
    for r in rossi:
        print("ROSSO " + r)
    print("verde" if not rossi else f"{len(rossi)} rossi")
    return 1 if rossi else 0


PICK = ("predittivo", "citta", "ruote", "modelli_bot", "cartella_draft", "s3_draft", "lavoro_giro", "lavoro_banco_citta",
        "lavoro_rigioca", "lavoro_banco_apertura", "mazzo_perfetto")   # chiavi del draft, che il Sealed non ha


def prova_sealed(righe):
    """Il Sealed (16 ott 2026, sessione Magic 04): il modello si apre, non ha chiavi del pick, ogni chiave resta dentro
    l'espansione, ogni copia di fonti.json ha la sua chiave; un set senza Sealed e' rosso al controllo; --nuovo X apre
    Sealed solo con --sealed (in una cartella temporanea, Espansioni/ non si tocca); il nome dell'evento."""
    global ESPANSIONI
    import tempfile
    rossi = []
    m = json.load(open(os.path.join(MODELLO, "Sealed", "progetto.json"), encoding="utf-8"))
    fo = json.load(open(os.path.join(MODELLO, "Sealed", "fonti.json"), encoding="utf-8"))
    rossi += [f"Sealed: il modello ha la chiave del pick «{k}»" for k in PICK if k in m["file"]]
    rossi += [f"Sealed: fonti.json copia «{k}» in «{v}», che progetto.json non ha" for k, v in fo["copia"].items() if v not in m["file"]]
    rossi += [f"Sealed: fonti.json copia «{k}», che non ha un link" for k in fo["copia"] if k not in fo["link"]]
    rossi += [f"Sealed: obbligatorio «{k}» senza chiave" for k in m["obbligatori"] if k not in m["file"]]
    for s in ("FRA", "DFT"):
        no = controlla(s, "sealed")
        if esiste(s, "sealed"):
            righe.append(f"{s} Sealed   progetto aperto, obbligatori {'verdi' if not no else 'ROSSI: ' + '; '.join(no)}")
        elif not (no and "manca il progetto" in no[0]):
            rossi.append(f"{s} sealed: un set senza progetto Sealed non e' rosso ({no})")
        else:
            righe.append(f"{s} Sealed   nessun progetto (nessun dato del Sealed scaricato): rosso al controllo, come deve")
    vera, aperti = ESPANSIONI, dict(_APERTI)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            ESPANSIONI = tmp
            _APERTI.clear()
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                nuovo("ZZQ")
            if os.path.exists(os.path.join(tmp, "ZZQ", "Sealed")):
                rossi.append("--nuovo senza --sealed apre anche Sealed/")
            with contextlib.redirect_stdout(io.StringIO()):
                nuovo("ZZQ", sealed=True)
            pj = apri("ZZQ", "sealed")
            if pj.get("dal_modello") or pj["set"] != "ZZQ":
                rossi.append("--nuovo --sealed non apre il progetto Sealed")
            for k, v in pj["file"].items():
                kw = {x: "*" for x in re.findall(r"\{(\w+)\}", json.dumps(v))}
                for c in candidati(k, "ZZQ", "sealed", **kw):
                    if not os.path.normpath(c).startswith(os.path.join(tmp, "ZZQ")):
                        rossi.append(f"Sealed: «{k}» punta fuori dall'espansione ({c})")
            if "ZZQ" not in fonte("17lands_voti", "ZZQ", "sealed") or "format=Sealed" not in fonte("17lands_voti", "ZZQ", "sealed"):
                rossi.append("Sealed: il link dei voti non e' quello del set")
            no = controlla("ZZQ", "sealed")
            if not no or any("manca il progetto" in x for x in no):
                rossi.append(f"Sealed: un set aperto senza dati deve dire i file che mancano ({no})")
            righe.append(f"Sealed: modello {len(m['file'])} chiavi, nessuna del pick; set di prova aperto con --sealed, "
                         f"controllo senza dati rosso sui file ({len(no)}): ok")
        finally:
            ESPANSIONI = vera
            _APERTI.clear(); _APERTI.update(aperti)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Comune"))
    import vivo
    for ev, atteso in (("Sealed_SOS_20260421", ("sealed", "SOS")), ("QuickDraft_FRA_20261008", ("quick", "FRA")),
                       ("PremierDraft_DFT_20250211", ("premier", "DFT")), ("TradSealed_FRA_20260929", (None, None))):
        if vivo.formato_da_evento(ev) != atteso:
            rossi.append(f"evento {ev}: {vivo.formato_da_evento(ev)} invece di {atteso}")
    righe.append("eventi: Sealed_SOS_20260421 -> sealed; TradSealed (non verificato su un log vero) -> nessun formato: ok")
    return rossi


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--prova" in a:
        raise SystemExit(prova())
    if "--nuovo" in a:
        nuovo(a[a.index("--nuovo") + 1], sealed="--sealed" in a); raise SystemExit(0)
    no = controlla()
    print("\n".join(no) if no else f"progetto {_set_attivo()} {formato_attivo()}: verde ({cartella()})")
    raise SystemExit(1 if no else 0)
