"""Le immagini vere delle pedine nel replayer (14 nov 2026, Autore: «troviamo delle immagini arena per i token o le pedine perche' e' meglio che
appaiano sul replayer»).

Fino a quel giorno una pedina era il disegno di default (carta scura con l'emblema d'oro). Le immagini di Arena stanno dentro il client, che non si
smonta; le stesse illustrazioni le ha Scryfall, coi set delle pedine («tFRA», «tFDN»...), con le stesse regole delle immagini delle carte (intatte, la
riga dell'artista). Una pedina di Arena (grpId) ha nel database delle carte set, nome, forza e costituzione (db_carte); si cerca su Scryfall, una volta:
  1. la pedina del suo set col nome, la forza e la costituzione («t:token !"Angel" set:tfra pow=3 tou=3»);
  2. se no la stessa pedina in qualunque set (la stampa piu' recente);
  3. se no il solo nome fra le pedine.
Una pedina che copia una carta (Ajani's Pridemate, la copia di una creatura) ha il nome di una carta vera: usa la sua immagine e non si cerca niente.
La risposta si ricorda in Log_Arena/carte_img/pedine/indice.json ({grpId: indirizzo o ""}: "" = non trovata, non si richiede); l'immagine in
Log_Arena/carte_img/pedine/<grpId>.jpg. Le richieste vanno su un filo solo, una ogni 0,15 s (Scryfall chiede 50-100 ms), e dopo un 429 si aspetta un minuto.

    immagine(grp, nome)       -> il file se c'e' gia', se no None e la pedina va in coda (al_pronto: chi richiamare quando arriva)
    py -I -X utf8 Companion/App/Comune/pedine.py --prova     la scelta su risposte finte, con le negative (niente rete)
"""
import json, os, sys, threading, time, urllib.parse, urllib.request
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402

CARTELLA = os.path.join(percorsi.ROOT, "Log_Arena", "carte_img", "pedine")
INDICE = os.path.join(CARTELLA, "indice.json")
API = "https://api.scryfall.com/cards/search?order=released&dir=desc&q="
_CHIAVE = threading.Lock()
_STATO = dict(indice=None, coda=[], filo=None, pausa=0.0)
al_pronto = []          # funzioni senza argomenti, richiamate (dal filo) quando un'immagine nuova e' sul disco


def file(grp):
    return os.path.join(CARTELLA, f"{int(grp)}.jpg")


def _indice():
    if _STATO["indice"] is None:
        try:
            _STATO["indice"] = {int(k): v for k, v in json.load(open(INDICE, encoding="utf-8")).items()}
        except (OSError, ValueError, AttributeError):
            _STATO["indice"] = {}
    return _STATO["indice"]


def _salva():
    try:
        os.makedirs(CARTELLA, exist_ok=True)
        tmp = INDICE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in _indice().items()}, f)
        os.replace(tmp, INDICE)
    except OSError:
        pass


def dati(grp):
    """(set, nome, forza, costituzione) della pedina dal database delle carte di Arena, None se non e' una pedina conosciuta."""
    try:
        import db_carte
        c = next((c for c in db_carte.carte() if c.get("grpid") == grp), None)
        if not c or not c.get("isToken"):
            return None
        nome = db_carte.testi().get(c.get("titleId"))
        return (c.get("set") or "", nome, c.get("power"), c.get("toughness")) if nome else None
    except Exception:      # noqa: BLE001 - senza database niente pedine
        return None


def domande(set_, nome, forza, cost):
    """Le ricerche in ordine, dalla piu' stretta."""
    nm = nome.replace('"', "")
    pt = (f" pow={forza}" if forza not in (None, "") else "") + (f" tou={cost}" if cost not in (None, "") else "")
    out = []
    if set_:
        out.append(f't:token !"{nm}" set:t{set_.lower()}{pt}')
    if pt:
        out.append(f't:token !"{nm}"{pt}')
    out.append(f't:token !"{nm}"')
    return out


