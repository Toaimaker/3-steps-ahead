"""Le liste delle carte come in Arena (Autore, 5 nov 2026: «mi piacerebbe che avessero lo stesso stile delle liste del gioco di arena: capsule lunghe e lucide con
dentro nome della carta e costo mana con i loghi veri»; «le carte vengono impilate per costo di mana dall'alto in basso e non ci sono piu' i numeri di mana come separatori»).

Il disegno segue una lista di Arena mandata da Autore il 5 nov 2026 («sarebbe difficile impostarlo secondo questa linea?»): le copie in una scatola scura a sinistra, sotto la
capsula, terre base senza simbolo. I colori e i font restano i nostri («i colori delle carte erano meglio prima e teniamo i nostri font»).

Una riga e' un Canvas: la capsula e' un'immagine fatta con PIL (nei colori della carta, due colori sfumano da sinistra a destra, riflesso nella meta' alta), sopra il nome e i simboli
del costo; a destra un testo facoltativo. Le capsule e i simboli si fanno una volta e si riusano. I simboli sono gli svg di Scryfall in
Companion/Grafica/simboli, resi in png con PyMuPDF. Costo e colori vengono dai quaderni dei set (Espansioni/<SET>/Comune/anagrafe.json), poi da Regole/standard_carte.json.
Una carta che non si trova resta in lista senza costo, grigia: mai sparisce.

Sopra la lista la testata del mazzo (Autore, stesso giorno: «visivamente intendo, cioe' avere gli elementi cosi' disposti? con le curve di mana nome mazzo ecc»): un riquadro con
l'arte della carta piu' rara che sfuma verso destra, il nome, «40/40 Cards» coi colori e la curva di mana a barre d'oro. L'arte viene da Scryfall come l'immagine della carta.

Le carte a figura piena (Autore, stesso giorno: «ma se mostrassimo direttamente le carte a figura piena?»): carta_piena, per la griglia di Collection. Le immagini sono le stesse
dell'hover: un operaio in fondo le scarica una alla volta e le riduce; il disegno le prende in mano quando sono pronte, Tk non si tocca fuori dal suo thread. Cambiando pagina la coda
si svuota. Gli indirizzi diretti delle immagini vengono dal bulk di Scryfall in Dati/scryfall/oracle_cards: il loro server delle immagini non ha il limite dell'API. L'indirizzo per nome
dell'API resta per le carte che il bulk non ha: e' stretto (risponde 429 se lo si chiama in fila, provato il 5 nov 2026), quindi una richiesta ogni 0,6 s, e dopo un 429 un minuto di pausa.

Al passaggio del mouse l'immagine della carta (Autore, 5 nov 2026: «si puo' linkare ogni carta a un'immagine dal web della carta stessa che viene mostrata in hover?»):
da Scryfall per nome esatto, scaricata una volta in fondo, senza fermare la finestra, e tenuta in Log_Arena/carte_img (fuori da git). Se non arriva non compare niente.
Sotto l'immagine i dati del draft (Autore, stesso giorno: «sotto l'hover della carta diamo i metadati dei draft»), dal quaderno del set: GIH WR, ALSA, play rate e partite di 17Lands,
una riga per Quick e una per Premier. Dove 17Lands non ha il GIH c'e' il win rate di Untapped, con «≈» davanti: non e' lo stesso numero (grado C). Fuori dai set del drafter niente tabella.

    py -I -X utf8 Companion/App/Comune/capsule.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import base64, collections, glob, gzip, io, json, re, threading, time, urllib.error, urllib.parse, urllib.request, zlib

ROOT = percorsi.ROOT
CARTELLA = os.path.join(percorsi.GRAFICA, "simboli")
ALTO = 26
RAGGIO = 6                    # gli angoli delle righe (Autore, 5 nov 2026: «capsule piu' rettangolari con bordo arrotondato»)
CARTE_IMG = os.path.join(ROOT, "Log_Arena", "carte_img")
MINI = os.path.join(CARTE_IMG, "mini")     # le carte gia' pronte per la griglia: vedi cuoci
LARGO_IMG = 440       # Autore, 5 nov 2026: «possiamo aumentare la dimensione della carta in hover?»; il file di Scryfall e' largo 488
LARGA_CARTA, ALTA_CARTA = 200, 279
TETTO_IMMAGINI = 96     # carte intere in memoria oltre quelle a vista (solo)
SOTTO_CARTA = 24      # la riga sotto la carta intera
ROSSO_BAN = "#d9534f"     # il bordo e il testo di una carta bandita nel formato scelto (il rosso della finestra)
# Le regole delle immagini di Scryfall (scryfall.com/docs/api/images, lette l'11 nov 2026, Distribuzione/Business_Model.md sezione 5): niente immagini
# desaturate o col colore cambiato, e con l'arte ritagliata (art_crop) l'artista e il copyright scritti altrove nella stessa schermata. Nell'app pubblica:
# le carte che non hai restano a colori (lo dice il testo sotto), e le copertine dei mazzi hanno sotto l'arte la riga con l'artista. L'app di Autore
# resta com'era (uso personale).
NON_TUA = "#f0ad4e"
FASCIA_ARTE = 16
_IN_CORSO, _FALLITE = set(), set()
_CTX = []


def contesto():
    """I certificati di certifi, come gli altri programmi del progetto: quelli di Windows visti da Python risultano scaduti. Costano 150 ms: si leggono alla prima immagine da scaricare, non all'avvio."""
    if not _CTX:
        try:
            import ssl, certifi
            _CTX.append(ssl.create_default_context(cafile=certifi.where()))
        except ImportError:
            _CTX.append(None)
    return _CTX[0]


COLORI = dict(W="#94896a", U="#1d6cae", B="#3b3644", R="#b23a29", G="#2c7a48", C="#5f646e")
LARGA_COPIE = 36              # la scatola delle copie
INIZIO = 30                   # la capsula comincia qui, sopra la scatola
ALTO_TESTATA = 62
GILDE = dict(WU="Azorius", UB="Dimir", BR="Rakdos", RG="Gruul", WG="Selesnya", WB="Orzhov", UR="Izzet", BG="Golgari", WR="Boros", UG="Simic")
MONO = dict(W="White", U="Blue", B="Black", R="Red", G="Green")
BASI = dict(Plains="W", Island="U", Swamp="B", Mountain="R", Forest="G")
_CARTE = None
_BLOCCO_CARTE = threading.Lock()
_DRAFT = {}


def _partite(d):
    return sum((f.get("partite") or 0) for g in d for f in g.values() if isinstance(f, dict))


def _carte():
    """{nome: (costo, colori, cmc)} da tutti i quaderni, poi dallo Standard per quel che manca."""
    global _CARTE
    if _CARTE is not None:
        return _CARTE
    with _BLOCCO_CARTE:      # la carica il filo dei dati all'avvio: la finestra che ne ha bisogno prima aspetta lui, non rilegge i quaderni
        if _CARTE is not None:
            return _CARTE
        c = {}
        for f in glob.glob(os.path.join(ROOT, "Espansioni", "*", "Comune", "anagrafe.json")):
            try:
                a = json.load(open(f, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for x in (a.get("carte") or {}).values():
                if x.get("nome"):
                    d = (x.get("gih") or {}, x.get("untapped") or {})
                    for n in {x["nome"], x["nome"].split(" // ")[0].strip()}:    # una ristampa: vale il set dove la carta ha piu' partite
                        if _partite(d) >= _partite(_DRAFT.get(n, ({}, {}))):
                            _DRAFT[n] = d
                    v = (x.get("costo") or "", x.get("colori") or "", x.get("cmc"), (x.get("rarita") or "").lower())
                    c.setdefault(x["nome"], v)
                    if " // " in x["nome"]:
                        c.setdefault(x["nome"].split(" // ")[0].strip(), v)     # la carta a due facce per il nome della faccia davanti
        try:
            for x in json.load(open(os.path.join(ROOT, "Regole", "standard_carte.json"), encoding="utf-8")):
                c.setdefault(x["name"], (x.get("mana_cost") or "", x.get("colors") or "", x.get("cmc"), (x.get("rarity") or "").lower()))
        except (OSError, ValueError):
            pass
        for n, k in BASI.items():
            c[n] = ("", k, 0, "common")
        _CARTE = c
        return _CARTE


def aggiungi(carte):
    """{nome: (costo, colori, mana, rarita')}: carte in piu', per chi conosce anche quelle fuori dai quaderni e dallo Standard (la collezione)."""
    c = _carte()
    for n, v in carte.items():
        c.setdefault(n, v)


def info(nome):
    """-> (simboli del costo, colori, mana totale); None come mana se la carta non si trova."""
    c = _carte()
    r = c.get(nome) or c.get(nome.split(" // ")[0].strip())
    if r is None:
        return [], "", None
    costo, colori, cmc = r[:3]
    return re.findall(r"\{([^}]+)\}", costo.split(" // ")[0]), "".join(k for k in "WUBRG" if k in (colori or "")), cmc


def ordina(voci):
    """[(nome, copie)] per costo dall'alto in basso, poi per nome; le terre in fondo, le carte senza dati prima delle terre."""
    def chiave(v):
        s, _c, m = info(v[0])
        terra = v[0] in BASI or (m == 0 and not s)
        return (terra, 99 if m is None else m, v[0])
    return sorted(voci, key=chiave)


def metadati(nome):
    """I dati del draft di una carta: [(formato, gih, alsa, play rate, partite)] gia' scritti per la tabella, una riga per Quick e una per Premier. [] se il quaderno non la conosce."""
    _carte()
    if nome in BASI:      # una terra base nel pack non e' una scelta
        return []
    g, u = _DRAFT.get(nome) or _DRAFT.get(nome.split(" // ")[0].strip()) or ({}, {})
    righe = []
    for chiave, etichetta in (("quick", "QUICK"), ("premier", "PREMIER")):
        x, y = g.get(chiave) or {}, u.get(chiave) or {}
        if x.get("gih") is not None:
            wr, partite = f"{x['gih']:.1f}%", x.get("partite")
        elif y.get("wr") is not None and (y.get("partite") or 0) > 0:
            wr, partite = f"≈{y['wr']:.1f}%", y.get("partite")
        else:
            wr, partite = "-", x.get("partite")
        if wr == "-" and x.get("alsa") is None:
            continue
        righe.append((etichetta, wr, "-" if x.get("alsa") is None else f"{x['alsa']:.1f}", "-" if x.get("play_rate") is None else f"{x['play_rate'] * 100:.0f}%", "-" if partite is None else f"{partite:,}"))
    return righe


def nome_mazzo(coppia, splash=""):
    """«UR» -> «Izzet», col colore leggero «Izzet + B»."""
    k = "".join(x for x in "WUBRG" if x in (coppia or ""))
    n = GILDE.get(k) or ("".join(MONO.get(x, x) for x in k) if len(k) < 2 else k) or "Deck"
    return f"{n} + {splash}" if splash else n


def curva(voci):
    """[(copie, nome)] -> quante magie costano 1, 2, 3, 4, 5, 6 o piu'. Le terre non contano."""
    out = [0] * 6
    for q, n in voci:
        toks, _c, m = info(n)
        if n in BASI or m is None or (m == 0 and not toks):
            continue
        out[min(5, max(1, int(m)) - 1)] += q
    return out


def copertina(voci, salta=0):
    """La carta da mettere in testa al mazzo: la piu' rara, poi la piu' cara; salta=1 la seconda. None se non ci sono magie."""
    ordine = dict(mythic=3, rare=2, uncommon=1)
    nomi = sorted({n for _q, n in voci if n not in BASI})
    if not nomi:
        return None
    nomi.sort(key=lambda n: (ordine.get((_carte().get(n) or _carte().get(n.split(" // ")[0].strip()) or ("", "", 0, ""))[3], 0), info(n)[2] or 0), reverse=True)
    return nomi[min(salta, len(nomi) - 1)]


def area_schermo(x, y):
    """(sinistra, alto, destra, basso) dell'area utile del monitor che contiene il punto; None fuori dai monitor o fuori da Windows."""
    try:
        import ctypes
        from ctypes import wintypes as W

        class Info(ctypes.Structure):
            _fields_ = [("cb", W.DWORD), ("monitor", W.RECT), ("lavoro", W.RECT), ("flag", W.DWORD)]

        u = ctypes.windll.user32
        u.MonitorFromPoint.argtypes = [W.POINT, W.DWORD]
        u.MonitorFromPoint.restype = W.HMONITOR
        u.GetMonitorInfoW.argtypes = [W.HMONITOR, ctypes.POINTER(Info)]
        h = u.MonitorFromPoint(W.POINT(int(x), int(y)), 0)
        i = Info(); i.cb = ctypes.sizeof(Info)
        if h and u.GetMonitorInfoW(h, ctypes.byref(i)):
            return i.lavoro.left, i.lavoro.top, i.lavoro.right, i.lavoro.bottom
    except Exception:
        pass
    return None


_INDIRIZZI, _CHIAVE = None, threading.Lock()
_ARTISTI = {}
_PAUSA = [0.0]


def indirizzi():
    """{nome: indirizzo diretto dell'immagine normal}, dall'ultimo bulk di Scryfall; anche per la sola faccia davanti."""
    global _INDIRIZZI
    with _CHIAVE:
        if _INDIRIZZI is None:
            m = {}
            try:
                f = sorted(glob.glob(os.path.join(ROOT, "Dati", "scryfall", "oracle_cards", "*.jsonl.gz")))[-1]
                with gzip.open(f, "rt", encoding="utf-8") as g:
                    for r in g:
                        d = json.loads(r)
                        u = (d.get("image_uris") or (d.get("card_faces") or [{}])[0].get("image_uris") or {}).get("normal")
                        if u and d.get("layout") not in ("art_series", "token", "double_faced_token", "emblem"):      # hanno lo stesso nome della carta e sono solo l'illustrazione
                            m[d["name"]] = u
                            m.setdefault(d["name"].split(" // ")[0], u)
                            a = d.get("artist") or (d.get("card_faces") or [{}])[0].get("artist")
                            if a:
                                _ARTISTI[d["name"]] = a
                                _ARTISTI.setdefault(d["name"].split(" // ")[0], a)
            except (IndexError, OSError, ValueError):
                pass
            _INDIRIZZI = m
        return _INDIRIZZI


def indirizzo(nome, arte=False):
    """L'indirizzo diretto dell'immagine, o None. Le versioni Alchemy (A-) hanno l'immagine della carta di partenza."""
    m = indirizzi()
    testa = nome.split(" // ")[0].strip()
    u = m.get(nome) or m.get(testa) or (m.get(testa[2:]) if testa.startswith("A-") else None)
    return u.replace("/normal/", "/art_crop/", 1) if u and arte else u


def artista(nome):
    """L'artista dell'illustrazione dal bulk di Scryfall (la stessa stampa dell'immagine), o None."""
    indirizzi()
    testa = nome.split(" // ")[0].strip()
    return _ARTISTI.get(nome) or _ARTISTI.get(testa) or (_ARTISTI.get(testa[2:]) if testa.startswith("A-") else None)


def file_immagine(nome, arte=False):
    return os.path.join(CARTE_IMG, ("arte_" if arte else "") + re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_") + ".jpg")


def file_mini(nome):
    return os.path.join(MINI, os.path.basename(file_immagine(nome)))


def cuoci(nome, sorgente=None):
    """La carta pronta per la griglia di Collection, una volta per tutte (Autore, 6 nov 2026: «si possono bakare le carte per rendere tutto piu' veloce?»): ridotta a 200x279 con gli angoli
    arrotondati sul fondo della scheda, in jpg. Prepararla ogni volta costava 22 ms a carta (misura del 6 nov), leggerla cotta meno di 1, e pesa 22 KB. sorgente: un file aperto, se no l'immagine scaricata."""
    from PIL import Image, ImageDraw
    os.makedirs(MINI, exist_ok=True)
    im = Image.open(sorgente or file_immagine(nome)).convert("RGB").resize((LARGA_CARTA, ALTA_CARTA), Image.LANCZOS)
    m = Image.new("L", (LARGA_CARTA * 3, ALTA_CARTA * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), radius=30, fill=255)
    z = Image.new("RGB", im.size, "#18181c")
    z.paste(im, (0, 0), m.resize(im.size, Image.LANCZOS))
    f = file_mini(nome)
    tmp = f"{f}.{threading.get_ident()}.tmp"
    z.save(tmp, "JPEG", quality=88)
    os.replace(tmp, f)


def file_cover(arte, L, H):
    """Dove sta la copertina cotta di un mazzo. Il nome dipende dall'arte: se arriva dopo, cambia."""
    c_e = bool(arte and os.path.exists(file_immagine(arte, True)))
    from account import ASPETTO_PUBBLICO as PUBBLICA       # l'aspetto pubblico vale anche nell'app di Autore (11 nov 2026)
    credito = "|artista" if PUBBLICA and c_e else ""          # la copertina con la riga dell'artista e' un'altra copertina
    return os.path.join(CARTE_IMG, "cover", f"{zlib.crc32(f'{arte if c_e else None}|{L}x{H}{credito}'.encode('utf-8')):08x}.jpg")


def cover_mazzo(arte, L, H):
    """La copertina della scheda di un mazzo: l'arte della carta tagliata a misura, cotta come le carte. arte None: un riquadro scuro. -> il file."""
    from PIL import Image
    f = file_cover(arte, L, H)
    if os.path.exists(f):
        return f
    os.makedirs(os.path.dirname(f), exist_ok=True)
    im = Image.new("RGB", (L, H), "#202024")
    if arte and os.path.exists(file_immagine(arte, True)):
        from account import ASPETTO_PUBBLICO as PUBBLICA
        h = H - FASCIA_ARTE if PUBBLICA else H       # nell'app pubblica sotto l'arte la riga con l'artista e il copyright, fuori dall'illustrazione
        a = Image.open(file_immagine(arte, True)).convert("RGB")
        z = max(L / a.width, h / a.height)
        a = a.resize((int(a.width * z) + 1, int(a.height * z) + 1), Image.LANCZOS)
        x, y = (a.width - L) // 2, (a.height - h) // 3
        im.paste(a.crop((x, y, x + L, y + h)), (0, 0))
        if PUBBLICA:
            from PIL import ImageDraw, ImageFont
            d = ImageDraw.Draw(im)
            d.rectangle((0, h, L, H), fill="#18181c")
            chi = artista(arte)
            testo = (f"Art: {chi} · " if chi else "") + "© Wizards of the Coast"
            try:
                font = ImageFont.truetype(os.path.join(ROOT, "Companion", "Grafica", "Poppins-Regular.ttf"), 9)
            except OSError:
                font = ImageFont.load_default()
            while d.textlength(testo, font=font) > L - 12 and len(testo) > 10:
                testo = testo[:-2].rstrip() + "…"
            d.text((6, h + (FASCIA_ARTE - 11) // 2), testo, fill="#8a8a90", font=font)
    tmp = f"{f}.{threading.get_ident()}.tmp"
    im.save(tmp, "JPEG", quality=92)
    os.replace(tmp, f)
    return f


def scarica_immagine(nome, arte=False):
    """L'immagine della carta (o la sola arte) da Scryfall, una volta sola: scrive il file accanto e poi lo mette al suo posto, cosi' chi lo legge non lo trova mai a meta'."""
    f = file_immagine(nome, arte)
    try:
        os.makedirs(CARTE_IMG, exist_ok=True)
        u = indirizzo(nome, arte)
        api = u is None
        if api:
            if time.time() < _PAUSA[0]:
                return
            testa = nome.split(" // ")[0].strip()
            u = f"https://api.scryfall.com/cards/named?format=image&version={'art_crop' if arte else 'normal'}&exact=" + urllib.parse.quote(testa[2:] if testa.startswith("A-") else testa)
            time.sleep(0.6)
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "magic-arena-companion/1.0", "Accept": "image/*"}), timeout=15, context=contesto())
        dati = r.read()
        if len(dati) < 2000:
            raise ValueError("risposta troppo corta")
        tmp = f"{f}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as o:
            o.write(dati)
        os.replace(tmp, f)
    except urllib.error.HTTPError as e:
        if e.code == 429:        # non e' colpa della carta: si riprova piu' tardi, la prossima volta che serve
            _PAUSA[0] = time.time() + 60
        else:
            _FALLITE.add((nome, arte) if arte else nome)
    except Exception:
        _FALLITE.add((nome, arte) if arte else nome)
    finally:
        _IN_CORSO.discard((nome, arte) if arte else nome)


def file_simbolo(tok):
    return os.path.join(CARTELLA, tok.replace("/", "") + ".svg")


_CACHE = {}       # id della radice di Tk -> (radice, simboli, sfumature, misure dei testi): condivise fra tutte le liste della stessa finestra


def cache_radice(tk):
    """Le cache delle immagini e delle misure, una per radice di Tk (11 nov 2026, sessione Magic 13): la finestra di un mazzo fa una lista nuova a ogni apertura
    e ricalcolava le sfumature di tutte le capsule e la misura di ogni nome (57 e 30 ms ad apertura). La radice resta nel valore: il suo id non si riusa
    finche' la cache c'e' (le prove aprono e chiudono piu' radici: le immagini di una radice chiusa non valgono nell'altra)."""
    r = getattr(tk, "_default_root", None)
    if id(r) not in _CACHE:
        _CACHE[id(r)] = (r, {}, {}, {})
    return _CACHE[id(r)]



def sfumatura(ca, cb, A, spenta, L=64):
    """La sfumatura di una capsula, L x A: piu' chiara in alto, il riflesso nella meta' alta, da ca a cb fra il 30% e il 70% della larghezza. Con numpy dall'11
    nov 2026 (sessione Magic 13): era un doppio ciclo in Python, ~1 ms a coppia di colori; stesse operazioni nello stesso ordine, stessi pixel
    (sfumatura_lenta, --prova)."""
    import numpy_leggero
    from PIL import Image
    np = numpy_leggero.carica()      # senza i 600 MB di OpenBLAS (numpy_leggero)
    q = np.arange(A, dtype=np.float64) / (A - 1)
    luce = 1.22 - 0.5 * q
    velo = np.where(q < 0.46, (0.30 * (1 - q / 0.46) + 0.05) * (0.45 if spenta else 1), 0.0)
    t = np.clip((np.arange(L, dtype=np.float64) / (L - 1) - 0.3) / 0.4, 0.0, 1.0)
    u, v = np.array(ca, dtype=np.float64), np.array(cb, dtype=np.float64)
    rgb = (u[None, None, :] + (v - u)[None, None, :] * t[None, :, None]) * luce[:, None, None] * (0.55 if spenta else 1)
    c = np.minimum(255, rgb + (255 - rgb) * velo[:, None, None])
    return Image.fromarray(c.astype(np.uint8), "RGB")


def sfumatura_lenta(ca, cb, A, spenta, L=64):
    """La sfumatura come si faceva prima, pixel per pixel: solo per la prova."""
    from PIL import Image
    base = Image.new("RGB", (L, A)); px = base.load()
    for y in range(A):
        q = y / (A - 1)
        luce = 1.22 - 0.5 * q
        velo = (0.30 * (1 - q / 0.46) + 0.05) * (0.45 if spenta else 1) if q < 0.46 else 0
        for x in range(L):
            t = max(0.0, min(1.0, (x / (L - 1) - 0.3) / 0.4))
            rgb = [(u + (v - u) * t) * luce * (0.55 if spenta else 1) for u, v in zip(ca, cb)]
            px[x, y] = tuple(int(min(255, c + (255 - c) * velo)) for c in rgb)
    return base

class Liste:
    def __init__(self, tk, F, alto=ALTO):
        self.tk, self.F = tk, F
        _r, self.foto, self.fondi, self.misure = cache_radice(tk)
        self.alto = alto      # alta 20 nella finestra del mazzo (Autore, 7 nov 2026: «tutto piu' piccolo e meglio organizzato»)
        from tkinter import font as tkfont
        self.misura = tkfont.Font(font=F(8, True))
        self.misura_t = tkfont.Font(font=F(11, True))
        self.misura_c = tkfont.Font(font=F(8))
        for f_, d_ in ((self.misura, F(8, True)), (self.misura_t, F(11, True)), (self.misura_c, F(8))):
            f_.chiave = repr(d_)        # la chiave della cache delle misure: il font, non l'oggetto
        self.carte, self.pop, self.sopra, self.timer = {}, None, None, None
        self.dati_hover = True        # la tabella del draft sotto l'immagine in hover
        self.schede = {}              # {nome: [(titolo, valore, colore)]}: i dati della carta sotto l'immagine in hover (la finestra del mazzo: rarita', copie che hai, prezzo)
        self.piene, self.attese, self.coda, self.pronte, self.operaio, self.giro_acceso, self.fermo = {}, {}, collections.deque(), collections.deque(), None, False, False
        self.spente, self.grezze = {}, {}       # le carte che non hai, opache (8 nov 2026), e i dati grezzi delle immagini scaricate per farle

    def simbolo(self, tok, lato=15):
        """La PhotoImage di un simbolo, o None se non c'e'."""
        k = (tok, lato)
        if k not in self.foto:
            png = os.path.join(CARTELLA, f"{tok.replace('/', '')}_{lato}.png")
            try:
                if not os.path.exists(png):
                    try:
                        import pymupdf as fitz
                    except ImportError:
                        import fitz
                    doc = fitz.open(file_simbolo(tok)); pg = doc[0]; z = lato / pg.rect.width
                    pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True).save(png)
                self.foto[k] = self.tk.PhotoImage(file=png)
            except Exception:
                self.foto[k] = None
        return self.foto[k]

    def fondo(self, w, colori, spenta):
        """La capsula larga w: sfumatura dall'alto al basso, riflesso nella meta' alta, due colori da sinistra a destra, angoli tondi."""
        k = (w, colori, spenta, self.alto)
        if k not in self.fondi:
            from PIL import Image, ImageDraw
            kb = ("base", colori, spenta, self.alto)       # la sfumatura 64 x alto non dipende dalla larghezza: una volta per colori (7 nov 2026: era il 60% dell'apertura di un mazzo)
            if kb not in self.fondi:
                a, b = (colori[0], colori[-1]) if colori else ("C", "C")
                ca, cb = (tuple(int(COLORI["C" if spenta else x][i:i + 2], 16) for i in (1, 3, 5)) for x in (a, b))
                self.fondi[kb] = sfumatura(ca, cb, self.alto * 2, spenta)
            im = self.fondi[kb]
            S = 3
            im = im.resize((w * S, self.alto * S), Image.BILINEAR).convert("RGBA")
            km = ("maschera", w, self.alto)        # la forma e il filo dipendono solo dalla misura
            if km not in self.fondi:
                m = Image.new("L", im.size, 0)
                ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, self.alto * S - 1), radius=RAGGIO * S, fill=255)
                filo = Image.new("RGBA", im.size, (0, 0, 0, 0))       # un filo di luce leggero: disegnato a parte, se no il bianco copre il colore
                ImageDraw.Draw(filo).rounded_rectangle((0, 0, w * S - 1, self.alto * S - 1), radius=RAGGIO * S, outline=(255, 255, 255, 60), width=S)
                self.fondi[km] = (m, filo)
            m, filo = self.fondi[km]
            im = Image.alpha_composite(im, filo)
            im.putalpha(m)
            im = im.resize((w, self.alto), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG")
            self.fondi[k] = self.tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        return self.fondi[k]

    def scatola(self):
        """La scatola scura delle copie: la capsula la copre a destra."""
        if ("scatola", self.alto) not in self.fondi:
            from PIL import Image, ImageDraw
            S = 3
            L, H = LARGA_COPIE * S, self.alto * S
            im = Image.new("RGBA", (L, H), (0, 0, 0, 0))
            m = Image.new("L", (L, H), 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, L + 30, H - 1), radius=6 * S, fill=255)
            col = Image.new("RGB", (1, H)); px = col.load()
            for y in range(H):
                g = 30 - int(22 * y / (H - 1))
                px[0, y] = (g, g, g + 6)
            im.paste(col.resize((L, H)), (0, 0), m)
            ImageDraw.Draw(im).rounded_rectangle((0, 0, L + 30, H - 1), radius=6 * S, outline=(120, 120, 130, 255), width=S)
            im = im.resize((LARGA_COPIE, self.alto), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG")
            self.fondi[("scatola", self.alto)] = self.tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        return self.fondi[("scatola", self.alto)]        # la chiave porta l'altezza: la cache e' condivisa fra liste alte 20 e alte di serie

    def cornice(self, colore, lato=50):
        """La cornice del tier: bordo di metallo nel colore del tier, dentro scuro e lucido."""
        k = ("cornice", colore, lato)
        if k not in self.fondi:
            from PIL import Image, ImageDraw
            S = 4; L = lato * S
            rgb = tuple(int(colore[i:i + 2], 16) for i in (1, 3, 5))
            mix = lambda a, b, q: tuple(int(u + (v - u) * q) for u, v in zip(a, b))
            im = Image.new("RGBA", (L, L), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            for y in range(L):         # il metallo: chiaro in alto, pieno a meta', scuro in fondo, con una seconda luce verso il basso
                q = y / (L - 1)
                c = mix((255, 255, 255), rgb, q / 0.42) if q < 0.42 else (mix(rgb, (0, 0, 0), (q - 0.42) / 0.58 * 0.62) if q < 0.8 else mix(mix(rgb, (0, 0, 0), 0.5), rgb, (q - 0.8) / 0.2))
                d.line((0, y, L, y), fill=c + (255,))
            m = Image.new("L", (L, L), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, L - 1, L - 1), radius=12 * S, fill=255)
            bordo = 4 * S
            dentro = Image.new("RGBA", (L, L), (0, 0, 0, 0)); d2 = ImageDraw.Draw(dentro)
            for y in range(bordo, L - bordo):
                q = (y - bordo) / (L - 2 * bordo)
                d2.line((0, y, L, y), fill=mix((58, 58, 68), (14, 14, 18), min(1, q * 1.4)) + (255,))
            m2 = Image.new("L", (L, L), 0); ImageDraw.Draw(m2).rounded_rectangle((bordo, bordo, L - bordo - 1, L - bordo - 1), radius=8 * S, fill=255)
            im.paste(dentro, (0, 0), m2)
            ImageDraw.Draw(im).rounded_rectangle((bordo - S, bordo - S, L - bordo + S - 1, L - bordo + S - 1), radius=9 * S, outline=mix(rgb, (0, 0, 0), 0.55) + (255,), width=S)
            im.putalpha(m)
            im = im.resize((lato, lato), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG")
            self.fondi[k] = self.tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        return self.fondi[k]

    def fondo_testata(self, w, nome, alto=ALTO_TESTATA, scuro=95):
        """Il riquadro della testata: scuro, con l'arte della carta a sinistra che sfuma verso destra."""
        f = file_immagine(nome, True) if nome else None
        c_e = bool(f and os.path.exists(f))
        k = ("testata", w, alto, scuro, nome if c_e else None)
        if k not in self.fondi:
            from PIL import Image, ImageDraw
            S = 2
            L, H = w * S, alto * S
            # (11 nov 2026: 20-40 ms per testata, rifatta a ogni mazzo nuovo; ora ~8. Il fondo e la sfumatura si fanno da una riga di pixel, non riga per riga e
            # pixel per pixel; l'arte si riduce col Lanczos dentro il ritaglio; l'ultima riduzione e' un 2:1 esatto, box)
            col = Image.frombytes("RGBA", (1, H), bytes(v for y in range(H) for g in (44 - int(26 * y / (H - 1)),) for v in (g, g, g + 8, 255)))
            im = col.resize((L, H), Image.NEAREST)
            if c_e:
                try:
                    a = Image.open(f).convert("RGBA")
                    larga = max(int(L * 0.62), 150 * S)
                    z = max(larga / a.width, H / a.height)
                    nl, nh = int(a.width * z) + 1, int(a.height * z) + 1
                    x0, y0 = (nl - larga) // 2, (nh - H) // 3
                    a = a.resize((larga, H), Image.LANCZOS, box=(x0 / z, y0 / z, (x0 + larga) / z, (y0 + H) / z), reducing_gap=2.0)
                    sfuma = Image.frombytes("L", (larga, 1), bytes(int(235 * min(1.0, (1 - x / larga) / 0.6)) for x in range(larga)))
                    a.putalpha(sfuma.resize((larga, H), Image.NEAREST))
                    im.alpha_composite(a)
                    velo = Image.new("RGBA", (L, H), (0, 0, 0, 0))    # un velo sopra, perche' il nome si legga su ogni arte
                    ImageDraw.Draw(velo).rectangle((0, 0, L, H), fill=(0, 0, 0, scuro))
                    im.alpha_composite(velo)
                except Exception:
                    pass
            ImageDraw.Draw(im).rounded_rectangle((0, 0, L - 1, H - 1), radius=5 * S, outline=(100, 100, 112, 255), width=S)
            m = Image.new("L", (L, H), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, L - 1, H - 1), radius=5 * S, fill=255)
            im.putalpha(m)
            im = im.resize((w, alto), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG", compress_level=1)
            self.fondi[k] = self.tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        return self.fondi[k]

    def chiedi_arte(self, c, arte, disegna):
        """L'arte di una carta, in fondo, se non c'e' ancora: quando arriva ridisegna chi l'ha chiesta."""
        if not arte or os.path.exists(file_immagine(arte, True)):
            return

        def tenta(n=0):
            if not c.winfo_exists():
                return
            if os.path.exists(file_immagine(arte, True)):
                disegna()
            elif n < 80 and (arte, True) not in _FALLITE:
                c.after(200, lambda: tenta(n + 1))
        if (arte, True) not in _IN_CORSO and (arte, True) not in _FALLITE:
            _IN_CORSO.add((arte, True))
            threading.Thread(target=scarica_immagine, args=(arte, True), daemon=True).start()
        c.after(300, tenta)

    def testata(self, padre, nome, carte, totale, valori_curva, arte=None, colori=(), bg="#18181c"):
        """La testata del mazzo come in Arena: arte, nome, «40/40 Cards» coi colori, a destra la curva di mana."""
        tk = self.tk
        c = tk.Canvas(padre, height=ALTO_TESTATA, bg=bg, highlightthickness=0, bd=0)
        font = self.F(11, True)

        def disegna(e=None):
            w = c.winfo_width()
            if w < 60:
                return
            c.delete("all")
            c.create_image(0, 0, image=self.fondo_testata(w, arte), anchor="nw")
            passo, largo = 9, 7                   # la curva: tubi neri con dentro l'oro
            x0 = w - 9 - passo * len(valori_curva) + (passo - largo)
            cima, base = 10, ALTO_TESTATA - 10
            mx = max(valori_curva) or 1
            for i, q in enumerate(valori_curva):
                x = x0 + i * passo
                c.create_rectangle(x, cima, x + largo, base, fill="#07070b", outline="#4a4a52")
                if q:
                    h = max(3, round((base - cima - 2) * q / mx))
                    c.create_rectangle(x + 1, base - h, x + largo, base, fill="#d9a441", outline="")
                    c.create_rectangle(x + 1, base - h, x + 2, base, fill="#f6d98c", outline="")
            t = self.taglia(nome, x0 - 18, self.misura_t)
            for dx, dy in ((1, 1), (1, 2), (0, 1), (2, 1)):
                c.create_text(10 + dx, 21 + dy, text=t, anchor="w", fill="#000000", font=font)
            c.create_text(10, 21, text=t, anchor="w", fill="#ffffff", font=font)
            testo = f"{carte}/{totale} Cards"
            c.create_text(11, 44, text=testo, anchor="w", fill="#000000", font=self.F(8))
            c.create_text(10, 43, text=testo, anchor="w", fill="#ffffff", font=self.F(8))
            x = 10 + self.misura_c.measure(testo) + 6
            for k in colori:
                img = self.simbolo(k, 13)
                if img is not None and x + 13 < x0 - 2:
                    c.create_image(x, 43, image=img, anchor="w"); x += 15

        attesa = {"id": None, "w": None}

        def ridimensiona(e):
            """Mentre la finestra si sistema arrivano tre o quattro larghezze di fila, e ognuna rifaceva l'arte (7 nov 2026: 0,1 s per apertura): si disegna l'ultima."""
            if e.width == attesa["w"]:
                return
            attesa["w"] = e.width
            if attesa["id"] is not None:
                c.after_cancel(attesa["id"])
            attesa["id"] = c.after(20, lambda: (attesa.update(id=None), disegna()))
        c.bind("<Configure>", ridimensiona)
        self.chiedi_arte(c, arte, disegna)
        return c

    def dati(self, padre, lettera, colore, nome, valore, bg="#18181c", lato=46):
        """Il tier nella sua cornice e accanto un valore, col nome sopra."""
        c = self.tk.Canvas(padre, height=lato, bg=bg, highlightthickness=0, bd=0)

        def disegna(e=None):
            w = c.winfo_width()
            if w < 60:
                return
            c.delete("all")
            c.create_image(0, 0, image=self.cornice(colore, lato), anchor="nw")
            c.create_text(lato / 2 + 1, lato / 2 + 2, text=lettera, fill="#000000", font=self.F(19, True))
            c.create_text(lato / 2, lato / 2 + 1, text=lettera, fill=colore, font=self.F(19, True))
            c.create_text(lato + 12, lato / 2 - 11, text=nome, anchor="w", fill="#ffffff", font=self.F(7, True))
            c.create_text(lato + 12, lato / 2 + 8, text=valore, anchor="w", fill="#ffffff", font=self.F(11, True))
        c.bind("<Configure>", disegna)
        return c

    def misura_di(self, testo, misura=None):
        """La larghezza di un testo in un font, ricordata (ogni misura e' una chiamata a Tk)."""
        misura = misura or self.misura
        k = (getattr(misura, "chiave", None) or str(misura), testo)
        if k not in self.misure:
            self.misure[k] = misura.measure(testo)
        return self.misure[k]

    def taglia(self, testo, largo, misura=None):
        if self.misura_di(testo, misura) <= largo:
            return testo
        while testo and self.misura_di(testo + "…", misura) > largo:
            testo = testo[:-1]
        return testo.rstrip() + "…"

    def disegna_riga(self, c, w, nome, quante=1, destra="", spenta=False, col_destra="#ffffff", copie=None, colonna=""):
        """Il disegno di una capsula larga w sulla tela c (la sua, o la riga di un elenco: CartaTela)."""
        toks, colori, _m = info(nome)
        testo_c = copie if copie is not None else f"{quante}x"
        font = self.F(8, True)
        c.delete("all")
        fuori = max(self.misura_di(colonna), self.misura_di(destra)) + 8 if (destra or colonna) else 1
        larga = max(40, w - INIZIO - fuori)
        c.larga = larga
        c.create_image(0, 0, image=self.scatola(), anchor="nw")
        # il numero delle copie si deve leggere subito (Autore, 5 nov 2026: «il numero copie a sx un po' piu' leggibile»)
        c.create_text(16, self.alto / 2 + 1, text=testo_c, fill="#000000", font=self.F(10 if self.alto >= ALTO else 8, True))
        c.create_text(15, self.alto / 2, text=testo_c, fill="#8a8a90" if spenta else "#ffffff", font=self.F(10 if self.alto >= ALTO else 8, True))
        c.create_image(INIZIO, 0, image=self.fondo(larga, colori, spenta), anchor="nw")
        x = INIZIO + larga - 9
        for t in reversed(toks):
            img = self.simbolo(t, 15 if self.alto >= ALTO else 14)
            if img is not None:
                c.create_image(x, self.alto / 2, image=img, anchor="e"); x -= 16
        t = self.taglia(nome, x - INIZIO - 14)
        tx = INIZIO + 11
        # lieve grassetto e ombretta sotto (Autore, 5 nov 2026: «i testi sulle carte con un lieve grassetto e ombretta sotto per vederli meglio»)
        for dx, dy in ((1, 2), (1, 1), (0, 1)):
            c.create_text(tx + dx, self.alto / 2 + dy, text=t, anchor="w", fill="#0a0c12", font=font)
        c.create_text(tx, self.alto / 2, text=t, anchor="w", fill="#a7a9ad" if spenta else "#ffffff", font=font)
        if destra:
            c.create_text(w - 1, self.alto / 2, text=destra, anchor="e", fill="#707074" if spenta else col_destra, font=self.F(8, True))

    def riga(self, padre, nome, quante=1, destra="", spenta=False, bg="#18181c", col_destra="#ffffff", copie=None, colonna=""):
        """Una capsula. quante: le copie, nella scatola a sinistra come «3x»; copie: un testo al suo posto (2/3 durante la partita); destra: un testo fuori, a destra.
        colonna: il testo piu' largo che quella colonna puo' avere: le capsule di una lista finiscono tutte allo stesso punto, anche quelle senza testo a destra (Autore, 6 nov 2026: «le capsule dei mazzi devono avere tutte la stessa lunghezza»)."""
        c = self.tk.Canvas(padre, height=self.alto, bg=bg, highlightthickness=0, bd=0)
        st = {"q": quante}

        def disegna(e=None):
            w = c.winfo_width()
            if w >= 60:
                self.disegna_riga(c, w, nome, st["q"], destra, spenta, col_destra, copie, colonna)

        def metti_q(q):
            """Le copie cambiate: si ridisegna solo questa capsula (il builder, 11 nov 2026)."""
            if q != st["q"]:
                st["q"] = q
                disegna()
        c.metti_q = metti_q
        c.bind("<Configure>", disegna)
        c.bind("<Enter>", lambda e: self.entra(c, nome)); c.bind("<Leave>", self.esci); c.bind("<Destroy>", self.esci, add="+")
        return c

    def elenco(self, padre, voci, bg="#18181c", passo=0):
        """Tutte le capsule di una lista su una tela sola, una riga per carta (11 nov 2026, sessione Magic 13, Note/Motore_Grafico_App.md): con una tela per
        capsula la finestra di un mazzo aveva 60-80 finestre di Windows solo per la lista. voci: [(nome, copie)]; passo: lo spazio fra le righe. Ogni riga e' una
        CartaTela: la carta grande in hover e i suoi dati come prima. Una voce puo' avere un terzo elemento, le opzioni di disegna_riga (spenta, copie, destra,
        colonna, col_destra). -> la tela, con .righe = [(riga, nome, copie, opzioni)]."""
        import carta_tela
        alto = self.alto + passo
        # width=1: la tela non chiede i suoi 380 pixel di partenza, quindi non spinge l'impaginazione della finestra (11 nov 2026: la lista del mazzo si disegnava a
        # 189, poi 386, poi 334 pixel, tre volte per apertura)
        c = self.tk.Canvas(padre, width=1, height=max(1, len(voci) * alto - passo), bg=bg, highlightthickness=0, bd=0)
        sm = carta_tela.Smistatore(c)
        c.righe = []
        for i, v in enumerate(voci):
            nome, q = v[0], v[1]
            opz = v[2] if len(v) > 2 else {}        # le opzioni di disegna_riga: spenta, copie, destra, colonna, col_destra
            r = carta_tela.CartaTela(c, 0, i * alto, 1, self.alto, sm)
            r.bind("<Enter>", lambda e, r=r, nome=nome: self.entra(r, nome)); r.bind("<Leave>", self.esci); r.bind("<Destroy>", self.esci, add=True)
            c.righe.append((r, nome, q, opz))

        def disegna():
            c.attesa_ = None
            try:
                w = c.winfo_width()
            except Exception:       # la tela non c'e' piu'
                return
            if w < 60 or w == getattr(c, "larga_fatta", None):
                return
            c.larga_fatta = w
            for r, nome, q, opz in c.righe:
                r.larga = w
                self.disegna_riga(r, w, nome, q, **opz)

        def ridimensiona(e=None):
            """Mentre la finestra si impagina arrivano piu' larghezze di fila, tutte dentro lo stesso giro di Tk (la tela di sinistra prende la sua larghezza solo
            dopo che la lista si e' gia' impaginata a quella richiesta): si disegna una volta, all'ultima, col primo timer dopo l'impaginazione. Un timer e non
            after_idle: l'impaginazione e' fatta di compiti idle, e un idle girava in mezzo (11 nov 2026: due disegni per apertura, a 189 e a 335 pixel)."""
            if getattr(c, "attesa_", None) is None:
                c.attesa_ = c.after(1, disegna)
        c.attesa_ = None
        c.disegna_ora = disegna
        c.bind("<Configure>", ridimensiona)
        return c

    # ------------------------------------------------ le carte a figura piena
    def nuova_pagina(self):
        """Cambia la pagina: le carte che non si vedono piu' non si scaricano. Tenute troppe immagini, si liberano: le tele di prima non ci sono piu'."""
        self.coda.clear(); self.attese.clear()
        if len(self.piene) > 400:
            self.piene.clear(); self.grezze.clear(); self.spente.clear()

    def solo(self, nomi):
        """Scorrendo: si aspettano solo le carte a vista, l'operaio salta le altre; oltre TETTO_IMMAGINI immagini in memoria restano solo quelle a vista (duecento
        facevano 45 MB di pixel, e Tk su Windows ne tiene una seconda copia per disegnarle; tutta la collezione 700). Dall'11 nov 2026 il tetto e' 96, anche
        per le carte opache (prima 200, e a 200 si buttavano tutte): una miniatura cotta si rilegge dal disco in meno di 1 ms."""
        vivi = set(nomi)
        for n in [n for n in self.attese if n not in vivi]:
            del self.attese[n]
        if len(self.piene) > TETTO_IMMAGINI:
            for n in [n for n in self.piene if n not in vivi]:
                del self.piene[n]; self.grezze.pop(n, None)
        if len(self.spente) > TETTO_IMMAGINI:
            for k in [k for k in self.spente if k[0] not in vivi]:
                del self.spente[k]

    def carta_piena(self, padre, nome, sotto="", bg="#18181c", spenta=False, bandita=False, su=None):
        """Una carta intera con sotto, in grigio al centro, il solo testo sotto (Autore, 5 nov 2026: «teniamo sotto le carte in grigio al centro un testo che indica in quante copie
        la si possiede»). Finche' l'immagine non c'e', un riquadro col nome. spenta: la carta che non hai, opaca (Autore, 8 nov 2026: «in collection le carte mancanti falle
        opache che si capisca che non si hanno»). bandita: bandita nel formato scelto, col bordo rosso sopra l'immagine e il testo sotto in rosso (10 nov 2026).
        su=(x, y, smistatore): la carta si disegna sulla tela padre, col centro in alto in (x, y), non in una tela sua (carta_tela.py, 11 nov 2026: una finestra di
        Windows per carta faceva scattare la rotella di Collection)."""
        if su is not None:
            import carta_tela
            c = carta_tela.CartaTela(padre, su[0] - LARGA_CARTA / 2, su[1], LARGA_CARTA, ALTA_CARTA + SOTTO_CARTA, su[2])
        else:
            c = self.tk.Canvas(padre, width=LARGA_CARTA, height=ALTA_CARTA + SOTTO_CARTA, bg=bg, highlightthickness=0, bd=0)
        from account import ASPETTO_PUBBLICO as PUBBLICA
        c.spenta, c.fondo_spenta = spenta, bg
        if spenta and PUBBLICA:           # a colori pieni (le regole di Scryfall): che non ce l'hai lo dice il testo sotto
            sotto = f"{sotto}  ·  NOT OWNED" if sotto else "NOT OWNED"
        colore = ROSSO_BAN if bandita else (NON_TUA if PUBBLICA else "#6e6e74") if spenta else "#e6e6ea"
        c.create_text(LARGA_CARTA / 2, ALTA_CARTA + SOTTO_CARTA / 2, text=sotto, fill=colore, font=self.F(11, True),
                      tags="sotto")     # «x1 x2 ecc e piu' visibile», stesso giorno
        c.create_rectangle(1, 1, LARGA_CARTA - 1, ALTA_CARTA - 1, fill="#202024", outline="#3a3a42")
        c.create_text(LARGA_CARTA / 2, ALTA_CARTA / 2, text=nome, width=LARGA_CARTA - 30, fill="#a7a9ad", font=self.F(9, True), justify="center")
        c.bind("<Enter>", lambda e: self.entra(c, nome)); c.bind("<Leave>", self.esci); c.bind("<Destroy>", self.esci, add="+")
        if nome not in self.piene and os.path.exists(file_mini(nome)):
            self.da_mini(nome)
        if nome in self.piene:
            c.create_image(0, 0, image=self.immagine_tela(c, nome), anchor="nw")
        else:
            attesa = self.attese.setdefault(nome, [])
            attesa.append(c)
            if len(attesa) == 1:
                self.coda.append(nome)
            self.sveglia(c)
        if bandita:     # sopra l'immagine, anche quando arriva dopo (raccogli la mette sotto il tag «ban»)
            c.create_rectangle(2, 2, LARGA_CARTA - 2, ALTA_CARTA - 2, outline=ROSSO_BAN, width=4, tags="ban")
        return c

    def immagine_tela(self, c, nome):
        """L'immagine per la tela: quella vera, o la versione opaca se la carta non la hai (spenta). Nell'app pubblica sempre quella vera."""
        from account import ASPETTO_PUBBLICO as PUBBLICA
        if not getattr(c, "spenta", False) or PUBBLICA:
            return self.piene[nome]
        k = (nome, c.fondo_spenta)
        if k not in self.spente:
            from PIL import Image, ImageEnhance, ImageTk
            try:
                f = file_mini(nome)
                src = Image.open(f) if os.path.exists(f) else Image.open(io.BytesIO(base64.b64decode(self.grezze[nome]) if isinstance(self.grezze.get(nome), str) else self.grezze[nome]))
                im = src.convert("RGBA")
                g = ImageEnhance.Color(im).enhance(0.25)        # quasi senza colore
                rgb = tuple(int(c.fondo_spenta[i:i + 2], 16) for i in (1, 3, 5))
                out = Image.blend(Image.new("RGBA", im.size, rgb + (255,)), g, 0.38)       # e velata dal fondo: si vede, ma si capisce che manca
                out.putalpha(im.getchannel("A"))
                if len(self.spente) > 4 * TETTO_IMMAGINI:     # solo() le sfoltisce scorrendo; questo e' il tetto per chi non chiama solo()
                    self.spente.clear()
                self.spente[k] = ImageTk.PhotoImage(out)
            except Exception:
                return self.piene[nome]
        return self.spente[k]

    def da_mini(self, nome):
        from PIL import Image, ImageTk
        try:
            self.piene[nome] = ImageTk.PhotoImage(Image.open(file_mini(nome)))
        except Exception:
            pass

    def sveglia(self, c):
        if self.operaio is None or not self.operaio.is_alive():
            self.operaio = threading.Thread(target=self.lavora, daemon=True)
            self.operaio.start()
        if not self.giro_acceso:
            self.giro_acceso = True
            self.radice = c.winfo_toplevel()
            self.radice.after(70, self.raccogli)

    def lavora(self):
        """Fuori dal thread di Tk: scarica e cuoce, niente widget."""
        while True:
            try:
                nome = self.coda.popleft()
            except IndexError:
                return
            if nome not in self.attese:      # scorsa via prima che toccasse a lei
                continue
            if not os.path.exists(file_mini(nome)):
                if not os.path.exists(file_immagine(nome)):
                    if self.fermo or nome in _FALLITE or nome.startswith("Carta Inventata"):
                        continue
                    scarica_immagine(nome)
                    time.sleep(0.03)
                try:
                    cuoci(nome)
                except Exception:
                    continue
            self.pronte.append((nome, None))

    def raccogli(self):
        """Nel thread di Tk: mette le immagini pronte sulle loro tele."""
        for _ in range(16):       # poche per giro: la finestra resta viva
            try:
                nome, dati = self.pronte.popleft()
            except IndexError:
                break
            # la stessa carta puo' arrivare due volte, se la pagina si e' ridisegnata mentre si scaricava: una immagine nuova al suo posto spegnerebbe quella gia' sulla tela
            if nome not in self.piene:
                if dati is None:
                    self.da_mini(nome)
                else:
                    self.piene[nome] = self.tk.PhotoImage(data=dati)
                    self.grezze[nome] = dati
            for c in self.attese.pop(nome, []) if nome in self.piene else ():
                if c.winfo_exists():
                    c.create_image(0, 0, image=self.immagine_tela(c, nome), anchor="nw")
                    c.tag_raise("ban")      # il bordo rosso di una bandita resta sopra l'immagine
        if self.coda and (self.operaio is None or not self.operaio.is_alive()):     # una carta arrivata mentre l'operaio chiudeva
            self.operaio = threading.Thread(target=self.lavora, daemon=True)
            self.operaio.start()
        if self.pronte or self.coda or (self.operaio is not None and self.operaio.is_alive()):
            self.radice.after(30, self.raccogli)
        else:
            self.giro_acceso = False

    # ------------------------------------------------ l'immagine della carta al passaggio del mouse
    def entra(self, c, nome):
        self.esci()
        self.sopra = c
        self.timer = c.after(220, lambda: self.mostra(c, nome, 0))     # un attimo: scorrendo la lista non lampeggia niente

    def esci(self, e=None):
        if self.timer is not None and self.sopra is not None:
            try:
                self.sopra.after_cancel(self.timer)
            except Exception:
                pass
        self.timer = self.sopra = None
        if self.pop is not None:
            try:
                self.pop.destroy()
            except Exception:
                pass
            self.pop = None

    def immagine(self, nome):
        if nome not in self.carte:
            from PIL import Image, ImageDraw
            im = Image.open(file_immagine(nome)).convert("RGBA")
            im = im.resize((LARGO_IMG, round(im.height * LARGO_IMG / im.width)), Image.LANCZOS)
            m = Image.new("L", (im.width * 3, im.height * 3), 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), radius=round(m.width * 0.047), fill=255)
            im.putalpha(m.resize(im.size, Image.LANCZOS))
            buf = io.BytesIO(); im.save(buf, "PNG")
            self.carte[nome] = self.tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        return self.carte[nome]

    def mostra(self, c, nome, tentativi):
        if self.sopra is not c or nome in _FALLITE or nome.startswith("Carta Inventata"):
            return
        if not os.path.exists(file_immagine(nome)):
            if nome not in _IN_CORSO:
                _IN_CORSO.add(nome)
                threading.Thread(target=scarica_immagine, args=(nome,), daemon=True).start()
            if tentativi < 80:
                self.timer = c.after(100, lambda: self.mostra(c, nome, tentativi + 1))
            return
        try:
            img = self.immagine(nome)
        except Exception:
            return
        top = c.winfo_toplevel()
        p = self.pop = self.tk.Toplevel(top)
        p.withdraw()
        p.overrideredirect(True)
        p.configure(bg="#101014")
        # l'immagine e i dati su una tela sola (11 nov 2026, sessione Magic 13): prima un'etichetta per l'immagine e una per ogni dato, 20-40 widget a ogni hover
        cv = self.tk.Canvas(p, bg="#101014", highlightthickness=0, bd=0); cv.pack()
        self.disegna_hover(cv, img, self.schede.get(nome), metadati(nome) if self.dati_hover else None)
        p.update_idletasks()
        # il mouse puo' essere gia' uscito mentre la scheda si costruiva: esci() l'ha distrutta (8 nov 2026, «bad window path name» nel registro della finestra)
        if not p.winfo_exists() or self.pop is not p or not c.winfo_exists():
            return
        w, h = p.winfo_reqwidth(), p.winfo_reqheight()
        a_destra = c.winfo_rootx() + c.winfo_width() / 2 < top.winfo_rootx() + top.winfo_width() / 2     # dalla parte della finestra dove c'e' posto
        x = c.winfo_rootx() + c.winfo_width() + 10 if a_destra else c.winfo_rootx() - w - 10
        y = max(top.winfo_rooty(), min(c.winfo_rooty() - h // 2, top.winfo_rooty() + top.winfo_height() - h))
        a = area_schermo(c.winfo_rootx(), c.winfo_rooty())
        if a:     # dentro il monitor: prima dall'altra parte, per non finire sotto il mouse
            if x + w > a[2]:
                x = c.winfo_rootx() - w - 10
            if x < a[0]:
                x = c.winfo_rootx() + c.winfo_width() + 10
            x, y = max(a[0], min(x, a[2] - w)), max(a[1], min(y, a[3] - h))
        p.geometry(f"{w}x{h}+{x}+{y}")
        p.deiconify()

    def disegna_hover(self, cv, img, voci, righe):
        """La carta grande e sotto i suoi dati, disegnati. voci: [(titolo, valore, colore)], una colonna per dato col titolo sopra (Autore, 7 nov 2026: «i
        minidati a sx delle carte li mettiamo sulla scheda della carta quando appare»); righe: la tabella del draft, i nomi sopra con un colore ciascuno
        (Autore, 5 nov 2026: «i titoletti piu' grandi e di colori differenti»), una riga per formato."""
        import tabella_tela as TT
        fondo, W = "#18181c", img.width()
        cv.create_image(0, 0, image=img, anchor="nw")
        y = img.height()
        tinte = ("#24baff", "#5cb85c", "#f0ad4e", "#c792ea", "#ffffff")
        if voci:
            _w, h1 = TT.misura(cv, self.F(9, True), "Ag"); _w, h2 = TT.misura(cv, self.F(10, True), "Ag")
            y0 = y + 6
            alto = 6 + h1 + h2 + 2 + 6
            cv.create_rectangle(0, y0, W, y0 + alto, fill=fondo, width=0)
            n = len(voci)
            for i, (titolo, valore, col) in enumerate(voci):
                x = 10 + i * (W - 20) / n
                cv.create_text(x, y0 + 6, text=titolo, anchor="nw", fill=tinte[i % len(tinte)], font=self.F(9, True))
                cv.create_text(x, y0 + 6 + h1 + 1, text=valore, anchor="nw", fill=col or "#ffffff", font=self.F(10, True))
            y = y0 + alto
        if righe:
            testa = (("", "#ffffff"), ("GIH WR", "#24baff"), ("ALSA", "#5cb85c"), ("PLAYED", "#f0ad4e"), ("GAMES", "#c792ea"))
            _w, h1 = TT.misura(cv, self.F(9, True), "Ag"); _w, h8 = TT.misura(cv, self.F(8, True), "Ag"); _w, h10 = TT.misura(cv, self.F(10, True), "Ag")
            hr = max(h8, h10) + 2
            y0 = y + 6
            alto = 6 + h1 + hr * len(righe) + 6
            cv.create_rectangle(0, y0, W, y0 + alto, fill=fondo, width=0)
            larghe = [max([TT.misura(cv, self.F(9, True), testa[i][0])[0]] + [TT.misura(cv, self.F(8 if i == 0 else 10, True), str(r[i]))[0] for r in righe if i < len(r)])
                      for i in range(len(testa))]
            destra, xs = W - 10, {}
            for i in range(len(testa) - 1, 0, -1):      # le colonne dei numeri allineate a destra, da destra; il nome del formato a sinistra
                xs[i] = destra
                destra -= larghe[i] + 10
            for i, (t, col) in enumerate(testa):
                if t:
                    cv.create_text(xs[i], y0 + 6, text=t, anchor="ne", fill=col, font=self.F(9, True))
            for r_, riga in enumerate(righe):
                yr = y0 + 6 + h1 + r_ * hr + 1
                for i, v in enumerate(riga):
                    if i == 0:
                        cv.create_text(10, yr, text=v, anchor="nw", fill="#ffffff", font=self.F(8, True))
                    elif i in xs:
                        cv.create_text(xs[i], yr, text=v, anchor="ne", fill="#ffffff", font=self.F(10, True))
            y = y0 + alto
        cv.configure(width=W, height=y)

def prova():
    casi = [("costo e colori di una carta del set", info("Saheeli, Jewel of Avishkar")[:2] == (["2", "U", "R"], "UR")),
            ("una terra base non ha simboli", info("Island")[0] == []),
            ("i dati del draft", [r[:2] for r in metadati("Saheeli, Jewel of Avishkar")] == [("QUICK", "60.4%"), ("PREMIER", "55.5%")] or len(metadati("Saheeli, Jewel of Avishkar")) == 2),
            ("nessun dato su una carta sconosciuta o una base", metadati("Carta Inventata") == [] and metadati("Island") == []),
            ("il nome del mazzo", (nome_mazzo("UR"), nome_mazzo("RU", "B"), nome_mazzo("R"), nome_mazzo("")) == ("Izzet", "Izzet + B", "Red", "Deck")),
            ("la curva conta le magie, non le terre", curva([(2, "Icy Reception"), (9, "Island"), (1, "Saheeli, Jewel of Avishkar"), (3, "Carta Inventata")]) == [0, 2, 0, 1, 0, 0] or curva([(2, "Icy Reception"), (9, "Island"), (1, "Saheeli, Jewel of Avishkar")])[3] == 1),
            ("la copertina e' la piu' rara", copertina([(4, "Icy Reception"), (1, "The Theorist, Jace Beleren"), (9, "Island")]) == "The Theorist, Jace Beleren"),
            ("senza magie niente copertina", copertina([(9, "Island")]) is None),
            ("la seconda copertina non e' la prima", copertina([(4, "Icy Reception"), (1, "The Theorist, Jace Beleren"), (9, "Island")], 1) == "Icy Reception"),
            ("una terra base ha il suo colore", info("Island")[1] == "U"),
            ("carta sconosciuta: resta, senza costo", info("Carta Inventata") == ([], "", None)),
            ("in ordine di costo, terre in fondo", [n for n, _ in ordina([("Island", 9), ("Awaken the Inferno", 2), ("Icy Reception", 2), ("Carta Inventata", 1)])] == ["Icy Reception", "Awaken the Inferno", "Carta Inventata", "Island"]),
            ("a parita' di costo per nome", [n for n, _ in ordina([("Surveillance Phantasm", 1), ("Icy Reception", 1)])] == ["Icy Reception", "Surveillance Phantasm"]),
            ("ogni simbolo del set ha il suo file", all(os.path.exists(file_simbolo(t)) for x in _carte().values() for t in re.findall(r"\{([^}]+)\}", x[0]) if t in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "X", "W", "U", "B", "R", "G", "C", "G/U", "2/W")))]
    import tkinter as tk
    root = tk.Tk(); root.withdraw()
    L = Liste(tk, lambda n, b=False: ("Segoe UI", n, "bold" if b else "normal"))
    for i, (n, q, sp) in enumerate((("Saheeli, Jewel of Avishkar", 1, False), ("Island", 9, False), ("Carta Inventata", 1, True))):
        w = L.riga(root, n, q, destra="12%" if i == 0 else "", spenta=sp); w.pack(fill="x")
    root.update_idletasks(); root.geometry("300x100"); root.update()
    uguali = [L.riga(root, "Island", 1, destra=d, colonna="M 4/4") for d in ("", "C 1/1", "M 4/4")]
    for w in uguali:
        w.pack(fill="x")
    root.geometry("300x180+6000+0"); root.deiconify(); root.update(); root.update()
    casi.append(("le capsule di una lista finiscono allo stesso punto", len({w.larga for w in uguali}) == 1))
    for w in uguali:
        w.destroy()
    root.withdraw()
    casi.append(("le capsule si disegnano", len(L.fondi) >= 0 and L.fondo(200, "UR", False) is L.fondo(200, "UR", False)))
    casi.append(("un simbolo si legge", L.simbolo("2") is not None and L.simbolo("G/U") is not None))
    casi.append(("la cornice del tier", L.cornice("#f0ad4e") is L.cornice("#f0ad4e")))
    t_ = L.testata(root, "Izzet", 40, 40, [1, 2, 3, 4, 2, 1], None, "UR"); t_.pack(fill="x")
    d_ = L.dati(root, "A", "#5cb85c", "EXPECTED WINS", "3.34"); d_.pack(fill="x")
    root.geometry("300x200+6000+0"); root.deiconify(); root.update(); root.update()      # una finestra nascosta non si disegna: fuori schermo, non davanti a Autore
    import time as _t
    _f = _t.time() + 0.3
    while _t.time() < _f:          # la testata si disegna 20 ms dopo l'ultima larghezza (7 nov 2026)
        root.update(); _t.sleep(0.01)
    casi.append(("testata e dati si disegnano", len(t_.find_all()) > 5 and len(d_.find_all()) > 3))
    casi.append(("l'indirizzo diretto", (indirizzo("Saheeli, Jewel of Avishkar") or "").startswith("https://cards.scryfall.io/normal/") and "/art_crop/" in (indirizzo("Saheeli, Jewel of Avishkar", True) or "")))
    casi.append(("una versione Alchemy ha l'immagine di partenza", indirizzo("A-Cori-Steel Cutter") == indirizzo("Cori-Steel Cutter") and indirizzo("A-Cori-Steel Cutter") is not None))
    casi.append(("niente stampe art series al posto della carta", indirizzo("Aang, Swift Savior") is None or "art" not in indirizzo("Aang, Swift Savior").split("/")[-1]))
    casi.append(("il file dell'immagine", file_immagine("Saheeli, Jewel of Avishkar").endswith("saheeli_jewel_of_avishkar.jpg")))
    scarica_immagine("Carta Che Non Esiste")
    casi.append(("una carta sconosciuta non lascia file e non cade", "Carta Che Non Esiste" in _FALLITE and not os.path.exists(file_immagine("Carta Che Non Esiste"))))
    scarica_immagine("Icy Reception")
    ok = os.path.exists(file_immagine("Icy Reception")) and L.immagine("Icy Reception").width() == LARGO_IMG
    casi.append(("l'immagine vera arriva da Scryfall", ok))
    casi.append(("fuori dai monitor non si sposta niente", area_schermo(60000, 60000) is None))
    a_ = area_schermo(root.winfo_screenwidth() // 2, root.winfo_screenheight() // 2)
    casi.append(("l'area del monitor", a_ is not None and a_[2] > a_[0] and a_[3] > a_[1]))
    casi.append(("la carta in hover sta in un monitor da 1080", L.immagine("Icy Reception").height() + 130 <= 1040))
    scarica_immagine("Icy Reception", True)
    casi.append(("anche la sola arte", os.path.exists(file_immagine("Icy Reception", True))))
    p_ = L.carta_piena(root, "Icy Reception", "x2"); p_.pack()
    casi.append(("sotto la carta c'e' il suo testo", any(p_.type(i) == "text" and p_.itemcget(i, "text") == "x2" for i in p_.find_all())))
    v_ = L.carta_piena(root, "Carta Inventata"); v_.pack()
    t0 = time.time()
    while time.time() - t0 < 6 and "Icy Reception" not in L.piene:
        root.update(); time.sleep(0.05)
    casi.append(("la carta piena arriva e si posa sulla tela", "Icy Reception" in L.piene and any(p_.type(i) == "image" for i in p_.find_all())))
    casi.append(("una carta sconosciuta resta col suo nome", not any(v_.type(i) == "image" for i in v_.find_all())))
    prima = L.piene["Icy Reception"]
    L.pronte.append(("Icy Reception", base64.b64encode(open(file_immagine("Icy Reception"), "rb").read()))); L.radice.after(0, L.raccogli); root.update()
    casi.append(("la stessa carta due volte non spegne la prima", L.piene["Icy Reception"] is prima))
    casi.append(("la carta si cuoce al primo passaggio", os.path.exists(file_mini("Icy Reception"))))
    from PIL import Image as _I
    casi.append(("la cotta ha la misura della griglia", _I.open(file_mini("Icy Reception")).size == (LARGA_CARTA, ALTA_CARTA)))
    L.piene.clear(); t_ = time.perf_counter(); q_ = L.carta_piena(root, "Icy Reception", "x1"); t_ = time.perf_counter() - t_; q_.pack()
    casi.append(("una carta cotta compare subito, senza aspettare l'operaio", any(q_.type(i) == "image" for i in q_.find_all()) and not L.attese.get("Icy Reception") and t_ < 0.1))
    import account as _acc
    asp = _acc.ASPETTO_PUBBLICO
    _acc.ASPETTO_PUBBLICO = False       # l'aspetto di prima (MIO_ASPETTO=1): senza la riga dell'artista
    f_b = cover_mazzo("Icy Reception", 298, 168)
    _acc.ASPETTO_PUBBLICO = asp
    casi.append(("la copertina di un mazzo", _I.open(f_b).size == (298, 168)))
    casi.append(("una copertina senza arte", os.path.exists(cover_mazzo(None, 298, 168))))
    # l'app pubblica e le regole delle immagini di Scryfall (11 nov 2026): la copertina ha sotto l'arte la riga dell'artista, la carta che non hai resta a colori
    era = _acc.ASPETTO_PUBBLICO
    try:
        _acc.ASPETTO_PUBBLICO = True        # l'aspetto pubblico: dell'app pubblica e, dall'11 nov 2026, anche di quella di Autore
        f_p = cover_mazzo("Icy Reception", 298, 168)
        fascia = _I.open(f_p).convert("RGB").crop((0, 168 - FASCIA_ARTE, 298, 168))
        angolo = fascia.getpixel((297, FASCIA_ARTE - 1))           # il fondo della riga (jpg: qualche unita' di scarto)
        scritta = len(set(fascia.tobytes()[i:i + 3] for i in range(0, len(fascia.tobytes()), 3))) > 4 and all(abs(x - y) <= 4 for x, y in zip(angolo, (24, 24, 28)))
        casi.append(("pubblica: la copertina ha la riga dell'artista, un altro file", f_p != f_b and scritta and bool(artista("Icy Reception")) == bool(indirizzi())))
        L.piene.clear(); L.da_mini("Icy Reception"); q_p = L.carta_piena(root, "Icy Reception", "x0", spenta=True)
        testo_p = [q_p.itemcget(i, "text") for i in q_p.find_withtag("sotto")]
        casi.append(("pubblica: la carta che non hai e' l'immagine vera, il testo lo dice", L.immagine_tela(q_p, "Icy Reception") is L.piene["Icy Reception"]
                     and testo_p == ["x0  ·  NOT OWNED"]))
        casi.append(("l'app di Autore ha l'aspetto pubblico (11 nov 2026), a meno di MIO_ASPETTO=1", era is (os.environ.get("MIO_ASPETTO") != "1")))
        _acc.ASPETTO_PUBBLICO = False
        q_n = L.carta_piena(root, "Icy Reception", "x0", spenta=True)
        casi.append(("negativa: con l'aspetto di prima la carta che non hai resta opaca", L.immagine_tela(q_n, "Icy Reception") is not L.piene["Icy Reception"]))
    finally:
        _acc.ASPETTO_PUBBLICO = era
    L.attese.update(A=[], B=[]); L.solo(["A"])
    casi.append(("scorrendo si aspetta solo chi e' a vista", "A" in L.attese and "B" not in L.attese))
    L.piene.update({f"finta {i}": None for i in range(201)}); L.solo(["finta 3"])
    casi.append(("le immagini in memoria hanno un tetto", list(L.piene) == ["finta 3"]))
    L.nuova_pagina()
    casi.append(("la pagina nuova svuota la coda", not L.coda and not L.attese))
    rgb = [tuple(int(COLORI[k][i:i + 2], 16) for i in (1, 3, 5)) for k in COLORI]
    casi.append(("la sfumatura con numpy ha gli stessi pixel di quella di prima", all(sfumatura(a, b, A, sp).tobytes() == sfumatura_lenta(a, b, A, sp).tobytes()
                                                                                    for a in rgb for b in rgb for sp in (False, True) for A in (40, 52))))
    casi.append(("negativa: un colore diverso da' pixel diversi", sfumatura(rgb[0], rgb[1], 40, False).tobytes() != sfumatura_lenta(rgb[0], rgb[2], 40, False).tobytes()))
    root.destroy()
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