def cerca(grp, chiedi=None):
    """L'indirizzo dell'immagine (normal) della pedina, "" se non si trova. chiedi(url) -> dict della risposta (per le prove)."""
    d = dati(grp)
    if not d:
        return ""
    chiedi = chiedi or _chiedi
    for q in domande(*d):
        r = chiedi(API + urllib.parse.quote(q))
        for c in (r or {}).get("data") or []:
            u = (c.get("image_uris") or (c.get("card_faces") or [{}])[0].get("image_uris") or {}).get("normal")
            if u:
                return u
    return ""


def _chiedi(url):
    if time.time() < _STATO["pausa"]:
        raise TimeoutError("pausa dopo un 429")
    time.sleep(0.15)
    try:
        import capsule
        ctx = capsule.contesto()
    except Exception:      # noqa: BLE001
        ctx = None
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "magic-arena-companion/1.0", "Accept": "application/json"}),
                                   timeout=15, context=ctx)
        return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _STATO["pausa"] = time.time() + 60
            raise
        return None         # 404: nessuna pedina con quella ricerca


def _scarica(grp, u):
    import capsule
    r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "magic-arena-companion/1.0", "Accept": "image/*"}), timeout=15,
                               context=capsule.contesto())
    dati_ = r.read()
    if len(dati_) < 2000:
        raise ValueError("risposta troppo corta")
    os.makedirs(CARTELLA, exist_ok=True)
    tmp = f"{file(grp)}.{threading.get_ident()}.tmp"
    with open(tmp, "wb") as o:
        o.write(dati_)
    os.replace(tmp, file(grp))


def _lavora():
    while True:
        with _CHIAVE:
            if not _STATO["coda"]:
                _STATO["filo"] = None
                return
            grp = _STATO["coda"].pop(0)
        try:
            u = _indice().get(grp)
            if u is None:
                u = cerca(grp)
                with _CHIAVE:
                    _indice()[grp] = u
                    _salva()
            if u and not os.path.isfile(file(grp)):
                _scarica(grp, u)
                for f in list(al_pronto):
                    try:
                        f()
                    except Exception:      # noqa: BLE001 - chi richiama non deve fermare il filo
                        pass
        except Exception:      # noqa: BLE001 - la rete: si riprova la prossima volta che serve
            pass


def immagine(grp, nome=None):
    """Il file dell'immagine della pedina grp, se c'e'; se no None e la pedina va in coda. Una pedina col nome di una carta vera usa la carta."""
    if not grp:
        return None
    try:
        grp = int(grp)
    except (TypeError, ValueError):
        return None
    f = file(grp)
    if os.path.isfile(f):
        return f
    if _indice().get(grp) == "":
        return None
    with _CHIAVE:
        if grp not in _STATO["coda"]:
            _STATO["coda"].append(grp)
        if _STATO["filo"] is None:
            _STATO["filo"] = threading.Thread(target=_lavora, daemon=True, name="pedine")
            _STATO["filo"].start()
    return None


def prova():
    casi = []
    q = domande("FRA", "Angel", "3", "3")
    casi.append(("le ricerche dalla piu' stretta: il set della pedina, poi forza e costituzione, poi il nome",
                 q == ['t:token !"Angel" set:tfra pow=3 tou=3', 't:token !"Angel" pow=3 tou=3', 't:token !"Angel"']))
    casi.append(("una pedina senza forza (Tesoro): niente pow e tou", domande("FRA", "Treasure", None, None) == ['t:token !"Treasure" set:tfra', 't:token !"Treasure"']))
    vero = globals()["dati"]
    try:
        globals()["dati"] = lambda g: ("FRA", "Angel", "3", "3") if g == 1 else None
        chieste = []

        def finta(url):
            chieste.append(urllib.parse.unquote(url[len(API):]))
            if "set:tfra" in chieste[-1]:
                return None             # il set non ce l'ha: si allarga
            return dict(data=[dict(image_uris=dict(normal="https://img/angel.jpg"))])
        casi.append(("se il set non la ha, la stessa pedina in un altro set", cerca(1, finta) == "https://img/angel.jpg" and len(chieste) == 2))
        casi.append(("negativa: una carta che non e' una pedina non si cerca", cerca(2, finta) == "" and len(chieste) == 2))
        casi.append(("negativa: nessuna risposta, nessun indirizzo", cerca(1, lambda u: None) == ""))
    finally:
        globals()["dati"] = vero
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    ok = sum(1 for _n, v in casi if v)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
