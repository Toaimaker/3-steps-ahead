"""Il mazzo a carte intere su un tavolo (Autore, 9 nov 2026: «aggiungiamo un pulsante che ci permette di vedere il mazzo non piu' per pillows ma per carte in un nuovo
spazio dove possiamo muoverle, spostarle impilarle / un'area grande per il mazzo sotto e una piu' stretta per la sideboard sopra»).

Una tela sola, due zone: in alto la fascia stretta della sideboard (col comandante e il compagno, fermi), sotto l'area grande del mazzo. Le carte sono immagini con gli angoli
arrotondati in antialias e un'ombra morbida, in pile sfalsate quanto basta per leggere nome e costo.
Una carta per nome, non una per copia (stesso giorno: «invece di mettere ogni copia di una carta, mettiamo un counter su ogni carta che ci permette di aumentare fino a 4 la sua
tiratura nel mazzo / in tutti i mazzi accanto a ogni carta avremo un numero che indica quante ne abbiamo inserite cosi' anche da sovrapposte sappiamo la quantita' accanto al
nome / se clicco su una carta in mezzo a una colonna, la colonna si espande e mi mostra la carta con il suo counter»):
- accanto al nome, sul bordo sinistro della carta, il numero delle copie: si legge anche nella pila;
- sulle carte intere (l'ultima di ogni pila, o quella aperta) il contatore − N +, nei mazzi che si cambiano (Wishlist e Deck building): fino al limite del formato
  (4, 1 nel Brawl, senza limite le basi e le carte «any number», `costruttore_mazzi.limite`), contando mazzo e sideboard insieme; a 0 la carta esce;
- un clic su una carta in mezzo a una pila apre la pila: quella carta si vede intera col suo contatore, le altre scendono; un altro clic la richiude.
Trascinare sposta la carta con tutte le copie (Maiuscolo: tutta la pila); lasciata su una pila ci si impila, altrove fa una pila nuova; fra fascia e area passa fra mazzo e
sideboard. Il doppio clic passa UNA copia dall'altra parte. Una carta e' una sola per zona: arrivando dove c'e' gia', le copie si sommano.
Il mazzo della Wishlist o di Deck building cambia davvero (mazzi_salvati); uno di Arena o del meta no: li' e' solo la disposizione, e la testata lo dice.
La disposizione resta, mazzo per mazzo, in Log_Arena/tavoli_mazzi.json; se la lista nel frattempo e' cambiata si riparte per costo.
Anche nel builder (stesso giorno: «questa option la voglio anche nell'editor di creazione mazzo, solo che anche qui posso trascinare dentro le carte direttamente dalla
collezione o avere una tab di ricerca veloce per i nomi»): il pulsante Card view del builder apre il tavolo sopra il builder, alla sua misura, cosi' a sinistra resta la
Collection. Il tavolo lavora sul mazzo del builder (editore): ogni cambio passa al builder, e ogni cambio del builder torna sul tavolo (allinea). Una carta trascinata dalla
Collection cade dove la lasci (sulla pila sotto il mouse, nella fascia in sideboard); la casella Add card cerca per nome fra le carte del formato: Invio la mette nel mazzo,
Maiuscolo+Invio in sideboard.
Le connessioni padre -> figlio (stesso giorno, Autore: «quando premo synergies si blocca, ascolta fa cosi' togli il meccanismo di synergies, metti un pallino sotto
le carte e tirando quel pallino posso agganciarle ad altre, la prima carta e' padre e chi riceve il pallino e' figlio, lo strumento impara sinergie guardando le connessioni
tra padre e figlio»): niente pulsante ne' pannello. Sotto ogni carta che si vede intera un pallino d'oro: tirato su un'altra carta fa la connessione dal padre al figlio,
una freccia d'oro dritta da pallino a pallino (una carta coperta nella pila con una freccia ha il pallino piccolo sul bordo destro della barra del nome), che
segue la carta mentre la trascini; rifatta, la toglie, e la toglie anche la ✕ che compare a meta' della freccia sotto il puntatore (o il tasto destro). Il ⇄ accanto
al pallino, nei mazzi che si cambiano, sostituisce la carta con una della collezione (prima quelle che hai). Il foglio non ha bordi: il pan col tasto centrale va ovunque e le carte si lasciano anche a sinistra e sopra.
Ogni punto di una carta la prende (anche dove una freccia le passa vicino): il punto si cerca nella geometria delle pile, non nei pezzi disegnati. Per una carta coperta nella pila: un clic la apre e ha il suo pallino. Le connessioni e cosa ne impara lo strumento
stanno in `rete_sinergie.py`.
Il foglio (stesso giorno: «dammi la possibilita' di zoomare sul foglio / togli size sml e semplicemente fammi alzare la barra di separazione tra foglio e sideboard /
se riduco la sideboard le carte si rimpiccioliscono fino a sparire se tolgo tutto lo spazio della sideboard / possiamo usare un segno sulla linea tra foglio e
sideboard per indicare dove trascinare su o giu' / movimento libero nel foglio, vincolato con snap solo se impilo le carte e con semplice de snap, se le trascino
via l'una dall'altra, si slegano»): lo zoom del foglio con la rotella (intorno al puntatore) o con − % + Fit nella testata, il pan col tasto centrale; la fascia della sideboard si alza e
si abbassa trascinando la barra col segno ▲▼, e le sue carte prendono la scala che ci sta, fino a sparire; le carte si muovono libere sul foglio e si impilano
solo se le lasci sopra un'altra pila, tirate fuori dalla pila se ne staccano. Zoom e fascia si salvano con la disposizione.
`--prova` (fuori schermo): pile, contatore e limiti, colonna aperta, trascinamenti, cambio di zona, salvataggio e ripresa, il builder, lo zoom, la fascia, il pallino padre -> figlio, con le negative."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import collections
import json
import math
import threading

import capsule as CAP
import disegni as DG
import mazzi_salvati as MS
import menu_board as MB
import piattaforma
import rete_sinergie as RS
import tela_gpu as TG

from tema import CI as C, FN, barra_scura
from widget import VERDE_P, pronta_poi, pulsante_solido
GRIGIO_T = ("#3a3a40", "#4a4a52", "#2c2c30")       # i pulsanti grigi della testata (Undo, Redo, Full page, lo zoom): stile S3, 14 nov 2026

import account as _ACC  # noqa: E402
FILE = _ACC.lega(globals(), "FILE", "tavoli_mazzi.json")     # Log_Arena/tavoli_mazzi.json; nell'app pubblica uno per account (10 nov 2026, Magic 12)
BASE_W = 146                    # la carta a zoom 1; le posizioni si salvano in questa scala
SCALE = dict(S=0.8, M=1.0, L=1.25)      # le grandezze del primo giro: una disposizione salvata allora riprende il suo zoom
ZOOM_MIN, ZOOM_MAX = 0.3, 2.0
ZOOM_VISTA = 0.12                # A, l'apertura e il filtro possono scendere fin qui per far stare tutto un foglio grande (la rotella si ferma a ZOOM_MIN)
FASCIA_DEF = 250                # l'altezza della fascia della sideboard all'apertura, in pixel
SPARISCE = 0.16                 # sotto questa scala le carte della fascia non si disegnano piu'

MAX_PILA = 10                   # oltre, la pila si divide (o si allunga, se il mazzo non sta in una riga)
MARGINE, SPAZIO = 22, 20        # dal bordo, fra le pile (il numero delle copie sporge a sinistra della carta)
ETICHETTA = 30                  # la riga del titolo di una zona
APERTA = 8                      # lo spazio sotto la carta aperta in mezzo a una pila
# le label (Autore, 9 nov 2026: «la possibilita' di creare delle label di carte dentro le quali diamo un nome: es le carte in una label sono le carte finisher»;
# scelta «riquadro sul foglio»): un riquadro col nome in alto, sotto le carte; misure in coordinate del mazzo (scala 1)
LARGO_OUT, RIGA_OUT = 236, 20     # l'outliner: la larghezza e l'altezza di una riga
OCCHIO_OUT = 20                    # la colonna degli occhi, a sinistra dell'outliner (13 nov 2026)
FG_AIUTO, FG_DICI = "#ffffff", "#fff2c4"
INFO_L, INFO_H, TESTA_HUD = 236, 84, 22     # l'HUD delle carte e della curva, in alto a destra sul foglio: larghezza, corpo, testa
FONDO_HUD = (16, 16, 20, 168)       # lo sfondo semitrasparente dell'HUD      # il testo sulla testa azzurra dei comandi: il titolo e cosa e' appena successo
TIT_L, PAD_L = 26, 18           # l'altezza del titolo, l'aria intorno alle pile quando la label nasce
FONDO_L, TESTA_L, BORDO_L, SEGNO_L = "#121722", "#18202c", "#4a5262", "#6d7686"      # i colori del redesign del 14 nov 2026 (erano grigi ArtStation)
FOGLIO, PUNTINO, PASSO_PUNTI = "#0b0e13", "#232c3b", 24     # il foglio a puntini del redesign: il fondo, il puntino, il passo a zoom 1
R_PUNTO = 7                     # il raggio del dot di una linea, in pixel
GRIGIO_L = "#6a6a76"            # il colore di una label nuova
CONT_PIENO, CONT_MINIMO = 108, 40       # la carta (pixel) da cui il contatore e' intero (− N +), e sotto cui non c'e' (13 nov 2026)
STRUMENTI_MIN = 90              # sotto questa larghezza della carta, alla base resta solo il pallino d'oro (⇄ e + nota quando ti avvicini)
OPZIONI = "_opzioni"            # nel file delle disposizioni: le preferenze del tavolo (non e' un mazzo)
# i comandi del tavolo: solo nella finestrella in basso a destra (Autore, 10 nov 2026: «il menu dei comandi deve esistere solo e unicamente in basso a destra
# come piccola finestra»); prima erano una riga sotto la testata
COMANDI = (("Wheel", "zoom"), ("Middle-drag", "pan"), ("Drag a card", "move · drop on a pile stacks"), ("Shift+drag", "the whole pile"),
           ("Click", "opens a pile"), ("Double-click", "one copy across"), ("Gold dot → card", "parent → child"), ("Click a line", "color and weight"),
           ("✕ · right-click", "unlink"), ("Pin · double-click a line", "adds a dot"), ("Drag on the empty sheet", "select"), ("≡ in the frame", "label: name, color"),
           ("A", "frame the whole network"), ("F", "frame the selection (or the card picked in the outliner)"), ("Esc", "clear the selection, then close"))
COMANDI_MOD = (("− +", "copies"), ("⇄", "replace the card"), ("Ctrl+Z · Ctrl+Y", "undo · redo (also Ctrl+Shift+Z)"),
               ("Save", "nothing is saved by itself: Save writes the deck and the board"), ("+ note beside the gold dot", "a note on the card"),
               ("+ note on a group title", "a note on the group"), ("Groups ▾", "new group, groups from your games, every group with its ≡, lock and tidy"))
COMANDI_VISTA = (("Wheel", "zoom"), ("Middle-drag", "pan"), ("Drag a card", "move it (deck and sideboard stay as they are)"), ("Click", "opens a pile, selects the card"),
                 ("A", "frame the whole network"),
                 ("F", "frame the selection"), ("Hover", "the card large"), ("Edit the deck", "to change the board"), ("Esc", "close"))
_FOTO = {}                      # (nome, larghezza) -> PhotoImage: le carte gia' pronte, fra un'apertura e l'altra
_CHIAVE = threading.Lock()


def misure(s):
    """Larghezza, altezza, sfalsamento della pila e ombra alla scala s. Lo sfalsamento lascia leggere nome e costo della carta sotto (il 12,5% dell'altezza)."""
    w = round(BASE_W * s)
    h = round(w * CAP.ALTA_CARTA / CAP.LARGA_CARTA)
    return w, h, round(h * 0.125), max(4, round(7 * s))


# la griglia del foglio (Autore, 10 nov 2026: «facciamo che il movimento e' libero ma poi si allineano come se fossero su una griglia regolare»): in orizzontale
# una colonna e' una carta piu' lo spazio fra le pile, in verticale il passo con cui le carte si sfalsano in una pila; in coordinate del mazzo (scala 1)
PASSO_X = BASE_W + SPAZIO
PASSO_Y = misure(1.0)[2]


# la griglia piu' fitta (12 nov 2026, Autore: «ridimensioniamo la grid sulla quale dovrebbero snappare le carte, rendiamola piu' fitta: dimensione adatta a fare
# in modo che una carta sia compresa in uno specifico range di quadratini della griglia e che quindi non snappi in disordine»): quadratini quasi quadrati, 12 per
# colonna (una carta e lo spazio fra le pile: 166 / 12 = 13,8 pixel) e 2 per passo verticale (26 / 2 = 13). Una carta occupa sempre le stesse 12 colonne di
# quadratini; la disposizione per costo e la rete restano sulla griglia di prima, che e' fatta degli stessi quadratini.
CELLE_X, CELLE_Y = 12, 2
CELLA_X, CELLA_Y = PASSO_X / CELLE_X, PASSO_Y / CELLE_Y


def a_griglia(x, y, mezza=False):
    """Il quadratino della griglia piu' vicino (mezza: tenuta per chi la passa; i quadratini sono gia' piu' fitti di meta' colonna)."""
    return MARGINE + round((x - MARGINE) / CELLA_X) * CELLA_X, round(y / CELLA_Y) * CELLA_Y


def carica_tavoli(f=None):
    try:
        with open(f or FILE, encoding="utf-8") as g:
            return json.load(g)
    except (OSError, ValueError):
        return {}


def salva_tavolo(chiave, dato, f=None):
    if f is None and _ACC.sola_lettura():       # All accounts: il Board si guarda e basta
        return
    f = f or FILE
    with _CHIAVE:
        d = carica_tavoli(f)
        d[chiave] = dato
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "w", encoding="utf-8") as g:
            json.dump(d, g, ensure_ascii=False, indent=1)
        os.replace(f + ".tmp", f)


def cuoci_carta(nome, s):
    """La carta intera alla scala s come immagine PIL: angoli arrotondati (maschera a 3x ridotta: niente scalini) e un'ombra morbida sotto. -> (PIL, ombra p) o None
    se l'immagine non c'e' ancora."""
    w, h, _off, p = misure(s)
    src = next((f for f in ((CAP.file_mini(nome), CAP.file_immagine(nome)) if w <= 200 else (CAP.file_immagine(nome), CAP.file_mini(nome))) if os.path.exists(f)), None)
    if src is None:
        return None
    from PIL import Image, ImageDraw, ImageFilter
    try:
        im = Image.open(src).convert("RGBA").resize((w, h), Image.LANCZOS)
    except Exception:
        return None
    m = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=round(w * 3 * 0.047), fill=255)
    im.putalpha(m.resize((w, h), Image.LANCZOS))
    tela = Image.new("RGBA", (w + 2 * p, h + 2 * p), (0, 0, 0, 0))
    ombra = Image.new("L", tela.size, 0)
    ImageDraw.Draw(ombra).rounded_rectangle((p, p + p // 3, p + w - 1, p + h - 1 + p // 3), radius=round(w * 0.047), fill=170)
    nera = Image.new("RGBA", tela.size, (0, 0, 0, 255))
    nera.putalpha(ombra.filter(ImageFilter.GaussianBlur(p / 2.2)))
    tela = Image.alpha_composite(tela, nera)
    tela.alpha_composite(im, (p, p))
    return tela, p


def foto_carta(tk, nome, s):
    """La carta alla scala s come PhotoImage (la tela di Tk), con la sorgente registrata anche per la scheda. None se l'immagine non c'e' ancora."""
    w, _h, _off, _p = misure(s)
    k = (nome, w)
    if k in _FOTO:
        return _FOTO[k]
    c = cuoci_carta(nome, s)
    if c is None:
        return None
    from PIL import ImageTk
    _FOTO[k] = TG.registra(ImageTk.PhotoImage(c[0]), c[0])
    if len(_FOTO) > 600:
        for x in list(_FOTO)[:200]:
            TG.dimentica(_FOTO.pop(x))
    return _FOTO[k]


_FOTO_2X = {}       # nome -> (chiave della texture, ombra): sulla scheda una carta si cuoce una volta sola, a 2x, e la scheda la scala a ogni zoom


def foto_gpu(nome):
    """La carta per la tela sulla scheda video: cotta una volta a scala 2 (nitida fino allo zoom 200%), poi la scheda la scala (con le mipmap). -> (chiave, ombra a 2x)
    o None se l'immagine non c'e' ancora. Prima ogni scatto di zoom rifaceva le immagini di tutte le carte: 135-171 ms."""
    if nome in _FOTO_2X:
        return _FOTO_2X[nome]
    c = cuoci_carta(nome, 2.0)
    if c is None:
        return None
    _FOTO_2X[nome] = (TG.registra_pil(f"carta2x:{nome}", c[0]), c[1])
    return _FOTO_2X[nome]


RIGA_COPIA = 24       # la riga di una carta in un gruppo duplicato (scala 1)
TIPI = (("all", "All"), ("creature", "Creatures"), ("instant", "Instants"), ("sorcery", "Sorceries"), ("enchantment", "Enchantments"),
        ("artifact", "Artifacts"), ("planeswalker", "Planeswalkers"), ("land", "Lands"), ("battle", "Battles"))
_TIPO_ARENA = {}


def tipo_arena(nome):
    """La riga del tipo di una carta dal database delle carte di Arena (per nome, la prima faccia), quando carte_db non ce l'ha."""
    if not _TIPO_ARENA:
        try:
            import db_carte
            t = db_carte.testi()
            for c in db_carte.carte():
                n = t.get(c.get("titleId"))
                if n:
                    _TIPO_ARENA.setdefault(n.split(" // ")[0].strip().lower(), t.get(c.get("cardTypeTextId")) or "")
        except Exception:       # noqa: BLE001 - senza database niente tipo: la carta resta con All
            _TIPO_ARENA["?"] = ""
    return _TIPO_ARENA.get((nome or "").split(" // ")[0].strip().lower(), "")


_COL_RAR_ARENA = {}
COLORI_ARENA = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}      # i numeri dei colori nel database di Arena


def colore_rarita_arena(nome):
    """(colori «WUBRG», rarita' 1-5) di una carta per nome dal database di Arena, per gli Arrange per colore e per rarita' (13 nov 2026). La rarita' e' la piu'
    bassa fra le stampe, come il jolly (dati_app.rarita_nome): 2 comune, 3 non comune, 4 rara, 5 mitica, 1 terra base. Le stampe ribilanciate di Alchemy, le
    pedine e le seconde facce non contano. Una carta che il database non ha: ("", None)."""
    if not _COL_RAR_ARENA:
        try:
            import db_carte
            t = db_carte.testi()
            for c in db_carte.carte():
                if c.get("IsRebalanced") or c.get("isToken") or c.get("isSecondaryCard"):
                    continue
                n = t.get(c.get("titleId"))
                if not n:
                    continue
                k = n.split(" // ")[0].strip().lower()
                col = "".join(COLORI_ARENA[x] for x in sorted(c.get("colors") or []) if x in COLORI_ARENA)
                r = c.get("rarity") if c.get("rarity") in (1, 2, 3, 4, 5) else None
                v = _COL_RAR_ARENA.setdefault(k, ["", None])
                if col and not v[0]:
                    v[0] = col
                if r is not None and (v[1] is None or r < v[1]):
                    v[1] = r
        except Exception:       # noqa: BLE001 - senza database ogni carta resta incolore e senza rarita': l'Arrange la mette in fondo
            _COL_RAR_ARENA["?"] = ["", None]
    return tuple(_COL_RAR_ARENA.get((nome or "").split(" // ")[0].strip().lower(), ("", None)))


CARTELLA_TIPI = os.path.join(percorsi.GRAFICA, "tipi")


def icona_svg(f, lato, colore):
    """Un svg a un colore solo (i simboli del font Mana) reso con PyMuPDF a 4x, ridotto col Lanczos e tinto di colore. -> PhotoImage (registrata per la tela
    sulla scheda video), o None se non si puo'."""
    try:
        import re
        import fitz
        from PIL import Image, ImageTk
        testo = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', 'fill="#000000"', open(f, encoding="utf-8").read())
        pg = fitz.open(stream=testo.encode("utf-8"), filetype="svg")[0]
        z = lato * 4 / max(pg.rect.width, pg.rect.height)
        pm = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True)
        a = Image.frombytes("RGBA", (pm.width, pm.height), pm.samples).getchannel("A").resize((lato, lato), Image.LANCZOS)
        out = Image.new("RGBA", (lato, lato), tuple(int(colore[i:i + 2], 16) for i in (1, 3, 5)) + (0,))
        out.putalpha(a)
        ft = ImageTk.PhotoImage(out)
        import tela_gpu
        tela_gpu.registra(ft, out)
        return ft
    except Exception:       # noqa: BLE001 - senza PyMuPDF o con un file rotto: chi chiama usa il disegno nostro
        return None


def icona_tipo(tipo, lato=18, colore="#d7dce5"):
    """L'icona di un tipo di carta: i simboli originali dei tipi (Autore, 12 nov 2026: «qui voglio i loghi originali»), gli svg del font Mana di Andrew Gioia
    (github.com/andrewgioia/mana; i simboli sono di Wizards of the Coast), in Companion/Grafica/tipi. La battaglia nel font non c'e': resta lo scudo disegnato
    da noi, come ogni tipo il cui file manca o non si legge."""
    f = os.path.join(CARTELLA_TIPI, tipo + ".svg")
    chiave = ("icona_tipo_svg", tipo, lato, colore)
    if os.path.exists(f):
        if chiave not in DG.CACHE:
            DG.CACHE[chiave] = icona_svg(f, lato, colore)
        if DG.CACHE[chiave] is not None:
            return DG.CACHE[chiave]

    def fa():
        d = DG.Disegno(lato, lato)
        k = lato / 20
        P = lambda pts: [(x * k, y * k) for x, y in pts]
        if tipo == "creature":          # tre graffi d'artiglio
            for dx in (0, 4.5, 9):
                d.linea(P([(4 + dx, 17), (8 + dx, 3)]), colore, 2.2 * k)
        elif tipo == "instant":         # il fulmine
            d.poligono(P([(12, 1), (4, 11), (9, 11), (7, 19), (16, 8), (11, 8), (13, 1)]), riempi=colore)
        elif tipo == "sorcery":         # la fiamma
            d.poligono(P([(10, 1), (14, 7), (16, 12), (14, 17), (10, 19), (6, 17), (4, 12), (6, 7), (8, 10)]), riempi=colore)
        elif tipo == "enchantment":     # il sole: un cerchio e otto raggi
            d.cerchio(10 * k, 10 * k, 3.6 * k, riempi=colore)
            import math
            for a in range(8):
                r0, r1 = 5.8, 9.2 if a % 2 == 0 else 8.0
                ca, sa = math.cos(a * math.pi / 4), math.sin(a * math.pi / 4)
                d.linea(P([(10 + r0 * ca, 10 + r0 * sa), (10 + r1 * ca, 10 + r1 * sa)]), colore, 1.6 * k)
        elif tipo == "artifact":        # l'anfora
            d.poligono(P([(7, 2), (13, 2), (12, 5), (15, 9), (14, 15), (11, 18), (9, 18), (6, 15), (5, 9), (8, 5)]), riempi=colore)
        elif tipo == "planeswalker":    # la scintilla: una lama verticale e due ali
            d.poligono(P([(10, 1), (12, 8), (10, 19), (8, 8)]), riempi=colore)
            d.poligono(P([(3, 6), (8, 9), (8, 13)]), riempi=colore)
            d.poligono(P([(17, 6), (12, 9), (12, 13)]), riempi=colore)
        elif tipo == "land":            # i monti
            d.poligono(P([(1, 17), (7, 6), (10, 11), (13, 4), (19, 17)]), riempi=colore)
        elif tipo == "battle":          # lo scudo
            d.poligono(P([(10, 1), (17, 4), (16, 12), (10, 19), (4, 12), (3, 4)]), riempi=colore)
        else:
            d.cerchio(10 * k, 10 * k, 6 * k, bordo=colore, larghezza=1.6 * k)
        return d
    return DG._icona(("icona_tipo", tipo, lato, colore), fa)


def segno_nota(lato=20, piena=True):
    """Il foglietto della nota (12 nov 2026): un foglio ambra con l'angolo piegato e tre righe; vuoto (solo il bordo e un +) per farne una nuova. Antialias."""
    def fa():
        d = DG.Disegno(lato, lato)
        k = lato / 20
        amb, scuro = (240, 173, 78, 255), (42, 34, 20, 255)
        foglio = [(3 * k, 2 * k), (13 * k, 2 * k), (17 * k, 6 * k), (17 * k, 18 * k), (3 * k, 18 * k)]
        if piena:
            d.poligono(foglio, riempi=amb)
            d.poligono([(13 * k, 2 * k), (13 * k, 6 * k), (17 * k, 6 * k)], riempi=(190, 128, 50, 255))
            for y in (9, 12, 15):
                d.linea([(6 * k, y * k), (14 * k, y * k)], scuro, 1.4 * k, tondo=False)
        else:
            d.poligono(foglio, riempi=(32, 32, 36, 230), bordo=amb, larghezza=1.4 * k)
            d.linea([(10 * k, 7 * k), (10 * k, 15 * k)], amb, 1.6 * k)
            d.linea([(6 * k, 11 * k), (14 * k, 11 * k)], amb, 1.6 * k)
        return d
    return DG._icona(("segno_nota", lato, piena), fa)


def pallino_nodo(lato=16):
    """Il pallino delle carte: un tondo d'oro col bordo scuro e un punto chiaro nel mezzo (antialias); 16 pixel alla base, 10 sulla barra del nome."""
    def fa():
        d = DG.Disegno(lato, lato)
        c = lato / 2
        d.cerchio(c, c, c - 0.8, riempi=(214, 172, 46, 255), bordo=(16, 16, 20, 255), larghezza=1.4 if lato > 12 else 1.1)
        d.cerchio(c, c, lato * 0.15, riempi=(255, 244, 205, 255))
        return d
    return DG._icona(("pallino_nodo", lato), fa)


def pallino_punto(lato=14):
    """Il dot di una linea (come in Nuke): un tondo scuro col bordo grigio perlato e il centro chiaro."""
    def fa():
        d = DG.Disegno(lato, lato)
        c = lato / 2
        d.cerchio(c, c, c - 0.8, riempi=(34, 34, 40, 255), bordo=(201, 202, 208, 255), larghezza=1.6)
        d.cerchio(c, c, lato * 0.16, riempi=(230, 231, 236, 255))
        return d
    return DG._icona(("pallino_punto", lato), fa)


def segno_chiodo(lato=20):
    """Il chiodo sulla freccia accesa (Autore, 10 nov 2026: «fai che il dot si aggiunga con un nodo chiodo»): mette un dot sulla linea in quel punto.
    Un tondo scuro col bordo perlato, dentro la testa del chiodo e il gambo."""
    def fa():
        d = DG.Disegno(lato, lato)
        c = lato / 2
        d.cerchio(c, c, c - 0.8, riempi=(30, 30, 36, 255), bordo=(201, 202, 208, 255), larghezza=1.4)
        d.linea([(c, c - lato * 0.06), (c, c + lato * 0.28)], (230, 231, 236, 255), larghezza=1.8)
        d.cerchio(c, c - lato * 0.14, lato * 0.15, riempi=(230, 231, 236, 255))
        return d
    return DG._icona(("segno_chiodo", lato), fa)


def segno_menu(lato=26):
    """Le tre linee del menu (al centro della cornice della selezione e sul titolo della label): un quadrato scuro col bordo azzurro e tre linee chiare."""
    def fa():
        d = DG.Disegno(lato, lato)
        d.rett(0.8, 0.8, lato - 0.8, lato - 0.8, riempi=(24, 26, 32, 240), bordo=(36, 186, 255, 255), larghezza=1.4, raggio=lato * 0.18)
        for k in (0.34, 0.5, 0.66):
            d.linea([(lato * 0.28, lato * k), (lato * 0.72, lato * k)], (235, 236, 240, 255), larghezza=1.8)
        return d
    return DG._icona(("segno_menu", lato), fa)


def mescola(c1, c2, k):
    """Il colore c1 portato verso c2 di k (0..1)."""
    a, b = c1.lstrip("#"), c2.lstrip("#")
    return "#%02x%02x%02x" % tuple(round(int(a[i:i + 2], 16) * (1 - k) + int(b[i:i + 2], 16) * k) for i in (0, 2, 4))


def croce(lato=12):
    """La ✕ disegnata (sulla scheda il font non ha il segno): due tratti grigi in antialias."""
    def fa():
        d = DG.Disegno(lato, lato)
        b = lato * 0.22
        d.linea([(b, b), (lato - b, lato - b)], (170, 170, 180, 255), larghezza=1.6)
        d.linea([(b, lato - b), (lato - b, b)], (170, 170, 180, 255), larghezza=1.6)
        return d
    return DG._icona(("croce", lato), fa)


def segno_x(lato=20):
    """La ✕ che toglie una connessione: un tondo scuro col bordo d'oro e la croce chiara (antialias)."""
    def fa():
        d = DG.Disegno(lato, lato)
        c = lato / 2
        d.cerchio(c, c, c - 0.8, riempi=(30, 22, 18, 255), bordo=(214, 172, 46, 255), larghezza=1.4)
        b = lato * 0.2
        d.linea([(c - b, c - b), (c + b, c + b)], (255, 236, 200, 255), larghezza=1.8)
        d.linea([(c - b, c + b), (c + b, c - b)], (255, 236, 200, 255), larghezza=1.8)
        return d
    return DG._icona(("segno_x", lato), fa)


def segno_stile(lato=20):
    """Sulla freccia accesa, accanto alla ✕: il tondo coi tre colori che apre la tavolozza della linea (colore e importanza)."""
    def fa():
        d = DG.Disegno(lato, lato)
        c = lato / 2
        d.cerchio(c, c, c - 0.8, riempi=(30, 30, 36, 255), bordo=(201, 202, 208, 255), larghezza=1.4)
        r = lato * 0.12
        for k, col in enumerate(((214, 172, 46, 255), (36, 186, 255, 255), (217, 83, 79, 255))):
            a = math.pi / 2 + k * 2 * math.pi / 3
            d.cerchio(c + lato * 0.2 * math.cos(a), c - lato * 0.2 * math.sin(a), r, riempi=col)
        return d
    return DG._icona(("segno_stile", lato), fa)


def chiaro(col, k=0.55):
    """Il colore schiarito verso il bianco (la freccia sotto il puntatore)."""
    c = col.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return "#%02x%02x%02x" % tuple(round(x + (255 - x) * k) for x in (r, g, b))


def segno_scambia(lato=16):
    """Il ⇄ sotto la carta: un tondo scuro col bordo azzurro e due frecce opposte (antialias)."""
    def fa():
        d = DG.Disegno(lato, lato)
        c = lato / 2
        d.cerchio(c, c, c - 0.8, riempi=(24, 24, 28, 255), bordo=(36, 186, 255, 255), larghezza=1.2)
        b, h = lato * 0.26, lato * 0.13
        bianco = (230, 240, 250, 255)
        d.linea([(c - b, c - h), (c + b * 0.55, c - h)], bianco, larghezza=1.3)
        d.poligono([(c + b, c - h), (c + b * 0.45, c - h - lato * 0.12), (c + b * 0.45, c - h + lato * 0.12)], riempi=bianco)
        d.linea([(c + b, c + h), (c - b * 0.55, c + h)], bianco, larghezza=1.3)
        d.poligono([(c - b, c + h), (c - b * 0.45, c + h - lato * 0.12), (c - b * 0.45, c + h + lato * 0.12)], riempi=bianco)
        return d
    return DG._icona(("segno_scambia", lato), fa)


def segno_barra():
    """Il segno sulla barra fra fascia e foglio: una pillola scura col bordo e i due triangoli ▲▼ disegnati (antialias), che dice «trascinami su e giu'»."""
    def fa():
        d = DG.Disegno(60, 18)
        d.rett(0.5, 0.5, 59.5, 17.5, riempi=(32, 32, 36, 255), bordo=(120, 120, 128, 255), larghezza=1.0, raggio=8.5)
        for cx in (22, 38):
            d.poligono([(cx - 4.5, 7.5), (cx + 4.5, 7.5), (cx, 3)], riempi=(220, 220, 226, 255))      # su
            d.poligono([(cx - 4.5, 10.5), (cx + 4.5, 10.5), (cx, 15)], riempi=(220, 220, 226, 255))    # giu'
        return d
    return DG._icona(("segno_barra",), fa)


def pillola(l, h, riempi, bordo=None):
    """Una pillola arrotondata in antialias (disegni.py), fatta una volta per misura e colori."""
    def fa():
        d = DG.Disegno(l, h)
        d.rett(0.5, 0.5, l - 0.5, h - 0.5, riempi=riempi, bordo=bordo, larghezza=1.0, raggio=h / 2 - 0.5)
        return d
    return DG._icona(("pillola", l, h, riempi, bordo), fa)


def tondo_segno(lato, riempi, segno, colore):
    """Il bottone tondo del contatore, col meno o col piu' disegnati (non scritti: centrati)."""
    def fa():
        d = DG.Disegno(lato, lato)
        d.cerchio(lato / 2, lato / 2, lato / 2 - 0.5, riempi=riempi)
        b = lato * 0.27
        d.linea([(lato / 2 - b, lato / 2), (lato / 2 + b, lato / 2)], colore, larghezza=max(1.6, lato / 11))
        if segno == "+":
            d.linea([(lato / 2, lato / 2 - b), (lato / 2, lato / 2 + b)], colore, larghezza=max(1.6, lato / 11))
        return d
    return DG._icona(("tondo_segno", lato, riempi, segno, colore), fa)


class TavoloCarte:
    """La finestra del tavolo. main, side, comandante, compagno: {nome: copie}. carte_db: {nome: dict(cmc, tipo, testo)}. modificabile: (sezione, id) di mazzi_salvati, o None.
    formato: per il limite delle copie. al_cambio(lista, side): chiamata quando il mazzo cambia (solo se modificabile). alla_fine(): chiuso il tavolo, se il mazzo e' cambiato."""

    def __init__(self, tk, F, padre, nome, main, side, comandante=None, compagno=None, carte_db=None, chiave=None, modificabile=None, al_cambio=None,
                 file_tavoli=None, file_mazzi=None, fuori=False, alla_fine=None, formato="Standard", limite=None, editore=None, nomi_ricerca=None, geometria=None,
                 chiave_rete=None, file_rete=None, chiave_vecchia=None, sola_lettura=False, salvataggio=None):
        self.tk, self.F = tk, F
        # niente salvataggi automatici in modalita' edit (Autore, 12 nov 2026: «le schede mazzo e la board di editor dei deck non deve autosalvare i cambiamenti»,
        # «nella board editor vogliamo i pulsanti save, undo (ctrl z), redo»): ogni gesto entra nello storico (Undo e Redo), il file si scrive solo con Save.
        # salvataggio: il Save del builder (salva il mazzo, poi chiama scrivi_tutto qui)
        self.salvataggio = salvataggio
        self.storia, self.passo, self.salvato_a = [], -1, 0
        self.nome, self.carte_db, self.formato = nome or "Deck", carte_db or {}, formato
        self.chiave, self.modificabile, self.al_cambio, self.alla_fine = chiave, modificabile, al_cambio, alla_fine
        self.chiave_vecchia = chiave_vecchia      # dove stava la disposizione prima (il builder la teneva a parte: «builder:<id>»)
        self.file_tavoli, self.file_mazzi = file_tavoli, file_mazzi
        self._limite = limite
        self.editore = editore              # il builder: riceve (lista, side) a ogni cambio, e salva lui
        self.nomi_ricerca = nomi_ricerca    # i nomi per la ricerca veloce (una funzione: si leggono quando servono)
        # sola lettura: il Board aperto dalla finestra del mazzo, da guardare (Autore, 10 nov 2026: «non avra' i tool di editing del mazzo, quelli si usano solo
        # dopo essere entrati nella modalita' edit», «sara' personalizzabile solo dopo essere andati in modalita' edit»): zoom, pan, una pila che si apre, la carta
        # grande; niente pallini, contatori, ⇄, connessioni, dot, label, selezione, Arrange network, Grid snap; la disposizione non si salva
        self.sola = bool(sola_lettura) or _ACC.sola_lettura()       # All accounts: sempre in sola lettura (10 nov 2026)
        # in sola lettura le carte si spostano lo stesso, e la disposizione resta (Autore, 10 nov 2026: «e' vero che non abbiamo le funzioni di edit ma le carte
        # possono cmq essere spostate e trascinate in giro»): una carta non cambia zona, il mazzo non cambia. Con All accounts no: li' non si salva niente
        self.sposta = bool(sola_lettura) and not _ACC.sola_lettura()
        self.modifica = bool(modificabile or editore) and not self.sola
        # le connessioni padre -> figlio: le stesse per lo stesso mazzo, dalla scheda e dal builder (chiave_rete)
        self.rete = RS.Rete(chiave_rete if chiave_rete is not None else chiave, file_rete)
        self.rete.in_memoria = self.modifica        # in modalita' edit la rete si scrive solo con Save
        self.tira, self._img_rete, self._segmenti, self._arco = None, None, [], None
        self._xy = None             # il punto della tela dell'ultimo clic o movimento: da li' si cerca la carta
        self._fine_drag = 0.0       # quando e' finito l'ultimo trascinamento (la carta grande non salta fuori subito dopo)
        self.cambiato = False
        self._da_inquadrare = False      # l'inquadratura dell'apertura, finche' la tela non ha la sua misura
        self.voci = {}          # id -> dict(nome, zona, q): una carta per nome e zona
        self.pile = []          # dict(zona="main"|"side"|"cmd", x, y, carte=[id...], aperta=id|None) in coordinate di scala M
        self.zoom = 1.0             # lo zoom del foglio (il mazzo)
        self.hs = FASCIA_DEF        # l'altezza della fascia della sideboard, in pixel: la barra di separazione
        # la fascia ferma in cima alla finestra (12 nov 2026, Autore: «quando zoomo in o out le carte nell'area sideboard si ridimensionano mentre quelle del
        # deck no», «quando sposto le carte nell'area sideboard, l'area side resta value 0»): prima scorreva col foglio, e lo zoom della rotella (che tiene
        # fermo il punto sotto il mouse) la portava fuori dallo schermo. Ora la fascia e le sue carte stanno dove comincia la vista (_fx, _fy: la vista con cui
        # sono disegnate) e si rimettono li' quando la vista cambia (segui_fascia); il foglio del mazzo le scorre sotto.
        self._fx, self._fy = 0.0, 0.0
        self.separa = None          # la barra mentre la trascini
        self._zoom_dopo = None
        self.drag = None
        self.sel = []           # le pile selezionate (riquadro sul vuoto, Ctrl+clic): si spostano insieme, e da loro nasce una label
        self.banda = None       # il riquadro di selezione mentre lo tiri
        self.ridim = None       # l'angolo di una label mentre lo tiri
        self.filtro = set()     # i tipi a vista (12 nov 2026): vuoto = All; le carte fuori stanno da parte (_riposte), nel mazzo e nella disposizione
        self._ordine_pile = []  # l'ordine delle pile prima del filtro: sfiltra lo rimette
        self._riposte = []      # [(pila, tolta, [(indice, vid)])]: le carte tenute da parte per il filtro, e se la pila e' uscita perche' non ne restava nessuna
        self.note = {}          # le note personali sulle carte (12 nov 2026): {nome della carta: dict(testo, aperta)}; quelle delle label stanno nella label
        self.occhi = set()      # le carte spente con l'occhio dell'outliner (13 nov 2026): {(nome, zona)}; i gruppi spenti hanno «nascosta» nella label
        self._spente = set()    # le carte che l'occhio tiene fuori adesso: le loro e quelle dei gruppi spenti (filtra)
        self.etichette = []     # le label: dict(nome, x, y, w, h) in coordinate del mazzo (scala 1), riquadri col nome; le carte dentro ne fanno parte
        # i dot delle linee (Autore, 9 nov 2026: «la possibilita' di spezzare le linee con dei dot dai quali possiamo fare partire altre linee (come in nuke)»):
        # id -> dict(x, y nel mazzo a scala 1, padre = la carta da cui viene il segnale, da = il dot prima nella catena o None); vie: (padre, figlio) -> l'ultimo dot
        self.punti, self.vie = {}, {}
        self.sel_punti = set()
        self.sel_label = set()          # le label tutte dentro il riquadro di selezione: si spostano col gruppo
        self._pezzi, self._tronchi = [], []
        self._stile_pop = self._nome_pop = None
        # la griglia (Autore, 10 nov 2026: «rendiamo l'opzione spuntabile in alto: grid snap»): una preferenza sola per tutti i mazzi, nel file delle disposizioni
        pref = carica_tavoli(self.file_tavoli).get(OPZIONI) or {}
        self.griglia = bool(pref.get("griglia", True))
        self.comandi_aperti = False      # la lista dei comandi parte sempre chiusa (Autore, 10 nov 2026: «commands parte chiuso»)
        self.outliner_aperto = bool(pref.get("outliner", True))    # l'outliner a sinistra, chiuso o aperto (10 nov 2026)
        self.sel_carta = None       # la carta scelta col clic, sul Board o nell'outliner: F la inquadra
        self.clic = None        # il clic semplice aspetta un attimo: se arriva il doppio clic, non apre la pila
        self.hover = dict(cid=None, timer=None, pop=None)
        self.pronte, self.attese = collections.deque(), set()
        self.lista = CAP.Liste(tk, F)
        # la finestra, sopra quella del mazzo (transient, mai topmost: non sta sopra Arena)
        f = self.fin = pronta_poi(tk.Toplevel(padre, bg=C["fondo"]))       # nascosta finche' non e' riempita (11 nov 2026)
        f.transient(padre)
        f.title(f"Board · {self.nome}")
        barra_scura(f, C["fondo"], C["titolo"], C["filo"])
        padre.update_idletasks()
        L = min(1500, f.winfo_screenwidth() - 80)
        H = min(980, f.winfo_screenheight() - 90)
        if fuori:
            f.geometry(f"{L}x{H}+5000+20")
        elif geometria:     # nel builder: sopra il builder, alla sua misura (a sinistra resta la Collection)
            f.geometry(geometria)
            try:
                L, H = (int(v) for v in geometria.split("+")[0].split("x"))
            except ValueError:
                pass
        else:
            x = padre.winfo_rootx() + (padre.winfo_width() - L) // 2
            y = padre.winfo_rooty() + max(0, (padre.winfo_height() - H) // 2)
            f.geometry(f"{L}x{H}+{max(0, x)}+{max(0, y)}")
        f.minsize(900, 600)
        self._L, self._H = max(900, L), max(600, H)        # la misura chiesta: serve finche' la tela non ha la sua (la finestra appena nata e' nascosta)
        f.after(50, self.pulsante_ingrandisci)      # una finestra transient su Windows non ha il pulsante per ingrandirla: lo rimette
        f.bind("<Escape>", lambda e: self.esc())
        f.bind("<Key>", self.tasto, add="+")       # A e F
        f.protocol("WM_DELETE_WINDOW", self.chiudi)
        self.testata()
        self.riga_filtri()
        # il foglio sulla scheda video (Autore, 9 nov 2026: «Sì, portalo»): la tela GPU ha le funzioni della tela di Tk; se la scheda non parte, Tk come prima.
        # Senza bordi: il pan va ovunque (confine=False nella tela di Tk)
        self.cv = TG.crea(tk, f, bg=FOGLIO, highlightthickness=0, bd=0, confine=False)
        self.gpu = not isinstance(self.cv, tk.Canvas)
        self.outliner()
        self.cv.pack(fill="both", expand=True)
        self.pannello_comandi()
        self.info_aperto = True         # l'HUD delle carte e della curva: si chiude e si riapre dalla sua testa
        self._hud_rect, self._hud_vista = None, None
        self.fin.after(120, self.giro_hud)
        i = 0
        for zona, carte in (("cmd", dict(comandante or {}, **(compagno or {}))), ("main", main or {}), ("side", side or {})):
            for n, q in carte.items():
                if q > 0:
                    self.voci[i] = dict(nome=n, zona=zona, q=q); i += 1
        self.compagno = set(compagno or {})
        f.update_idletasks()        # la tela alla sua misura: le pile per costo vanno a capo sulla larghezza vera
        ripreso = self.riprendi()
        # in sola lettura un mazzo senza sideboard ne' comandante non ha la fascia: era una striscia vuota di 250 pixel in cima (13 nov 2026, Autore: «testa le
        # board delle schede dei deck perche' all'apertura sono disposte male»); la barra resta, e tirata giu' la riapre
        if self.sola and not any(v["zona"] != "main" for v in self.voci.values()):
            self.hs = 0
        if ripreso and not self.fascia_sta():        # la sideboard salvata oltre il bordo della finestra: la fascia si rifa' (le pile del mazzo restano)
            self.pile = [pl for pl in self.pile if pl["zona"] == "main"] + self.pile_fascia()
        if ripreso:
            self.disegna()      # la disposizione di prima: si disegna subito, senza aspettare che la finestra cambi misura
        else:
            self.disponi("cost", salva=False)
        # un clic solo, sulla tela (premi_tela): la barra, il pallino, il contatore, se no la carta sotto il puntatore, in ogni suo punto (Autore, 9 nov 2026:
        # «ovunque appoggio il mouse voglio muovere la carta»). Prima i clic erano legati ai pezzi disegnati e lo strato delle frecce, sopra le carte, se li prendeva.
        self.cv.bind("<Double-Button-1>", self.doppio)
        self.cv.bind("<ButtonPress-3>", self.destro)          # il tasto destro su una freccia la toglie
        self.cv.bind("<B1-Motion>", self.trascina)
        self.cv.bind("<ButtonRelease-1>", self.rilascia)
        self.cv.bind("<Motion>", self.passa)
        self.cv.bind("<Leave>", lambda e: self.nascondi())
        # la rotella e' lo zoom, intorno al puntatore; il tasto centrale tenuto premuto sposta il foglio (Autore, 9 nov 2026)
        self.cv.bind("<MouseWheel>", lambda e: self.rotella(e) if not e.state & 0x1 else None)
        self.cv.bind("<Control-MouseWheel>", self.rotella)
        self.cv.bind("<ButtonPress-2>", self.pan_inizio)
        self.cv.bind("<B2-Motion>", self.pan_muovi)
        self.cv.bind("<ButtonRelease-2>", self.pan_fine)
        self.cv.bind("<ButtonPress-1>", self.premi_tela)
        if self.gpu:        # i tasti che arrivano alla finestra della scheda video (A, F, Esc): la tela li passa qui
            self.cv.bind("<Key>", self.tasto)
            self.cv.bind("<Escape>", lambda e: self.esc())
        self.cv.bind("<Shift-MouseWheel>", lambda e: self.cv.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.cv.bind("<Configure>", self.al_configure)
        self.carica_mancanti()
        if self.modifica:       # il punto di partenza dello storico: Undo non va oltre, ed e' lo stato salvato
            self.storia, self.passo, self.salvato_a = [self.foto_stato()], 0, 0
            self.aggiorna_salva()
        # all'apertura tutto il mazzo in vista (13 nov 2026): la vista partiva sempre dall'angolo in alto a sinistra del foglio con lo zoom salvato, e le pile
        # spostate a destra, a sinistra o sopra (Arrange network, i gruppi automatici, le carte isolate) restavano fuori, o sotto la fascia e l'HUD. Se la tela
        # non ha ancora la sua misura, aspetta il primo <Configure>
        self._da_inquadrare = True
        self.inquadra_apertura()
        f.lift(); f.focus_set()

    def al_configure(self, e=None):
        self.disegna()
        if self._da_inquadrare:
            self.inquadra_apertura()

    # ------------------------------------------------ i filtri per tipo (12 nov 2026)
    # Autore: «aggiungiamo la possibilita' con pulsanti sulla cornice alta della board e relativi loghi di mtga di visualizzare solo le creature solo gli istantanei
    # ecc nascondendo le carte non incluse nel flag e un flag per all che di default e' acceso - quando premo un flag diverso all si spegne e si rivela solo il
    # contenuto di quel flag - posso combinare piu' flag tra loro ma il flag all non puo' combinarsi con altri flag e' assoluto». Le icone sono disegnate da noi
    # nello stile dei simboli dei tipi (i loghi di Arena non sono fra i file che abbiamo): artiglio, fulmine, fiamma, sole, anfora, scintilla, monti, scudo.
    def riga_filtri(self):
        tk = self.tk
        self.c_filtri = tk.Canvas(self.fin, height=40, bg=C["cap"], highlightthickness=0, cursor="hand2")
        self.c_filtri.pack(fill="x")
        self.c_filtri.bind("<Button-1>", self.clic_filtro)
        self.c_filtri.bind("<Configure>", lambda e: self.disegna_filtri())
        self.disegna_filtri()

    def disegna_filtri(self):
        c, F = self.c_filtri, self.F
        c.delete("all")
        self._box_filtri = []
        x = 14
        c.create_text(x, 20, text="SHOW", anchor="w", fill=C["muto"], font=F(7, True))
        x += 44
        conti = collections.Counter()
        for vid in self.voci:
            for t_ in self.tipi_di(vid):
                conti[t_] += self.voci[vid]["q"]
        for chiave, testo in TIPI:
            on = (chiave == "all" and not self.filtro) or chiave in self.filtro
            n = sum(v["q"] for v in self.voci.values()) if chiave == "all" else conti.get(chiave, 0)
            if chiave != "all" and not n:
                continue
            etichetta = f"{testo} {n}"
            lg = 34 + 7 * len(etichetta)
            col = C["accento"] if on else C["grigio"]
            c.create_rectangle(x, 7, x + lg, 33, fill=C["scheda"] if on else C["cap"], outline=C["accento"] if on else C["filo"])
            if chiave != "all":
                c.create_image(x + 7, 11, image=icona_tipo(chiave, 18, col), anchor="nw")
            c.create_text(x + (28 if chiave != "all" else 12), 20, text=etichetta, anchor="w", fill=C["titolo"] if on else C["grigio"], font=F(8, True))
            self._box_filtri.append((x, x + lg, chiave))
            x += lg + 6
        # Auto groups non sta piu' qui (13 nov 2026): le sue funzioni sono nel menu Groups della testata (menu_gruppi)

    def clic_filtro(self, e):
        for x0, x1, chiave in getattr(self, "_box_filtri", []):
            if x0 <= e.x <= x1:
                return self.scegli_filtro(chiave)

    def scegli_filtro(self, chiave):
        """All e' assoluto: lo accende e spegne gli altri. Un tipo spegne All e si somma agli altri accesi; spento l'ultimo, torna All."""
        if chiave == "all":
            self.filtro = set()
        elif chiave in self.filtro:
            self.filtro.discard(chiave)
        else:
            self.filtro.add(chiave)
        self.disegna_filtri()
        self.disegna()
        self.inquadra_visibili()        # le carte a vista inquadrate se qualcuna e' fuori (13 nov 2026: «il focus si sposta a caso»)
        nascoste = sum(len(x[2]) for x in self._riposte)
        self.dici("Showing all the cards" if not self.filtro else f"Showing {', '.join(sorted(self.filtro))} · {nascoste} cards hidden")

    # i gruppi automatici (12 nov 2026, Autore: «aggiungiamo la possibilita' di creare autogruppi di carte in base ai dati di analysis / autogruppi in base alle
    # carte visibili contro quelle nascoste»): ogni gruppo nasce come label, con le sue carte in fila, a destra di tutto, uno sotto l'altro
    # ------------------------------------------------ il menu Groups (13 nov 2026 sera)
    # Autore: «acanto all'arrange mettimao il menu dei groups con tutto il necessario per gestire i gruppi: il menu autogroups non esisterà più e le sue
    # funzioni si troveranno qui d'ora in poi». NEW (la selezione, le carte a vista del filtro), FROM YOUR GAMES (l'ex Auto groups dall'analisi), YOUR GROUPS
    # (ogni gruppo: il clic lo sceglie e lo inquadra, ≡ apre il suo menu con nome, colore, lucchetto, nota, Duplicate, Swap, Delete), TIDY (lucchetti per tutti,
    # via i gruppi vuoti, via tutti i gruppi lasciando le carte).
    def menu_gruppi(self):
        """Il menu del pulsante Groups, nello stile comune dei mini-menu (menu_board). -> la finestrella (p.voci: {testo: azione}, per le prove)."""
        tk, F = self.tk, self.F
        self.nome_chiudi()
        m = MB.Menu(tk, F, self.fin, "Groups", chiudi=self.nome_chiudi)
        self._nome_pop = p = m.p
        sel = any(q["zona"] == "main" for q in self.sel) or bool(self.sel_punti) or bool(self.sel_label)
        m.sezione("New")
        m.voce("Group the selection", "Name and color for the cards you selected" if sel else "Select some cards first: drag a box on the empty sheet",
               lambda: self.crea_etichetta(None), spenta=not sel)
        m.voce("Group the visible cards", "The cards the type filter shows, in one group" if self.filtro else "Turn on a type filter first (Creatures, Lands...)",
               self.auto_visibili, spenta=not self.filtro)
        m.sezione("From your games")
        m.voce("Best performers · Hard to cast · Weak in losses", "Three groups from the analysis of this deck in your logs", self.auto_analisi)
        m.sezione(f"Your groups · {len(self.etichette)}")
        if not self.etichette:
            tk.Label(m.corpo, text="No groups yet", bg=MB.FONDO, fg=C["grigio"], font=F(8)).pack(anchor="w", padx=20, pady=(2, 2))
        for k, lb in enumerate(self.etichette):
            n = sum(self.carte_gruppo(k).values()) if not lb.get("copia") else sum((lb.get("carte") or {}).values())
            r = m.riga(padx=8, pady=1)
            r.configure(cursor="hand2")
            tk.Frame(r, bg=lb.get("colore") or GRIGIO_L, width=4).pack(side="left", fill="y", padx=(0, 8))
            nome = tk.Label(r, text=lb["nome"].upper() + ("  · COPY" if lb.get("copia") else ""), bg=MB.FONDO, fg="#ffffff", font=F(9, True), anchor="w",
                            cursor="hand2")
            nome.pack(side="left", fill="x", expand=True, pady=4)
            menu = tk.Label(r, image=segno_menu(18), bg=MB.FONDO, cursor="hand2"); menu.pack(side="right", padx=(6, 0))
            tk.Label(r, image=DG.lucchetto(13, lb.get("lucchetto", True), "#f0ad4e" if lb.get("lucchetto", True) else "#d7dce5"), bg=MB.FONDO).pack(side="right", padx=4)
            tk.Label(r, text=f"{n} CARDS" if n else "EMPTY", bg=MB.FONDO, fg=C["grigio"] if n else C["rosso"], font=F(7, True), padx=6).pack(side="right")
            ww = [r, nome] + [w_ for w_ in r.winfo_children() if isinstance(w_, tk.Label)]

            def acc(on, ww=ww):
                for w_ in ww:
                    w_.configure(bg=MB.RIGA_SU if on else MB.FONDO)
            for w_ in ww:
                w_.bind("<Enter>", lambda ev, f=acc: f(True)); w_.bind("<Leave>", lambda ev, f=acc: f(False))
            for w_ in (r, nome):
                w_.bind("<Button-1>", lambda ev, k=k: (self.nome_chiudi(), self.scegli_gruppo(k)))
            menu.bind("<Button-1>", lambda ev, k=k: (self.nome_chiudi(), self.menu_label(k)))
            m.voci[f"group:{k}"] = lambda k=k: self.scegli_gruppo(k)
            m.voci[f"menu:{k}"] = lambda k=k: self.menu_label(k)
        if self.etichette:
            m.sezione("Tidy")
            tutti_chiusi = all(lb.get("lucchetto", True) for lb in self.etichette)
            m.voce("Unlock all groups" if tutti_chiusi else "Lock all groups",
                   "Every group moves alone: drop it over cards to take them in" if tutti_chiusi else "Every group moves with its cards",
                   lambda: self.lucchetti_tutti(not tutti_chiusi))
            vuoti = [k for k, lb in enumerate(self.etichette) if not lb.get("copia") and not self.carte_gruppo(k)]
            m.voce("Remove empty groups", f"{len(vuoti)} without cards" if vuoti else "Every group has cards", self.togli_vuoti, spenta=not vuoti)
            m.voce("Remove all groups", "The frames go, the cards stay where they are (Undo brings them back)", self.togli_tutti_gruppi, colore=C["rosso"])
        m.piede("Click a group to find it · ≡ name, color, lock, note, duplicate, swap, delete")
        p.voci = m.voci
        return m.posa(sotto=self.b_gruppi)

    def scegli_gruppo(self, k):
        """Il gruppo k scelto (come una selezione) e inquadrato: dall'outliner e dal menu Groups."""
        if not 0 <= k < len(self.etichette):
            return
        self.vuota_sel()
        self.sel_label = {k}
        lb = self.etichette[k]
        z, o = self.zoom, self.oy("main")
        self.inquadra((lb["x"] * z, o + lb["y"] * z, (lb["x"] + lb["w"]) * z, o + (lb["y"] + lb["h"]) * z), zmax=max(1.0, self.zoom))
        self.disegna_sel()
        if getattr(self, "out_cv", None) is not None:
            self.disegna_outliner()

    def lucchetti_tutti(self, on):
        """Tutti i gruppi col lucchetto chiuso (si spostano con le loro carte) o aperto (da soli)."""
        for lb in self.etichette:
            lb["lucchetto"] = bool(on)
        self.disegna(); self.salva()
        self.dici("All groups locked: each moves with its cards" if on else "All groups unlocked: each moves alone, drop it over cards to take them in")

    def togli_vuoti(self):
        """Via i gruppi senza carte (le copie no: le loro carte sono scritte). -> quanti."""
        vuoti = [k for k, lb in enumerate(self.etichette) if not lb.get("copia") and not self.carte_gruppo(k)]
        for k in reversed(vuoti):
            self.etichette.pop(k)
        self.sel_label = set()
        self.disegna(); self.salva()
        self.dici(f"{len(vuoti)} empty group{'s' * (len(vuoti) != 1)} removed" if vuoti else "No empty group")
        return len(vuoti)

    def togli_tutti_gruppi(self):
        """Via tutti i gruppi e le loro copie; le carte restano dove sono. Prima la domanda. -> la finestrella della domanda."""
        from widget import conferma, ROSSO_P

        def via():
            n = len(self.etichette)
            self.etichette = []
            self.sel_label = set()
            self.disegna(); self.salva()
            self.dici(f"{n} group{'s' * (n != 1)} removed: the cards stay where they are · Undo brings them back")
        self.domanda_gruppi = conferma(self.tk, self.F, self.fin, "Remove all groups?", f"The {len(self.etichette)} frames go, the cards stay where they are. "
                                       "Undo brings them back.", "Remove", via, colori=ROSSO_P)
        return self.domanda_gruppi

    def gruppi_auto(self, gruppi):
        """gruppi: [(nome, colore, [nomi delle carte])]. Le carte del mazzo con quei nomi escono dalle loro pile, una pila ciascuna, in fila a destra di tutto,
        e una label intorno a ogni fila. -> le label nate."""
        self.sfiltra()
        w, h, _off, _p = misure(1.0)
        destra = max([pl["x"] + w for pl in self.pile if pl["zona"] == "main"] + [lb["x"] + lb["w"] for lb in self.etichette], default=MARGINE)
        x0 = a_griglia(destra + 2 * PASSO_X, 0)[0]
        y = 0
        nate = []
        usate = set()
        for nome, colore, nomi in gruppi:
            vids = [vid for vid, v in self.voci.items() if v["zona"] == "main" and v["nome"] in nomi and vid not in usate]
            if not vids:
                continue
            for i, vid in enumerate(sorted(vids, key=self.ordine)):
                usate.add(vid)
                pl = self.pila_di(vid)
                if pl is not None:
                    pl["carte"].remove(vid)
                    if pl.get("aperta") == vid:
                        pl["aperta"] = None
                    if not pl["carte"]:
                        self.pile.remove(pl)
                self.pile.append(dict(zona="main", x=x0 + i * PASSO_X, y=y + TIT_L + PAD_L, carte=[vid], aperta=None))
            lb = dict(nome=nome, x=round(x0 - PAD_L - 14), y=round(y), w=round(len(vids) * PASSO_X + 2 * PAD_L), h=round(TIT_L + PAD_L * 2 + h),
                      colore=colore, lucchetto=True, id=self.nuovo_id())
            self.etichette.append(lb)
            nate.append(lb)
            y = a_griglia(0, y + lb["h"] + 2 * PASSO_Y)[1]
        self.disegna(); self.salva()
        if nate:
            self.inquadra_tutto()
        return nate

    def auto_visibili(self):
        """Un gruppo solo, con le carte che il filtro per tipo mostra (Autore, 12 nov 2026: «auto group show vs hidden deve essere solo autogroup visible e gruppa
        solo il visibile ma non l'invisibile»): le nascoste restano dove sono, e il filtro resta acceso."""
        if not self.filtro:
            self.dici("Turn on a type filter first: the group is the cards it shows")
            return []
        nomi = dict(TIPI)
        si = {v["nome"] for vid, v in self.voci.items() if v["zona"] == "main" and self.visibile(vid)}
        nate = self.gruppi_auto([(", ".join(nomi.get(t, t) for t in sorted(self.filtro)), "#24baff", si)])
        self.dici(f"Auto group: the {len(si)} visible cards" if nate else "No visible card to group")
        return nate

    def analisi_mazzo(self):
        """L'analisi del mazzo dai nostri log (analisi_mazzo.py), se il Board e' quello di un mazzo di Arena con partite; None se no. Le prove la passano."""
        f = getattr(self, "fonte_analisi", None)
        if f is not None:
            return f()
        if not (self.chiave or "").startswith("mio:"):
            return None
        try:
            import analisi_mazzo as AM
            import dati_mazzo as DM
            pp = AM.partite_mazzo(self.chiave[4:])
            lista = collections.Counter()
            for v in self.voci.values():
                lista[v["nome"]] += v["q"]
            return AM.analizza(pp, dict(lista), lambda n: DM.e_terra(n, self.carte_db)) if pp else None
        except Exception:       # noqa: BLE001 - senza analisi lo dice
            return None

    def auto_analisi(self):
        a = self.analisi_mazzo()
        if not a or not a.get("con_dati"):
            self.dici("No games of this deck in your logs yet: the analysis groups need them (play it on Arena)")
            return []
        nel = {v["nome"] for v in self.voci.values() if v["zona"] == "main"}
        gruppi = [("Best performers", "#5cb85c", [x["nome"] for x in a.get("migliori") or [] if x["nome"] in nel]),
                  ("Hard to cast", "#f0ad4e", [x["nome"] for x in a.get("fatica") or [] if x["nome"] in nel]),
                  ("Weak in your losses", "#d9534f", [x["nome"] for x in a.get("perse") or [] if x["nome"] in nel])]
        nate = self.gruppi_auto(gruppi)
        self.dici(f"Auto groups from {a['con_dati']} games: " + ", ".join(lb["nome"] for lb in nate) if nate else "The analysis has no card to group yet")
        return nate

    def tipi_di(self, vid):
        """I tipi della carta (creature, instant, ...) dalla sua riga del tipo: carte_db, se no il database delle carte di Arena."""
        v = self.voci.get(vid) or {}
        riga = (self.info(vid).get("tipo") or "") if vid in self.voci else ""
        if not riga:
            riga = tipo_arena(v.get("nome") or "")
        riga = riga.lower()
        return {k for k, _t in TIPI[1:] if k in riga}

    def visibile(self, vid):
        if vid in self._spente:         # spenta con l'occhio dell'outliner, sua o del suo gruppo
            return False
        return not self.filtro or bool(self.tipi_di(vid) & self.filtro)

    # ------------------------------------------------ la visibilita' coi livelli, come in Photoshop (13 nov 2026)
    # Autore: «mettiamo la visibility di gruppi e carte nell'outliner con l'occhietto proprio come i layer di photoshop e il loro comportamento per visibility di
    # elementi gruppi e elementi nei gruppi». Ogni riga dell'outliner ha l'occhio. Una carta spenta esce dal foglio (come col filtro per tipo: resta nel mazzo, nei
    # conti e nella disposizione); un gruppo spento spegne la sua cornice e tutto quello che ha dentro, anche i gruppi dentro di lui. Come nei livelli, una carta
    # dentro un gruppo spento tiene il suo occhio (riacceso il gruppo torna com'era) e nell'outliner la sua riga si fa grigia. Alt+clic su un occhio: solo quella
    # voce a vista; un altro Alt+clic rimette tutto com'era. Trascinando sugli occhi si accendono o si spengono in fila.
    def contiene(self, a, b):
        return a["x"] <= b["x"] and b["x"] + b["w"] <= a["x"] + a["w"] and a["y"] <= b["y"] and b["y"] + b["h"] <= a["y"] + a["h"]

    def label_spenta(self, k):
        """Il gruppo k non si vede: spento lui, o un gruppo che lo contiene."""
        if not 0 <= k < len(self.etichette):
            return False
        lb = self.etichette[k]
        if lb.get("nascosta"):
            return True
        return any(l2.get("nascosta") and not l2.get("copia") and j != k and self.contiene(l2, lb) for j, l2 in enumerate(self.etichette))

    def nascoste_ora(self):
        """Le carte che l'occhio tiene fuori: le spente e quelle dentro un gruppo spento (sulle pile di adesso)."""
        out = {vid for vid, v in self.voci.items() if (v["nome"], v["zona"]) in self.occhi}
        for k, lb in enumerate(self.etichette):
            if lb.get("nascosta") and not lb.get("copia"):
                pile, _a = self.membri(k)
                out |= {c for pl in pile for c in pl["carte"]}
        return out

    def etichetta_vista(self, k):
        """Il riquadro del gruppo k si vede col filtro per tipo? (13 nov 2026, Autore: «quando accendo o spengo i filtri tipo delle carte se quelle carte sono
        in un gruppo deve accendersi o spegnersi (visibile invisibile) anche il quadro del gruppo».) Senza filtro sempre; col filtro solo se almeno una sua carta
        passa: una pila a vista dentro di lui (le carte nascoste stanno da parte e le loro pile escono), o, per la copia di un gruppo, una delle carte scritte.
        Un gruppo vuoto col filtro acceso non si vede. Nascosto non si disegna, quindi non si prende col mouse, come le carte nascoste."""
        if 0 <= k < len(self.etichette) and self.label_spenta(k):        # spento con l'occhio dell'outliner (13 nov 2026)
            return False
        if not self.filtro or not 0 <= k < len(self.etichette):
            return True
        lb = self.etichette[k]
        if lb.get("copia"):
            for nome in (lb.get("carte") or {}):
                c = self.carte_db.get(nome) or self.carte_db.get(nome.split(" // ")[0].strip()) or {}
                riga = (c.get("tipo") or tipo_arena(nome) or "").lower()
                if {t for t, _n in TIPI[1:] if t in riga} & self.filtro:
                    return True
            return False
        x0, y0, x1, y1 = lb["x"], lb["y"], lb["x"] + lb["w"], lb["y"] + lb["h"]
        for pl in self.pile:
            if pl["zona"] == "main" and pl["carte"]:
                r = self.ingombro(pl)
                if x0 <= (r[0] + r[2]) / 2 <= x1 and y0 <= (r[1] + r[3]) / 2 <= y1:
                    return True
        return False

    def sfiltra(self):
        """Rimette nelle pile le carte tenute da parte (e le pile uscite perche' vuote)."""
        for pl, _tolta, carte in reversed(self._riposte):
            # la pila torna sul foglio se non c'e' piu': uscita perche' il filtro l'aveva svuotata, o perche' ne hai trascinato via tutte le carte a vista
            # (12 nov 2026, lo stress: le sue carte nascoste restavano senza pila). Solo se le resta una carta: una carta nascosta tolta dal builder col filtro
            # acceso (allinea) lasciava la pila vuota, e il disegno cadeva (13 nov 2026, lo stress)
            vive = [(i, vid) for i, vid in carte if vid in self.voci]
            if vive and not any(pl is q for q in self.pile):
                self.pile.append(pl)
            for i, vid in vive:
                if vid not in pl["carte"]:
                    pl["carte"].insert(min(i, len(pl["carte"])), vid)
            if pl.get("aperta") not in pl["carte"]:
                pl["aperta"] = None
        self._riposte = []
        self.pile = [pl for pl in self.pile if pl["carte"]]
        # le pile tornano nell'ordine di prima del filtro (l'ordine e' chi sta sopra a chi): prima quelle uscite si rimettevano in fondo, e col filtro acceso ogni
        # disegno cambiava l'ordine, quindi lo storico segnava un gesto a ogni zoom («Save ●» senza modifiche, Undo che non faceva niente: 13 nov 2026, lo stress)
        ordine = {id(p_): i for i, p_ in enumerate(self._ordine_pile)}
        if ordine:
            self.pile.sort(key=lambda p_: ordine.get(id(p_), len(ordine)))
        self._ordine_pile = []

    def filtra(self):
        """Tiene da parte le carte fuori dal filtro e quelle spente con l'occhio; una pila che resta vuota esce dal foglio finche' il filtro (o l'occhio) c'e'."""
        self._spente = self.nascoste_ora() if (self.occhi or any(lb.get("nascosta") for lb in self.etichette)) else set()
        if not self.filtro and not self._spente:
            return
        self._ordine_pile = list(self.pile)
        for pl in list(self.pile):
            via = [(i, vid) for i, vid in enumerate(pl["carte"]) if not self.visibile(vid)]
            if not via:
                continue
            for _i, vid in via:
                pl["carte"].remove(vid)
            tolta = not pl["carte"]
            if tolta:
                self.pile.remove(pl)
            self._riposte.append((pl, tolta, via))

    def pile_tutte(self):
        """Le pile con tutte le loro carte, anche quelle tenute da parte dal filtro: [(pila, carte)] (per salvare)."""
        extra = {}
        for pl, _tolta, carte in self._riposte:
            extra.setdefault(id(pl), (pl, []))[1].extend(carte)
        out = []
        seq = self.pile + [x[0] for x in extra.values() if not any(x[0] is q for q in self.pile)]
        ordine = {id(p_): i for i, p_ in enumerate(self._ordine_pile)}      # l'ordine di prima del filtro: le foto dello storico non cambiano col filtro
        if ordine:
            seq.sort(key=lambda p_: ordine.get(id(p_), len(ordine)))
        for pl in seq:
            carte = list(pl["carte"])
            for i, vid in sorted(extra.get(id(pl), (pl, []))[1]):
                if vid in self.voci and vid not in carte:
                    carte.insert(min(i, len(carte)), vid)
            if carte:
                out.append((pl, carte))
        return out

    # ------------------------------------------------ la testata
    def testata(self):
        tk, F = self.tk, self.F
        t = tk.Frame(self.fin, bg=C["cap"]); t.pack(fill="x")
        tk.Label(t, text=self.nome, bg=C["cap"], fg=C["titolo"], font=FN(16)).pack(side="left", padx=(14, 12), pady=10)      # Bahnschrift (redesign del 14 nov 2026)

        if self.nomi_ricerca is not None and self.modifica:
            self.ricerca(t)
        # Arrange accanto ad Add card (13 nov 2026, Autore: «afianco a add card metterei il menù arrange»); prima stava a destra, vicino a Grid snap
        self.b_arrange = None
        if not self.sola:
            b = self.b_arrange = pulsante_solido(tk, F, t, "Arrange ▾", False, self.menu_disponi, alto=28, bg=C["cap"])
            b.configure(width=120); b.pack(side="left", padx=(10, 0))
        # Groups accanto ad Arrange (13 nov 2026 sera, Autore: «acanto all'arrange mettimao il menu dei groups con tutto il necessario per gestire i gruppi: il
        # menu autogroups non esisterà più e le sue funzioni si troveranno qui d'ora in poi»): solo in modalita' edit, come Auto groups prima
        self.b_gruppi = None
        if self.modifica:
            b = self.b_gruppi = pulsante_solido(tk, F, t, "Groups ▾", False, self.menu_gruppi, alto=28, bg=C["cap"])
            b.configure(width=120); b.pack(side="left", padx=(8, 0))
        dx = tk.Frame(t, bg=C["cap"]); dx.pack(side="right", padx=10)
        # Save in fondo a destra, dopo lo zoom, e verde come in tutta l'app (13 nov 2026, Autore: «e save lo sposti tutto a destra e save ovunque sull'app
        # sempre verde»); prima stava fra Redo e Full page, in arancio
        if not self.sola and self.modifica:
            self.b_salva = pulsante_solido(tk, F, dx, "Save", False, self.salva_tutto, alto=28, bg=C["cap"], colori=VERDE_P)
            self.b_salva.configure(width=96); self.b_salva.pack(side="right", padx=(14, 0))
        # lo zoom del foglio (al posto di S M L): − e + a passi, il numero torna al 100%, Fit fa stare il mazzo nella finestra; anche Ctrl+rotella
        # i pulsanti della testata nello stile S3 come tutti (14 nov 2026, Autore: «ogni pulsante esistente deve avere il redesign in linea con lo stile»);
        # fino a quel giorno erano scritte cliccabili
        for testo, azione in (("Fit", lambda: self.adatta()), ("+", lambda: self.zoom_a(self.zoom * 1.15)), ("%", None), ("−", lambda: self.zoom_a(self.zoom / 1.15))):
            if azione is None:
                self.l_zoom = tk.Label(dx, text="100%", bg=C["cap"], fg=C["titolo"], font=F(9, True), width=5, cursor="hand2"); self.l_zoom.pack(side="right")
                self.l_zoom.bind("<Button-1>", lambda e: self.zoom_a(1.0))
                continue
            b = pulsante_solido(tk, F, dx, testo, False, azione, alto=26, bg=C["cap"], colori=GRIGIO_T, icona=False)
            b.configure(width=54 if testo == "Fit" else 28)
            b.pack(side="right", padx=(8, 0) if testo == "Fit" else 0)
        tk.Label(dx, text="ZOOM", bg=C["cap"], fg=C["muto"], font=F(7, True)).pack(side="right", padx=(14, 4))
        self.b_pagina = pulsante_solido(tk, F, dx, "Full page", False, lambda: self.tutta_pagina(), alto=26, bg=C["cap"], colori=GRIGIO_T)
        self.b_pagina.configure(width=122); self.b_pagina.pack(side="right", padx=(10, 0))
        # By type, By cost e Label non ci sono piu' (Autore, 10 nov 2026: «togli i pulsanti by type by cost ecc»): la prima apertura dispone per costo,
        # la label nasce dalle tre linee della cornice della selezione. Resta un pulsante solo: la rete riordinata per connessioni (stesso giorno)
        if self.sola:
            tk.Label(dx, text="VIEW ONLY · Cards can be moved · Edit the deck to change it" if self.sposta else "VIEW ONLY · Edit the deck to change the board",
                     bg=C["cap"], fg=C["muto"], font=F(8, True)).pack(side="right", padx=(4, 12))
            self.b_griglia = None
        else:
            if self.modifica:       # Undo e Redo (12 nov 2026); Save sta in fondo a destra, dopo lo zoom (sopra)
                for chi, testo, fa in (("b_redo", "Redo", self.ripeti), ("b_undo", "Undo", self.annulla)):
                    w_ = pulsante_solido(tk, F, dx, testo, False, fa, alto=26, bg=C["cap"], colori=GRIGIO_T)
                    w_.configure(width=88); w_.pack(side="right", padx=(6, 0)); w_.spegni(True)
                    setattr(self, chi, w_)
            self.b_griglia = tk.Label(dx, text="  Grid snap", bg=C["cap"], fg=C["testo"], font=F(9, True), compound="left", cursor="hand2")
            self.b_griglia.pack(side="right", padx=(4, 10))
            self.b_griglia.bind("<Button-1>", lambda e: self.cambia_griglia())
            self.spunta_griglia()
        tk.Frame(self.fin, bg=C["filo"], height=1).pack(fill="x")

    def spunta_griglia(self):
        self.b_griglia.configure(image=DG.spunta(14, self.griglia, C["accento"], C["scheda"], C["grigio"], C["fondo"]))

    def cambia_griglia(self, on=None):
        """La spunta Grid snap: accesa, cio' che lasci si aggancia alla griglia; spenta, resta dove lo lasci. Si ricorda per tutti i mazzi."""
        self.griglia = (not self.griglia) if on is None else bool(on)
        self.spunta_griglia()
        self.salva_pref(griglia=self.griglia)
        self.dici("Grid snap " + ("on: what you drop lines up on the grid" if self.griglia else "off: what you drop stays where you leave it"))

    def outliner(self):
        """L'outliner, come in Maya (Autore, 10 nov 2026: «sulla sinistra voglio qualcosa come un outliner di Maya con tutta la lista carte / quantita' accanto / se
        clicco su una di quelle carte e premo F il network deve portarmi sulla carta / l'outliner ha le carte sopra e le terre sotto separate da un piccolo spazio»,
        «l'outliner deve essere chiudibile da sinistra a destra»): una riga per carta col numero delle copie, prima le magie, poi le terre, poi la sideboard, ogni
        gruppo staccato. Il clic sceglie la carta (anche sul Board), F la inquadra, il doppio clic la inquadra subito. La linguetta a destra lo chiude e lo riapre."""
        tk, F = self.tk, self.F
        f = self.f_out = tk.Frame(self.fin, bg=C["fondo"]); f.pack(side="left", fill="y")
        self.b_out = tk.Label(f, text="", bg=C["cap"], fg=C["titolo"], font=F(8, True), cursor="hand2", width=2)
        self.b_out.pack(side="right", fill="y")
        self.b_out.bind("<Button-1>", lambda e: self.apri_outliner(not self.outliner_aperto))
        corpo = self.out_corpo = tk.Frame(f, bg=C["fondo"], width=LARGO_OUT)
        corpo.pack_propagate(False)
        testa = tk.Frame(corpo, bg=C["fondo"]); testa.pack(fill="x", padx=(10, 8), pady=(8, 4))
        tk.Label(testa, text="OUTLINER", bg=C["fondo"], fg=C["muto"], font=F(7, True), anchor="w").pack(side="left")
        # SHOW ALL (13 nov 2026): con qualcosa di spento con l'occhio, riaccende tutto in un clic
        self.b_tutti = tk.Label(testa, text="SHOW ALL", bg=C["fondo"], fg=C["accento"], font=F(7, True), cursor="hand2")
        self.b_tutti.bind("<Button-1>", lambda e: self.mostra_tutto())
        self.out_cv = tk.Canvas(corpo, bg=C["fondo"], highlightthickness=0, bd=0, width=LARGO_OUT)
        self.out_cv.pack(fill="both", expand=True)
        self.out_cv.bind("<Button-1>", lambda e: self.scegli_outliner(e))
        self.out_cv.bind("<B1-Motion>", lambda e: self.occhi_trascina(e))
        self.out_cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "_occhi_drag", None))
        self.out_cv.bind("<Double-Button-1>", self.doppio_outliner)
        self.out_cv.bind("<Motion>", self.passa_outliner)
        self.out_cv.bind("<Leave>", lambda e: (self.out_cv.delete("su"), setattr(self, "_out_su", None)))
        self.out_cv.bind("<MouseWheel>", lambda e: self.out_cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.out_cv.bind("<Configure>", lambda e: self.disegna_outliner())
        self._out_righe = []
        self.apri_outliner(self.outliner_aperto, salva=False)

    def apri_outliner(self, aperto, salva=True):
        self.outliner_aperto = bool(aperto)
        if self.outliner_aperto:
            self.out_corpo.pack(side="left", fill="both", before=self.b_out)
        else:
            self.out_corpo.pack_forget()
        self.b_out.configure(text="◀" if self.outliner_aperto else "▶")
        if salva:
            self.salva_pref(outliner=self.outliner_aperto)

    def gruppi_outliner(self):
        """[(titolo, [vid])]: comandante, magie, terre, sideboard; dentro, per costo e nome."""
        terra = lambda i: "Land" in (self.info(i).get("tipo") or "").split(" // ")[0] or self.voci[i]["nome"] in MS.BASI
        ordinate = sorted(self.voci, key=self.ordine)
        return [("COMMANDER", [i for i in ordinate if self.voci[i]["zona"] == "cmd"]),
                ("", [i for i in ordinate if self.voci[i]["zona"] == "main" and not terra(i)]),
                ("", [i for i in ordinate if self.voci[i]["zona"] == "main" and terra(i)]),
                ("SIDEBOARD", [i for i in ordinate if self.voci[i]["zona"] == "side"])]

    def voci_outliner(self):
        """Le righe dell'outliner, un elenco solo (13 nov 2026, Autore: «l'outliner non deve ripetere le carte gruppate ma deve mantenere lo stesso elenco e
        aggiungere il gruppo tra le carte incluse in ogni gruppo»; prima i gruppi stavano in fondo, sotto GROUPS, e ripetevano le loro carte). Comandante, magie,
        terre e sideboard come sempre; un gruppo entra nell'elenco al posto della sua prima carta, come intestazione, con sotto tutte le sue carte (anche le terre),
        e le carte fuori dai gruppi restano dove sono. Una carta in due label (una dentro l'altra) sta nella piu' piccola. Le copie di un gruppo (Duplicate: carte
        scritte, non nel mazzo) sono una riga sola sotto il gruppo da cui vengono; i gruppi vuoti in fondo al mazzo. Con tutte le carte, anche quelle che il filtro
        nasconde. -> [("titolo", testo) | ("spazio",) | ("gruppo", k, label, copie) | ("carta", vid, colore del gruppo o None)]"""
        nascoste = bool(self._riposte)
        if nascoste:
            self.sfiltra()
        try:
            casa = {}
            for k, lb in enumerate(self.etichette):
                if lb.get("copia"):
                    continue
                pile, _a = self.membri(k)
                for pl in pile:
                    for c in pl["carte"]:
                        j = casa.get(c)
                        if j is None or lb["w"] * lb["h"] < self.etichette[j]["w"] * self.etichette[j]["h"]:
                            casa[c] = k
        finally:
            if nascoste:
                self.filtra()
        casa = {c: k for c, k in casa.items() if c in self.voci and self.voci[c]["zona"] == "main"}
        out, fatti = [], set()

        def copie_di(lb):
            return [(j, l2) for j, l2 in enumerate(self.etichette) if l2.get("copia") and lb.get("id") and l2.get("origine") == lb.get("id")]

        def blocco(k, righe):
            lb = self.etichette[k]
            fatti.add(k)
            carte = sorted((c for c, j in casa.items() if j == k), key=self.ordine)
            col = lb.get("colore") or GRIGIO_L
            righe.append(("gruppo", k, lb, sum(self.voci[c]["q"] for c in carte)))
            righe += [("carta", c, col) for c in carte]
            for j, l2 in copie_di(lb):
                fatti.add(j)
                righe.append(("gruppo", j, l2, sum((l2.get("carte") or {}).values())))

        sezioni = self.gruppi_outliner()
        for i, (titolo, vids) in enumerate(sezioni):
            righe = []
            for vid in vids:
                k = casa.get(vid)
                if k is None:
                    righe.append(("carta", vid, None))
                elif k not in fatti:
                    blocco(k, righe)
            if i == 2:      # in fondo al mazzo i gruppi vuoti e le copie senza il loro gruppo
                for k, lb in enumerate(self.etichette):
                    if k not in fatti and not (lb.get("copia") and any(l0.get("id") == lb.get("origine") for l0 in self.etichette if not l0.get("copia"))):
                        fatti.add(k)
                        righe.append(("gruppo", k, lb, sum((lb.get("carte") or {}).values()) if lb.get("copia") else 0))
            if not righe:
                continue
            if out:
                out.append(("spazio",))
            if titolo:
                out.append(("titolo", titolo))
            out += righe
        return out

    def disegna_outliner(self):
        cv = getattr(self, "out_cv", None)
        if cv is None or not cv.winfo_exists():
            return
        import tkinter.font as tkf
        F = self.F
        fnt, fnt_b = tkf.Font(font=F(8)), tkf.Font(font=F(8, True))
        L = max(cv.winfo_width(), LARGO_OUT)
        cv.delete("all")
        self._out_righe, y = [], 2

        def corto(nome, spazio, f_):
            if f_.measure(nome) > spazio:
                while nome and f_.measure(nome + "…") > spazio:
                    nome = nome[:-1]
                nome += "…"
            return nome
        for voce in self.voci_outliner():
            if voce[0] == "spazio":
                y += 9          # un piccolo spazio fra magie, terre e sideboard
            elif voce[0] == "titolo":
                cv.create_text(10, y + 6, text=voce[1], fill=C["muto"], font=F(6, True), anchor="w")
                y += 14
            elif voce[0] == "gruppo":       # l'intestazione del gruppo, nel suo colore, col totale delle copie; la copia di un gruppo in grigio
                _t, k, lb, n_ = voce
                col = lb.get("colore") or GRIGIO_L
                copia = bool(lb.get("copia"))
                if k in self.sel_label:
                    cv.create_rectangle(0, y, L, y + RIGA_OUT, fill="#1d3a52", width=0)
                spento = self.label_spenta(k)
                self.occhio_riga(cv, y, not lb.get("nascosta"), spento)
                cv.create_rectangle(OCCHIO_OUT + 4, y + 4, OCCHIO_OUT + 8, y + RIGA_OUT - 4, fill=col, width=0)
                testo = (lb["nome"] + ("  · copy" if copia else "")).upper()
                cv.create_text(OCCHIO_OUT + 14, y + RIGA_OUT / 2, text=corto(testo, L - 52 - OCCHIO_OUT, fnt_b),
                               fill=C["muto"] if spento else C["grigio"] if copia else "#ffffff", font=F(8, True), anchor="w")
                cv.create_text(L - 10, y + RIGA_OUT / 2, text=str(n_), fill=C["muto"] if spento else col, font=F(8, True), anchor="e")
                self._out_righe.append((y, y + RIGA_OUT, ("l", k)))
                y += RIGA_OUT
            else:
                _t, vid, col = voce
                v = self.voci[vid]
                scelta = vid == self.sel_carta
                if scelta:
                    cv.create_rectangle(0, y, L, y + RIGA_OUT, fill="#1d3a52", width=0)
                spento = vid in self._spente
                self.occhio_riga(cv, y, (v["nome"], v["zona"]) not in self.occhi, spento)
                spento = spento or self.pila_di(vid) is None        # fuori dal filtro per tipo: grigia anche lei, la carta non e' sul foglio
                x0 = OCCHIO_OUT + 10
                if col is not None:     # dentro un gruppo: rientrata, col filo del colore del gruppo
                    cv.create_rectangle(OCCHIO_OUT + 10, y, OCCHIO_OUT + 12, y + RIGA_OUT, fill=col, width=0)
                    x0 = OCCHIO_OUT + 22
                cv.create_text(x0, y + RIGA_OUT / 2, text=corto(v["nome"], L - 34 - x0, fnt), fill=C["muto"] if spento else "#ffffff" if scelta else C["testo"],
                               font=F(8), anchor="w")
                cv.create_text(L - 10, y + RIGA_OUT / 2, text=str(v["q"]), fill=C["muto"] if spento else C["accento"] if scelta else C["grigio"],
                               font=F(8, True), anchor="e")
                self._out_righe.append((y, y + RIGA_OUT, vid))
                y += RIGA_OUT
        cv.configure(scrollregion=(0, 0, L, y + 6))
        b_t = getattr(self, "b_tutti", None)
        if b_t is not None:
            if self.occhi or any(lb.get("nascosta") for lb in self.etichette):
                b_t.pack(side="right")
            else:
                b_t.pack_forget()
        su = getattr(self, "_out_su", None)
        r = next(((y0, y1) for y0, y1, v in self._out_righe if v == su), None) if su is not None else None
        if r:
            cv.create_rectangle(0, r[0], L, r[1], fill="#17202b", width=0, tags="su")
            cv.tag_lower("su")

    def doppio_outliner(self, e):
        """Il doppio clic: sul nome sceglie e inquadra; sull'occhio e' solo il secondo clic (prima inquadrava anche, e la vista saltava)."""
        if e.x < OCCHIO_OUT:
            return self.scegli_outliner(e)
        self.scegli_outliner(e)
        self.inquadra_selezione()

    def passa_outliner(self, e):
        """La riga sotto il mouse si accende appena, come le righe dei menu; sulle righe la manina."""
        cv = self.out_cv
        voce = self.riga_outliner(e.y)
        if voce == getattr(self, "_out_su", None):
            return
        self._out_su = voce
        cv.delete("su")
        r = next(((y0, y1) for y0, y1, v in self._out_righe if v == voce), None)
        if r:
            cv.create_rectangle(0, r[0], max(cv.winfo_width(), LARGO_OUT), r[1], fill="#17202b", width=0, tags="su")
            cv.tag_lower("su")
        cv.configure(cursor="hand2" if r else "")

    def mostra_tutto(self):
        """SHOW ALL: ogni carta e ogni gruppo di nuovo a vista (anche dopo un Alt+clic). -> quante voci ha riacceso."""
        n = len(self.occhi) + sum(1 for lb in self.etichette if lb.get("nascosta"))
        if not n:
            return 0
        self.occhi = set()
        for lb in self.etichette:
            lb.pop("nascosta", None)
        self._solo = None
        self.disegna()
        self.salva()
        self.disegna_outliner()
        self.dici(f"Everything in sight again ({n} item{'s' * (n != 1)} turned back on)")
        return n

    def occhio_riga(self, cv, y, acceso, spento):
        """L'occhio della riga: aperto se la voce e' accesa, barrato se e' spenta lei; aperto ma grigio se si spegne per il gruppo che la contiene."""
        col = C["muto"] if (acceso and spento) else C["accento"] if acceso else C["muto"]
        cv.create_image(3, y + RIGA_OUT / 2 - 8, image=DG.occhio(16, col, barrato=not acceso), anchor="nw")

    def riga_outliner(self, ey):
        y = self.out_cv.canvasy(ey)
        return next((v for y0, y1, v in self._out_righe if y0 <= y < y1), None)

    def acceso(self, voce):
        """La voce dell'outliner ha l'occhio aperto? voce: un vid o ("l", k)."""
        if isinstance(voce, tuple):
            return not self.etichette[voce[1]].get("nascosta")
        v = self.voci[voce]
        return (v["nome"], v["zona"]) not in self.occhi

    def metti_occhio(self, voce, on):
        """Accende (on) o spegne la voce, senza ridisegnare."""
        if isinstance(voce, tuple):
            lb = self.etichette[voce[1]]
            if on:
                lb.pop("nascosta", None)
            else:
                lb["nascosta"] = True
            return
        v = self.voci[voce]
        (self.occhi.discard if on else self.occhi.add)((v["nome"], v["zona"]))

    def occhio(self, voce, on=None, alt=False):
        """Il clic sull'occhio: accende o spegne la voce (on None: il contrario di adesso). alt: solo questa a vista, come Alt+clic nei livelli di Photoshop; di
        nuovo Alt+clic sulla stessa rimette la visibilita' di prima."""
        if alt:
            solo = getattr(self, "_solo", None)
            if solo is not None and solo[0] == voce:
                self.occhi, nascoste = set(solo[1]), set(solo[2])
                for k, lb in enumerate(self.etichette):
                    if lb.get("id", f"#{k}") in nascoste:
                        lb["nascosta"] = True
                    else:
                        lb.pop("nascosta", None)
                self._solo = None
                self.dici("Every item back as it was")
            else:
                self._solo = (voce, set(self.occhi), {lb.get("id", f"#{k}") for k, lb in enumerate(self.etichette) if lb.get("nascosta")})
                self.sfiltra()
                tieni_k = voce[1] if isinstance(voce, tuple) else None
                if tieni_k is not None:
                    pile, altre = self.membri(tieni_k)
                    dentro = {c for pl in pile for c in pl["carte"]}
                    tieni_l = {tieni_k} | set(altre) | {j for j, l2 in enumerate(self.etichette) if j != tieni_k and self.contiene(l2, self.etichette[tieni_k])}
                else:
                    dentro = {voce}
                    tieni_l = {j for j, l2 in enumerate(self.etichette) if not l2.get("copia") and voce in {c for pl in self.membri(j)[0] for c in pl["carte"]}}
                self.occhi = {(v["nome"], v["zona"]) for i, v in self.voci.items() if i not in dentro}
                for k, lb in enumerate(self.etichette):
                    if k in tieni_l:
                        lb.pop("nascosta", None)
                    else:
                        lb["nascosta"] = True
                nome = self.etichette[tieni_k]["nome"] if tieni_k is not None else self.voci[voce]["nome"]
                self.dici(f"Only «{nome}» in sight · Alt+click its eye again to bring everything back")
        else:
            self.metti_occhio(voce, (not self.acceso(voce)) if on is None else on)
            self._solo = None
        self.disegna()
        self.salva()
        self.disegna_outliner()

    def occhi_trascina(self, e):
        """Trascinando sulla colonna degli occhi, ogni riga che tocchi prende lo stato del primo occhio premuto (come nei livelli di Photoshop)."""
        d = getattr(self, "_occhi_drag", None)
        if d is None:
            return
        voce = self.riga_outliner(e.y)
        if voce is None or voce in d["fatte"] or self.acceso(voce) == d["on"]:
            return
        d["fatte"].add(voce)
        self.metti_occhio(voce, d["on"])
        self.disegna()
        self.salva()
        self.disegna_outliner()

    def scegli_outliner(self, e):
        y = self.out_cv.canvasy(e.y)
        vid = next((v for y0, y1, v in self._out_righe if y0 <= y < y1), None)
        if vid is None:
            return
        if e.x < OCCHIO_OUT:        # l'occhio (13 nov 2026): visibilita' come i livelli di Photoshop
            alt = bool((getattr(e, "state", 0) or 0) & (0x20000 if piattaforma.WINDOWS else 0x10))
            if not alt:
                self._occhi_drag = dict(on=not self.acceso(vid), fatte={vid})
            self.occhio(vid, alt=alt)
            return
        if isinstance(vid, tuple):      # la riga di un gruppo: la label scelta e inquadrata
            return self.scegli_gruppo(vid[1])
        if self.sel or self.sel_punti or self.sel_label:        # la carta scelta prende il posto della selezione (prima restava, e F inquadrava quella)
            self.sel, self.sel_punti, self.sel_label = [], set(), set()
        self.sel_carta = vid
        # la carta fuori dalla vista: il foglio la porta in vista, senza cambiare lo zoom (13 nov 2026, Autore: «non trovo in prima vista le carte che ho
        # focussato»); nascosta dal filtro o nella fascia chiusa, lo dice
        if not self.mostra_carta(vid):
            pl = self.pila_di(vid)
            if pl is None:
                self.dici(f"{self.voci[vid]['nome']} is hidden: its eye or its group's eye in the outliner" if vid in self._spente
                          else f"{self.voci[vid]['nome']} is hidden by the type filter")
            elif pl["zona"] != "main" and self.nascosta():
                self.dici(f"{self.voci[vid]['nome']} is in the sideboard: drag the bar down to open it")
        self.disegna_sel()
        self.disegna_outliner()
        self.out_cv.focus_set()

    # ------------------------------------------------ inquadrare: A tutta la rete, F la selezione (come in Maya)
    def tasto(self, e):
        """A e F sul Board (anche quando i tasti arrivano dalla finestra della scheda video); non mentre scrivi in una casella."""
        if isinstance(self.fin.focus_get(), (self.tk.Entry, self.tk.Text)):
            return
        k = (getattr(e, "keysym", "") or "").lower()
        st = getattr(e, "state", 0) or 0
        if st & 0x4 and k in ("z", "y"):        # Ctrl+Z annulla, Ctrl+Y (o Ctrl+Shift+Z) rifa' (12 nov 2026)
            return self.ripeti() if k == "y" or st & 0x1 else self.annulla()
        if st & 0x4:
            return
        if k == "a":
            return self.inquadra_tutto()
        if k == "f":
            return self.inquadra_selezione()

    def rett_tutto(self):
        """Il rettangolo di tutta la rete del mazzo, in pixel della tela: le pile, le label, i dot."""
        rr = [self.ingombro_px(pl) for pl in self.pile if pl["zona"] == "main"]
        rr += [self.lb_px(k) for k in range(len(self.etichette)) if self.etichetta_vista(k)]       # i gruppi spenti dal filtro no
        rr += [(lambda pt: (pt[0] - 10, pt[1] - 10, pt[0] + 26, pt[1] + 10))(self.punto_xy(q)) for q in self.punti]
        return self.unione(rr)

    @staticmethod
    def unione(rr):
        """Il rettangolo che li contiene tutti, con l'aria per il numero delle copie (a sinistra) e per i pallini (sotto). None se non ce n'e'."""
        rr = [r for r in rr if r]
        if not rr:
            return None
        return min(r[0] for r in rr) - 16, min(r[1] for r in rr) - 8, max(r[2] for r in rr) + 8, max(r[3] for r in rr) + 26

    def rett_visibili(self):
        """Il rettangolo delle pile del mazzo che si vedono adesso (col filtro per tipo: solo quelle con carte a vista)."""
        return self.unione([self.ingombro_px(pl) for pl in self.pile if pl["zona"] == "main" and pl["carte"]])

    def rett_selezione(self):
        cor = self.cornice_sel()
        if cor:
            return cor
        if self.sel_carta in self.voci:
            pl = self.pila_di(self.sel_carta)
            if pl is not None and pl["zona"] == "main":
                x0, y0, x1, y1 = self.ingombro_px(pl)
                return x0 - 16, y0 - 8, x1 + 8, y1 + 26
        return None

    def inquadra_tutto(self):
        r = self.rett_tutto()
        if r is None:
            self.dici("Nothing to frame")
            return False
        return self.inquadra(r)

    def inquadra_selezione(self):
        sola_carta = self.sel_carta in self.voci and not (self.sel or self.sel_punti or self.sel_label)
        pl = self.pila_di(self.sel_carta) if sola_carta else None
        if pl is not None and pl["zona"] != "main":
            # la carta scelta sta nella fascia della sideboard, ferma in cima alla finestra: e' gia' in vista, il foglio non si muove (13 nov 2026: prima F la
            # trattava come una carta del mazzo e portava la vista in un punto a caso del foglio)
            self.dici(f"{self.voci[self.sel_carta]['nome']} is in the sideboard band, always in view" if not self.nascosta()
                      else "That card is in the sideboard: drag the bar down to open it")
            return False
        r = self.rett_selezione()
        if r is None:
            if sola_carta and pl is None:
                self.dici(f"{self.voci[self.sel_carta]['nome']} is hidden by the type filter")
                return False
            self.dici("F frames the selection: click a card, pick one in the outliner, or drag a box")
            return False
        return self.inquadra(r)

    # le zone della finestra dove il foglio del mazzo si vede davvero (13 nov 2026, Autore: «quando seleziono una categoria di carte il focus si sposta a caso e
    # non trovo in prima vista le carte che ho focussato»): F, A e l'inquadratura mettevano il rettangolo al centro di tutta la tela, e la parte alta finiva sotto la
    # fascia della sideboard (ferma in cima, 250 pixel); l'HUD in alto a destra e la finestrella dei comandi in basso a destra coprivano il resto
    def ostacoli(self):
        """I riquadri sopra il foglio, in coordinate della finestra della tela: l'HUD delle carte e la finestrella dei comandi."""
        W, H = self.misura_tela()
        hud = self._hud_rect or (W - INFO_L - 14, 12, W - 14, 12 + TESTA_HUD + (INFO_H if self.info_aperto else 0))
        out = [tuple(hud)]
        try:
            pw, ph = self.pannello.winfo_width(), self.pannello.winfo_height()
            if pw > 1 and ph > 1:
                out.append((W - 12 - pw, H - 12 - ph, W - 12, H - 12))
        except Exception:       # noqa: BLE001 - la finestrella non c'e' ancora
            pass
        return out

    def misura_tela(self):
        """La tela in pixel; finche' non ha la sua misura (la finestra appena nata, nascosta), quella chiesta alla finestra, meno l'outliner e le righe in alto."""
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        if W >= 200 and H >= 200:
            return W, H
        return max(400, self._L - (LARGO_OUT + 18 if self.outliner_aperto else 18)), max(300, self._H - 140)

    def aree_libere(self):
        """Dove il mazzo si vede tutto, in coordinate della finestra della tela: sotto la fascia (se aperta), fuori da HUD e comandi. Due scelte quando un riquadro
        sporge nell'area: tagliare a destra (tutta l'altezza) o tagliare sopra e sotto (tutta la larghezza)."""
        W, H = self.misura_tela()
        top = (self.hs if not self.nascosta() else 0) + 10
        tocca = [o for o in self.ostacoli() if o[3] > top and o[1] < H and o[2] > 0]
        if not tocca:
            return [(0, top, W, H)]
        a = (0, top, min(o[0] for o in tocca) - 8, H)
        su = [o for o in tocca if o[1] < (top + H) / 2]
        giu = [o for o in tocca if o[1] >= (top + H) / 2]
        b = (0, max([top] + [o[3] + 8 for o in su]), W, min([H] + [o[1] - 8 for o in giu]))
        return [r for r in (a, b) if r[2] - r[0] > 100 and r[3] - r[1] > 100] or [(0, top, W, H)]

    def in_vista(self, r, tolleranza=3):
        """Il rettangolo (pixel della tela) si vede tutto in una delle aree libere?"""
        if r is None:
            return True
        vx, vy = self.cv.canvasx(0), self.cv.canvasy(0)
        x0, y0, x1, y1 = r[0] - vx, r[1] - vy, r[2] - vx, r[3] - vy
        t = tolleranza
        return any(a[0] - t <= x0 and x1 <= a[2] + t and a[1] - t <= y0 and y1 <= a[3] + t for a in self.aree_libere())

    def pile_in_vista(self):
        """Ogni pila del mazzo (col filtro: quelle a vista) si vede intera, sotto la fascia e fuori da HUD e comandi?"""
        W, H = self.misura_tela()
        vx, vy = self.cv.canvasx(0), self.cv.canvasy(0)
        top = (self.hs if not self.nascosta() else 0) + 10
        ost = self.ostacoli()
        for pl in self.pile:
            if pl["zona"] != "main" or not pl["carte"]:
                continue
            x0, y0, x1, y1 = self.ingombro_px(pl)
            x0, y0, x1, y1 = x0 - 14 - vx, y0 - vy, x1 - vx, y1 - vy        # il numero delle copie sporge a sinistra
            if x0 < -3 or y0 < top - 3 or x1 > W + 3 or y1 > H + 3:
                return False
            if any(x0 < o[2] and o[0] < x1 and y0 < o[3] and o[1] < y1 for o in ost):
                return False
        return True

    def inquadra(self, r, margine=30, zmax=ZOOM_MAX, salva=True):
        """Lo zoom e la vista che mettono il rettangolo (pixel della tela, allo zoom di adesso) al centro dell'area libera della finestra (sotto la fascia, fuori
        da HUD e comandi), il piu' grande possibile fino a zmax."""
        cv = self.cv
        self._da_inquadrare = False
        z0, o = self.zoom, self.oy("main")
        fx0, fx1 = r[0] / z0, r[2] / z0
        fy0, fy1 = (r[1] - o) / z0, (r[3] - o) / z0
        fw, fh = max(1.0, fx1 - fx0), max(1.0, fy1 - fy0)
        migliore = None
        for a in self.aree_libere():
            za = min((a[2] - a[0] - 2 * margine) / fw, (a[3] - a[1] - 2 * margine) / fh)
            if migliore is None or za > migliore[0]:
                migliore = (za, a)
        z, area = migliore
        passi = 20 if z >= ZOOM_MIN else 100
        z = max(ZOOM_VISTA, math.floor(min(zmax, ZOOM_MAX, z) * passi + 1e-6) / passi)     # per difetto: il rettangolo ci sta davvero
        if self._zoom_dopo is not None:
            cv.after_cancel(self._zoom_dopo)
            self._zoom_dopo = None
        if self.gpu:
            cv.azzera_zoom()
        self.zoom = z
        self.l_zoom.configure(text=f"{round(z * 100)}%")
        self.disegna()
        o = self.oy("main")
        cx, cy = (fx0 + fx1) / 2 * z, o + (fy0 + fy1) / 2 * z
        ax, ay = (area[0] + area[2]) / 2, (area[1] + area[3]) / 2
        dx, dy = cx - cv.canvasx(ax), cy - cv.canvasy(ay)
        cv.scan_mark(0, 0)
        cv.scan_dragto(int(round(-dx)), int(round(-dy)), gain=1)
        self.segui_fascia()
        if salva:
            self.salva()
        return True

    def inquadra_apertura(self):
        """All'apertura (e al primo <Configure> se la tela non era ancora a misura): se una pila del mazzo non si vede intera, tutto il mazzo inquadrato, allo zoom
        salvato al massimo (o al 100%). Se si vede gia' tutto, zoom e vista restano."""
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        if W < 200 or H < 200:
            return False
        self._da_inquadrare = False
        if self.pile_in_vista():
            return False
        r = self.rett_tutto()
        return self.inquadra(r, zmax=max(1.0, self.zoom), salva=False) if r else False

    def inquadra_visibili(self):
        """Dopo un cambio del filtro per tipo: se qualche carta a vista e' fuori dalla vista, le carte a vista inquadrate (le altre stanno da parte); se si vedono
        gia' tutte, la vista resta dov'e'."""
        self._da_inquadrare = False
        if self.cv.winfo_width() < 200 or self.pile_in_vista():
            return False
        r = self.rett_visibili() if self.filtro else self.rett_tutto()
        return self.inquadra(r, zmax=max(1.0, self.zoom)) if r else False

    def mostra_carta(self, vid):
        """La carta (appena arrivata, o scelta nell'outliner) fuori dalla vista: il foglio si sposta finche' la sua pila e' al centro, senza cambiare lo zoom."""
        pl = self.pila_di(vid) if vid in self.voci else None
        if pl is None or pl["zona"] != "main" or self.cv.winfo_width() < 200:
            return False
        x0, y0, x1, y1 = self.ingombro_px(pl)
        r = (x0 - 16, y0 - 8, x1 + 8, y1 + 26)
        if self.in_vista(r):
            return False
        cv = self.cv
        area = max(self.aree_libere(), key=lambda a: (a[2] - a[0]) * (a[3] - a[1]))
        alta = min(r[3] - r[1], area[3] - area[1] - 20)      # una pila piu' alta della finestra: la sua cima in vista
        ax, ay = (area[0] + area[2]) / 2, area[1] + 10 + alta / 2
        dx, dy = (r[0] + r[2]) / 2 - cv.canvasx(ax), r[1] + alta / 2 - cv.canvasy(ay)
        cv.scan_mark(0, 0)
        cv.scan_dragto(int(round(-dx)), int(round(-dy)), gain=1)
        self.segui_fascia()
        return True

    def curva(self):
        """La curva di mana delle magie del mazzo, con le copie: [quante a 0, 1, ..., 6, 7+]."""
        c = [0] * 8
        for i, v in self.voci.items():
            if v["zona"] != "main" or "Land" in (self.info(i).get("tipo") or "").split(" // ")[0] or v["nome"] in MS.BASI:
                continue
            c[min(7, int(self.info(i).get("cmc", 0) or 0))] += v["q"]
        return c

    def disegna_info(self, conti=None, tot=None):
        """L'HUD delle carte e della curva di mana, in alto a destra sul foglio (Autore, 10 nov 2026: «sposta l'hud mana curve a dx che abbia colori e stile dell'app e
        fallo con sfondo semi trasparente e chiudibile come i comandi»; prima un riquadro opaco in alto a sinistra): la testa azzurra col totale e la freccia (si chiude
        e si riapre), sotto, su uno sfondo scuro semitrasparente, magie, terre, sideboard e la curva delle magie del mazzo (0-6, 7+). Sta fermo nella finestra: sulla
        scheda video nello strato fisso della tela; con la tela di Tk si rimette a posto quando la vista cambia (giro_hud)."""
        cv, F = self.cv, self.F
        if conti is None:
            conti = collections.Counter()
            for v in self.voci.values():
                conti[v["zona"]] += v["q"]
            tot = conti["main"] + conti["side"]
        conti = collections.Counter(conti)
        self._hud_dati = (conti, tot)
        cv.delete("hud")
        W = cv.winfo_width()
        self._hud_vista = (cv.canvasx(0), cv.canvasy(0), W)
        if W < 200:         # la tela non ancora a misura (una finestra di prova nascosta): l'HUD aspetta, se no finirebbe sopra le carte in alto a sinistra
            self._hud_rect = None
            return
        x0, y0 = W - INFO_L - 14, 12
        alto = TESTA_HUD + (INFO_H if self.info_aperto else 0)
        self._hud_rect = (x0, y0, x0 + INFO_L, y0 + alto)
        ox, oy = (0.0, 0.0) if self.gpu else (cv.canvasx(0), cv.canvasy(0))      # con la tela di Tk il foglio scorre: l'HUD si mette dove si guarda
        self._hud_vista = (cv.canvasx(0), cv.canvasy(0), W)
        kw = dict(fisso=True) if self.gpu else {}
        X, Y = x0 + ox, y0 + oy
        cv.create_rectangle(X, Y, X + INFO_L, Y + TESTA_HUD, fill=C["accento"], width=0, tags=("hud", "hud_testa"), **kw)
        cv.create_text(X + 10, Y + TESTA_HUD / 2, text=f"DECK · {conti['main']} CARDS" if tot else "DECK · no list", fill="#ffffff", font=F(8, True), anchor="w",
                       tags=("hud", "hud_testa"), **kw)
        cv.create_image(X + INFO_L - 8 - 14, Y + TESTA_HUD / 2 - 7, image=DG.triangolo(14, self.info_aperto, "#ffffff"), anchor="nw", tags=("hud", "hud_testa"), **kw)      # disegnato: il font della scheda non ha ▾
        if self.info_aperto and tot:
            fondo = DG._icona(("hud_fondo", INFO_L, INFO_H), lambda: (lambda d: (d.rett(0, 0, INFO_L, INFO_H, riempi=FONDO_HUD, raggio=0), d)[1])(DG.Disegno(INFO_L, INFO_H)))
            cv.create_image(X, Y + TESTA_HUD, image=fondo, anchor="nw", tags=("hud", "hud_fondo"), **kw)
            curva = self.curva()
            magie = sum(curva)
            cv.create_text(X + 10, Y + TESTA_HUD + 12, text=f"{magie} spells · {conti['main'] - magie} lands · {conti['side']} sideboard"
                           + (f" · {conti['cmd']} commander" if conti["cmd"] else ""), fill=C["testo"], font=F(8), anchor="w", tags=("hud",), **kw)
            alto_b, base, passo = 34, Y + TESTA_HUD + INFO_H - 14, (INFO_L - 24) / 8
            mx = max(curva) or 1
            for k, n in enumerate(curva):
                x = X + 12 + k * passo
                h = round(alto_b * n / mx)
                if n:
                    cv.create_rectangle(x + 3, base - h, x + passo - 3, base, fill=C["accento"], width=0, tags=("hud", "curva"), **kw)
                    cv.create_text(x + passo / 2, base - h - 6, text=str(n), fill="#ffffff", font=F(6, True), tags=("hud",), **kw)
                cv.create_text(x + passo / 2, base + 7, text="7+" if k == 7 else str(k), fill=C["grigio"], font=F(6), tags=("hud",), **kw)
        if not self.gpu:
            cv.tag_raise("hud")

    def giro_hud(self):
        """Con la tela di Tk l'HUD sta sul foglio: quando la vista cambia (pan, zoom, finestra) si rimette nell'angolo; sulla scheda video solo se la finestra cambia misura."""
        try:
            if not self.fin.winfo_exists():
                return
        except Exception:
            return
        cv = self.cv
        W = cv.winfo_width()
        if not getattr(cv, "zk", 1.0) != 1.0:       # durante lo zoom immediato della scheda video no: lo rifa' il disegno
            self.segui_fascia()
        vista = (cv.canvasx(0), cv.canvasy(0), W)
        if self._hud_vista is not None and (vista != self._hud_vista if not self.gpu else vista[2] != self._hud_vista[2]) and getattr(self, "_hud_dati", None):
            self.disegna_info(*self._hud_dati)
        self.fin.after(90, self.giro_hud)

    def hud_su(self, ex, ey):
        """Il punto (coordinate della finestra della tela) e' sull'HUD? -> "testa", "corpo" o None."""
        r = self._hud_rect
        if not r or not (r[0] <= ex <= r[2] and r[1] <= ey <= r[3]):
            return None
        return "testa" if ey <= r[1] + TESTA_HUD else "corpo"

    def apri_info(self, aperto=None):
        self.info_aperto = (not self.info_aperto) if aperto is None else bool(aperto)
        self.disegna_info()

    def pulsante_ingrandisci(self):
        """Il pulsante per ingrandire nella barra del titolo (Autore, 10 nov 2026: «fai in modo che si possa allargare questa finestra della board fino a tutta
        pagina»): una finestra transient su Windows non lo ha; Tk sa ingrandirla lo stesso (zoomed). Anche il doppio clic sulla barra del titolo."""
        try:
            import ctypes
            u = ctypes.windll.user32
            u.GetParent.restype = ctypes.c_void_p
            hw = u.GetParent(self.fin.winfo_id())
            st = u.GetWindowLongW(ctypes.c_void_p(hw), -16)
            u.SetWindowLongW(ctypes.c_void_p(hw), -16, st | 0x10000)        # WS_MAXIMIZEBOX
            u.SetWindowPos(ctypes.c_void_p(hw), None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)      # niente spostamenti, il bordo rifatto
        except Exception:
            pass

    def tutta_pagina(self, on=None):
        """Full page nella testata: la finestra del Board su tutto lo schermo (l'area di lavoro, sopra la barra di Windows), o com'era."""
        on = (self.fin.state() != "zoomed") if on is None else bool(on)
        self.fin.state("zoomed" if on else "normal")
        self.b_pagina.metti("Restore" if on else "Full page", False)
        return on

    def salva_pref(self, **kw):
        """Le preferenze del Board, per tutti i mazzi: nel file delle disposizioni, sotto _opzioni."""
        try:
            salva_tavolo(OPZIONI, dict(carica_tavoli(self.file_tavoli).get(OPZIONI) or {}, **kw), self.file_tavoli)
        except OSError:
            pass

    def pannello_comandi(self):
        """La finestrella dei comandi, in basso a destra sopra il foglio: in testa la riga che dice cosa e' appena successo (self.aiuto), sotto i comandi."""
        tk, F = self.tk, self.F
        box = self.pannello = tk.Frame(self.fin, bg=C["filo"], padx=1, pady=1)
        dentro = tk.Frame(box, bg=C["cap"]); dentro.pack()
        self.aiuto_base = "COMMANDS · view only" if self.sola else "COMMANDS" + ("" if self.modifica else " · only arranged, not changed")
        # la testa azzurra (Autore, 10 nov 2026: «la testina della sua tendina deve essere azzurrina»); tutta la testa apre e chiude la lista
        testa = tk.Frame(dentro, bg=C["accento"], cursor="hand2"); testa.grid(row=0, column=0, sticky="ew")
        self.aiuto = tk.Label(testa, text=self.aiuto_base, bg=C["accento"], fg=FG_AIUTO, font=F(7, True), anchor="w", justify="left", wraplength=280, cursor="hand2")
        self.aiuto.pack(side="left", padx=(8, 4), pady=(5, 4))
        # la lista si chiude e si riapre dalla freccia in testa (Autore, 10 nov 2026: «la lista comandi deve essere chiudibile o espandibile»)
        self.b_comandi = tk.Label(testa, text="", bg=C["accento"], fg="#ffffff", font=F(8, True), cursor="hand2", padx=6)
        self.b_comandi.pack(side="right", pady=(4, 3))
        for w_ in (testa, self.aiuto, self.b_comandi):
            w_.bind("<Button-1>", lambda e: self.apri_comandi(not self.comandi_aperti))
        self.f_comandi = tk.Frame(dentro, bg=C["cap"])
        for i, (tasto, cosa) in enumerate(COMANDI_VISTA if self.sola else COMANDI + (COMANDI_MOD if self.modifica else ())):
            tk.Label(self.f_comandi, text=tasto, bg=C["cap"], fg=C["titolo"], font=F(7, True), anchor="w").grid(row=i, column=0, sticky="w", padx=(8, 6))
            tk.Label(self.f_comandi, text=cosa, bg=C["cap"], fg=C["grigio"], font=F(7), anchor="w").grid(row=i, column=1, sticky="w", padx=(0, 8))
        tk.Frame(self.f_comandi, bg=C["cap"], height=5).grid(row=99, column=0)
        self.apri_comandi(self.comandi_aperti)
        box.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")
        box.lift()

    def apri_comandi(self, aperta):
        self.comandi_aperti = bool(aperta)
        if self.comandi_aperti:
            self.f_comandi.grid(row=1, column=0, sticky="w")
        else:
            self.f_comandi.grid_remove()
        self.b_comandi.configure(text="▾" if self.comandi_aperti else "▸")

    # ------------------------------------------------ lo zoom del foglio e la fascia della sideboard
    def zoom_a(self, nuovo, ex=None, ey=None):
        """Lo zoom del foglio (il mazzo), a passi di 5 punti; intorno al puntatore se c'e' (Ctrl+rotella), se no intorno all'angolo in alto. Il disegno aspetta un attimo:
        la rotella manda tanti scatti e le carte si ricuociono una volta sola."""
        # sotto ZOOM_MIN si arriva solo inquadrando (A): da li' la rotella va a passi fini e non salta di colpo al 30%
        nuovo = max(min(ZOOM_MIN, self.zoom), min(ZOOM_MAX, nuovo))
        nuovo = round(nuovo * 20) / 20 if nuovo >= ZOOM_MIN else round(nuovo * 100) / 100
        if nuovo == self.zoom:
            return
        cv = self.cv
        if self.gpu:
            return self.zoom_gpu(nuovo, ex, ey)
        if self._zoom_dopo is not None:     # piu' scatti prima del disegno: il punto fermo resta quello del primo, misurato sul foglio disegnato
            cv.after_cancel(self._zoom_dopo)
            fermo = self._zoom_fermo
        elif ex is not None:
            cx, cy = cv.canvasx(ex), cv.canvasy(ey)
            fermo = (cx / self.zoom, (cy - self.oy("main")) / self.zoom, ex, ey)
        else:
            fermo = None
        self._zoom_fermo = fermo
        self.zoom = nuovo
        self.l_zoom.configure(text=f"{round(nuovo * 100)}%")

        def fai():
            self._zoom_dopo = None
            self.disegna()
            if fermo:       # il punto del mazzo che stava sotto il puntatore resta li' (anche oltre i bordi: il foglio non ne ha)
                nx, ny = fermo[0] * self.zoom, self.oy("main") + fermo[1] * self.zoom
                spx, spy = nx - cv.canvasx(fermo[2]), ny - cv.canvasy(fermo[3])
                cv.scan_mark(0, 0)
                cv.scan_dragto(int(round(-spx)), int(round(-spy)), gain=1)
                self.segui_fascia()
            self.salva()
        self._zoom_dopo = cv.after(60, fai)

    def zoom_gpu(self, nuovo, ex, ey):
        """Lo zoom sulla scheda video: a ogni scatto la scheda ingrandisce subito quello che c'e' intorno al puntatore (zoom_immediato, niente da ridisegnare),
        e quando la rotella si ferma (140 ms) Card view ridisegna una volta alla misura nuova, col punto sotto il puntatore fermo. Sulla scheda le carte non si
        rifanno (texture a 2x), quindi il ridisegno costa quanto un disegno normale."""
        cv = self.cv
        if ex is None:
            ex, ey = cv.winfo_width() / 2, cv.winfo_height() / 2
        if self._zoom_dopo is None:
            self._zoom_base = self.zoom         # lo zoom del foglio disegnato
        cv.zoom_immediato(nuovo / self.zoom, ex, ey)
        self.zoom = nuovo
        self.l_zoom.configure(text=f"{round(nuovo * 100)}%")
        self._zoom_punto = (ex, ey)
        if self._zoom_dopo is not None:
            cv.after_cancel(self._zoom_dopo)

        def fai():
            self._zoom_dopo = None
            px, py = self._zoom_punto
            base = self._zoom_base
            omain = self.oy("main")
            cx, cy = cv.canvasx(px), cv.canvasy(py)         # il punto sotto il puntatore, nel foglio disegnato (lo zoom immediato compreso)
            fx, fy = cx / base, (cy - omain) / base
            cv.azzera_zoom()
            self.disegna()
            nx, ny = fx * self.zoom, omain + fy * self.zoom
            cv.vx, cv.vy = nx - px, ny - py                 # il punto torna sotto il puntatore
            cv.sporco = True
            self.segui_fascia()
            self.salva()
        self._zoom_dopo = cv.after(140, fai)

    def rotella(self, e):
        self.nascondi()
        self._da_inquadrare = False
        self.zoom_a(self.zoom * (1.12 if e.delta > 0 else 1 / 1.12), e.x, e.y)

    def pan_inizio(self, e):
        """Il tasto centrale premuto: il foglio segue il mouse (la mano), fino al rilascio."""
        self.nascondi()
        self._da_inquadrare = False
        self.cv.configure(cursor="fleur")
        self.cv.scan_mark(e.x, e.y)

    def pan_muovi(self, e):
        self.cv.scan_dragto(e.x, e.y, gain=1)
        self.segui_fascia()

    def pan_fine(self, e):
        self.cv.configure(cursor="")
        bb = self.cv.bbox("all")
        self.cv.delete("barra")
        self.barra(bb[2] if bb else max(self.cv.winfo_width(), 400))       # il segno della barra torna al centro di quello che si vede

    def adatta(self):
        """Fit: tutto il mazzo nella finestra, come A (13 nov 2026: prima portava la vista all'angolo del foglio, e le pile spostate a sinistra o sopra
        restavano fuori; e non vedeva HUD e comandi)."""
        r = self.rett_tutto()
        if r is None:
            return False
        return self.inquadra(r)

    def sf(self):
        """La scala delle carte della fascia: quella che ci sta nell'altezza della fascia (una carta e due sfalsate), al massimo 1,25. Sotto SPARISCE non si disegnano."""
        _w, h, off, _p = misure(1.0)
        v = max(0.0, min(1.25, (self.hs - ETICHETTA - 12) / (h + 2 * off)))
        return int(v * 20) / 20     # a passi di 5 punti: trascinando la barra le carte si ricuociono solo quando cambia il passo

    def nascosta(self):
        return self.sf() < SPARISCE

    def sc(self, zona):
        return self.zoom if zona == "main" else self.sf()

    def oy(self, zona):
        """Dove comincia la zona sulla tela, in pixel: la fascia sotto il suo titolo (dove comincia la vista: la fascia sta ferma in cima alla finestra), il
        mazzo sotto la barra e il suo titolo."""
        return self.hs + ETICHETTA if zona == "main" else self._fy + ETICHETTA

    def ox(self, zona):
        """Dove comincia la zona in orizzontale: il mazzo a 0 sulla tela, la fascia dove comincia la vista."""
        return 0.0 if zona == "main" else self._fx

    def in_fascia(self, cy):
        """Il punto della tela (y) e' nella fascia della sideboard, che sta in cima alla finestra?"""
        return cy - self._fy < self.hs and not self.nascosta()

    def segui_fascia(self):
        """La vista e' cambiata (pan, rotella, zoom, inquadra): la fascia e le sue carte tornano in cima alla finestra, spostate, senza ridisegnare. Le frecce
        che toccano la fascia si rifanno. -> True se si e' mossa."""
        cv = self.cv
        self.metti_puntini(crea=False)
        # sulla scheda la vista vera (vx, vy), senza lo zoom immediato della rotella: la fascia sta nello strato che non si ingrandisce (12 nov 2026)
        fx, fy = (cv.vx, cv.vy) if self.gpu else (cv.canvasx(0), cv.canvasy(0))
        dx, dy = fx - self._fx, fy - self._fy
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return False
        self._fx, self._fy = fx, fy
        cv.move("fascia", dx, dy)
        tocca, rete = False, self._nomi_rete()
        for pl in self.pile:
            if pl["zona"] != "main":
                for vid in pl["carte"]:
                    for t_ in (f"c{vid}", f"n{vid}", f"s{vid}", f"ni{vid}", f"nn{vid}", f"nb{vid}"):
                        cv.move(t_, dx, dy)
                    tocca |= self.voci[vid]["nome"] in rete
        if tocca:
            self.disegna_rete()
        return True

    def bagliore_label(self, cx, cy):
        """Il gruppo sotto il puntatore ha un bagliore leggero sul bordo, nel suo colore (redesign del 14 nov 2026, approvato da Autore): due cornici sfumate
        verso il foglio, sotto il gruppo. Solo un segno: non cambia niente di cosa fa il gruppo. cy None: nessun bagliore."""
        cv, z, o = self.cv, self.zoom, self.oy("main")
        k_ = None
        if cy is not None:
            for k, lb in enumerate(self.etichette):
                if not self.etichetta_vista(k):
                    continue
                x0, y0 = lb["x"] * z, o + lb["y"] * z
                if x0 <= cx <= x0 + lb["w"] * z and y0 <= cy <= y0 + lb["h"] * z:
                    k_ = k          # l'ultima trovata e' quella disegnata sopra
        if k_ == getattr(self, "_bagliore", None):
            return
        cv.delete("bagliore")
        self._bagliore = k_
        if k_ is None:
            return
        lb = self.etichette[k_]
        col = lb.get("colore") or GRIGIO_L
        x0, y0 = lb["x"] * z, o + lb["y"] * z
        x1, y1 = x0 + lb["w"] * z, y0 + lb["h"] * z
        for d_, k2 in ((4, 0.82), (2, 0.6)):
            cv.create_rectangle(x0 - d_, y0 - d_, x1 + d_, y1 + d_, outline=mescola(col, FOGLIO, k2), width=2, tags=("bagliore",))
        if cv.find_withtag("label"):
            cv.tag_lower("bagliore", "label")
        if cv.find_withtag("puntini"):
            cv.tag_lower("puntini")

    def metti_puntini(self, crea=True):
        """Il foglio a puntini del redesign (14 nov 2026): un'immagine di puntini un passo piu' grande della vista, sotto tutto. Il disegno e' periodico, quindi
        col pan si sposta a scatti di un passo e resta uguale; si rifa' solo quando cambia lo zoom o la misura della finestra. crea False (il giro dell'HUD, il
        pan): solo lo sposta; l'immagine nuova si fa nel disegno (sulla scheda video una texture creata fuori dal disegno faceva cadere il processo)."""
        cv = self.cv
        try:
            passo = max(16, round(PASSO_PUNTI * self.zoom))
            W, H = max(cv.winfo_width(), 200), max(cv.winfo_height(), 200)
            vx, vy = (cv.vx, cv.vy) if self.gpu else (cv.canvasx(0), cv.canvasy(0))
            x0, y0 = math.floor(vx / passo) * passo - passo, math.floor(vy / passo) * passo - passo
            chiave = (passo, W + 3 * passo, H + 3 * passo)
            p_ = getattr(self, "_puntini", None)
            if p_ and p_[0] == chiave and cv.find_withtag("puntini"):
                if (p_[1], p_[2]) != (x0, y0):
                    cv.coords("puntini", x0, y0)
                    self._puntini = (chiave, x0, y0)
                return
            if not crea:
                return
            cv.delete("puntini")
            cv.create_image(x0, y0, image=DG.puntini(chiave[1], chiave[2], passo, PUNTINO, FOGLIO), anchor="nw", tags=("puntini",))
            cv.tag_lower("puntini")
            self._puntini = (chiave, x0, y0)
        except Exception:       # noqa: BLE001 - senza puntini il foglio resta del suo colore
            pass

    def _nomi_rete(self):
        return {n for p_, c_, _f in self.rete.legami({v["nome"] for v in self.voci.values()}) for n in (p_, c_)}

    def pos_px(self, pl):
        s_ = self.sc(pl["zona"])
        return self.ox(pl["zona"]) + pl["x"] * s_, self.oy(pl["zona"]) + pl["y"] * s_, s_

    def ys_px(self, pl):
        s_ = self.sc(pl["zona"]); o = self.oy(pl["zona"])
        return [o + y * s_ for y in self.posizioni(pl)]

    def ingombro_px(self, pl):
        """Il rettangolo della pila sulla tela, in pixel."""
        x, y, s_ = self.pos_px(pl)
        w, h, _off, _p = misure(1.0)
        return x, y, x + w * s_, self.oy(pl["zona"]) + (self.posizioni(pl)[-1] + h) * s_

    def vicino_barra(self, cy, cx=None):
        """Sulla barra fra fascia e foglio, o sul suo segno ▲▼ (che con la fascia chiusa del tutto sta appena sotto il bordo alto, intero)."""
        if abs(cy - self._fy - self.hs) <= 6:
            return True
        if cx is None or self.hs >= 9:
            return False
        mx = self.cv.canvasx(0) + max(self.cv.winfo_width(), 400) / 2
        return abs(cx - mx) <= 30 and 0 <= cy - self._fy <= 18

    def premi_tela(self, e):
        """Il tasto sinistro, ovunque sulla tela. In ordine: la barra della fascia (si trascina), il contatore (lo fa contatore), il pallino (una freccia
        nuova), una carta in ogni suo punto (si trascina), il vuoto (niente)."""
        self._da_inquadrare = False
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        self._xy = (cx, cy)
        self.stile_chiudi()
        su_hud = self.hud_su(e.x, e.y)
        if su_hud:          # l'HUD: la testa lo chiude e lo riapre, il corpo non lascia passare il clic al foglio
            self.drag = self.tira = None
            if su_hud == "testa":
                self.apri_info()
            return
        if self.sola:       # da guardare: la barra della fascia, una pila che si apre e le note da aprire e chiudere, nient'altro
            self.drag = self.tira = None
            sopra_n = self.pezzo_a(cx, cy)
            if sopra_n[0] in ("nota_i", "nota_b") and sopra_n[1] is not None:
                return self.apri_nota("c", self.voci[sopra_n[1]]["nome"])
            if sopra_n[0] in ("label_n", "label_nb") and sopra_n[1] is not None:
                return self.apri_nota("l", sopra_n[1])
            if self.vicino_barra(cy, cx):
                self.separa = dict(y0=cy, hs0=self.hs, attesa=None)
                return
            vid = self.carta_a(cx, cy)
            if vid is not None and self.sposta and not e.state & 0x4:      # la carta si trascina; un clic senza muoversi apre la pila, come prima
                return self.premi(e)
            if vid is not None:
                self.sel_carta = vid
                self.disegna_sel(); self.disegna_outliner()
                if self.clic is not None:
                    self.cv.after_cancel(self.clic)
                self.clic = self.cv.after(230, lambda: self.apri_pila(vid))
            return
        sopra = self.pezzo_a(cx, cy)
        if self.vicino_barra(cy, cx) and sopra[0] is None:      # la barra della fascia si prende solo dove non c'e' altro (10 nov 2026: il titolo di una label vicino
            self.drag = self.tira = None                    # alla barra trascinava la barra)
            self.separa = dict(y0=cy, hs0=self.hs, attesa=None)
            return
        if sopra[0] == "sel_menu":
            self.drag = None
            return self.menu_label(None)
        if sopra[0] in ("copia_s", "copia_x", "copia_a", "copia_w") and sopra[1] is not None:       # una copia di un gruppo: ⇄ cambia, ✕ toglie, + aggiunge, Swap
            self.drag = None
            if sopra[0] == "copia_w":
                return self.scambia_gruppo(sopra[1])
            if sopra[0] == "copia_a":
                return self.cerca_copia(sopra[1], None)
            k_, i_ = sopra[1]
            nome_ = sorted((self.etichette[k_].get("carte") or {}))[i_]
            if sopra[0] == "copia_x":
                return self.cambia_copia(k_, nome_, None)
            return self.cerca_copia(k_, nome_)
        if sopra[0] in ("nota_i", "nota_b", "nota_n", "label_n", "label_nb") and sopra[1] is not None:      # le note: l'icona apre e chiude, il riquadro e il ✎ scrivono
            self.drag = None
            if sopra[0] == "nota_i":
                return self.apri_nota("c", self.voci[sopra[1]]["nome"])
            if sopra[0] == "label_n":       # piena apre e chiude, col + scrive la prima
                return self.apri_nota("l", sopra[1]) if self.nota_di("l", sopra[1]) else self.editor_nota("l", sopra[1])
            if sopra[0] in ("nota_b", "nota_n"):
                return self.editor_nota("c", self.voci[sopra[1]]["nome"])
            return self.editor_nota("l", sopra[1])
        cor = self.cornice_sel()
        if (cor and sopra[0] in (None, "carta", "punto", "label_t") and not e.state & 0x4 and cor[0] <= cx <= cor[2] and cor[1] <= cy <= cor[3]):
            # con una selezione, dentro la sua cornice (una carta, un dot, il titolo di una label o il vuoto) si sposta sempre tutta la selezione, mai una carta sola
            # (Autore, 10 nov 2026: «non puo' essere che muovendolo per sbaglio si sposti solo una carta, e' obbligatorio che si muova l'intera selezione»)
            return self.gruppo_inizio(cx, cy)
        if sopra[0] == "ctrl":
            self.drag = None
            return self.contatore_su(sopra[1])
        if sopra[0] == "nodo":
            return self.nodo_inizio(e, sopra[1])
        if sopra[0] == "rete_x" and sopra[1] is not None:
            self.drag = None
            return self.togli_arco(sopra[1])
        if sopra[0] == "scambia" and sopra[1] is not None:
            self.drag = None
            return self.scambia_apri(sopra[1])
        if sopra[0] == "rete_s" and sopra[1] is not None:
            self.drag = None
            return self.stile_apri(sopra[1])
        if sopra[0] == "rete_c" and sopra[1] is not None:
            self.drag = None
            return self.inserisci_punto(*sopra[1], hit=getattr(self, "_chiodo_su", None))
        if sopra[0] == "rete_barra":        # il fondo della barretta dei pulsantini: niente
            self.drag = None
            return
        if sopra[0] == "rete_xt" and sopra[1] is not None:
            self.drag = None
            return self.togli_ingresso(sopra[1][0], sopra[1][3])
        if sopra[0] == "punto_out" and sopra[1] in self.punti:
            return self.punto_inizio(sopra[1], cx, cy, tira=True)
        if sopra[0] == "label_x":
            self.drag = None
            return self.togli_etichetta(sopra[1])
        if sopra[0] == "label_l":
            self.drag = None
            return self.lucchetto_label(sopra[1])
        if sopra[0] == "label_m":
            self.drag = None
            return self.menu_label(sopra[1])
        if sopra[0] == "label_r":
            lb = self.etichette[sopra[1]]
            self.drag = None
            self.ridim = dict(k=sopra[1], x0=cx, y0=cy, w0=lb["w"], h0=lb["h"], attesa=None)
            return
        if sopra[0] == "label_t":
            return self.etichetta_inizio(sopra[1], cx, cy)
        if sopra[0] == "punto" and sopra[1] in self.punti:
            return self.punto_inizio(sopra[1], cx, cy, tira=bool(e.state & 0x1))
        if sopra[0] is None:        # nel vuoto (anche dentro una label): una freccia sotto il puntatore apre la sua tavolozza, fra un attimo (il doppio clic mette un dot)
            sg = self.arco_a(cx, cy)
            if sg is not None:
                self.drag = None
                if self.clic is not None:
                    self.cv.after_cancel(self.clic)
                self.clic = self.cv.after(260, lambda: (setattr(self, "clic", None), self.stile_apri(sg)))
                return
        self.premi(e)

    def pezzo_a(self, x, y):
        """Cosa c'e' sotto il punto della tela: ("ctrl", None) il contatore, ("nodo", vid) il pallino, ("carta", vid), o (None, None). Le frecce, i bordi e la barra
        non contano: la carta si prende anche dove una freccia le passa sopra."""
        for it in reversed(self.cv.find_overlapping(x - 1, y - 1, x + 1, y + 1)):
            tags = self.cv.gettags(it)
            if "ctrl" in tags:
                return "ctrl", it
            if "nodo" in tags:
                return "nodo", next((int(t[1:]) for t in tags if t[0] == "n" and t[1:].isdigit()), None)
            if "rete_x" in tags:
                return "rete_x", self._arco
            if "rete_s" in tags:
                return "rete_s", self._arco
            if "rete_c" in tags:
                return "rete_c", getattr(self, "_chiodo", None)
            if "rete_barra" in tags:
                return "rete_barra", None
            if "rete_xt" in tags:
                return "rete_xt", self._arco_t
            if "punto_out" in tags:
                return "punto_out", next((int(t[2:]) for t in tags if t.startswith("po") and t[2:].isdigit()), None)
            if "scambia" in tags:
                return "scambia", next((int(t[1:]) for t in tags if t[0] == "s" and t[1:].isdigit()), None)
            if "punto" in tags:     # i dot stanno sopra le carte: si prendono anche li'
                return "punto", next((int(t[1:]) for t in tags if t[0] == "p" and t[1:].isdigit()), None)
            if "sel_menu" in tags:
                return "sel_menu", None
            for nome_, pre in (("copia_s", "cs"), ("copia_x", "cx")):      # le righe di una copia (12 nov 2026): (k, riga)
                if nome_ in tags:
                    t_ = next((t for t in tags if t.startswith(pre) and "_" in t), None)
                    return (nome_, tuple(int(x) for x in t_[2:].split("_"))) if t_ else (nome_, None)
            for nome_, pre in (("copia_a", "ca"), ("copia_w", "cw")):
                if nome_ in tags:
                    return nome_, next((int(t[2:]) for t in tags if t.startswith(pre) and t[2:].isdigit()), None)
            for nome_, pre in (("nota_i", "ni"), ("nota_b", "nb"), ("nota_n", "nn"), ("label_n", "ln"), ("label_nb", "lb")):      # le note (12 nov 2026)
                if nome_ in tags:
                    return nome_, next((int(t[2:]) for t in tags if t.startswith(pre) and t[2:].isdigit()), None)
            for nome_, pre in (("label_x", "lx"), ("label_l", "ll"), ("label_m", "lm"), ("label_r", "lr"), ("label_t", "lt")):     # la label sta sotto le carte: una carta sopra vince
                if nome_ in tags and self.carta_a(x, y) is None:
                    return nome_, next((int(t[2:]) for t in tags if t.startswith(pre) and t[2:].isdigit()), None)
        vid = self.carta_a(x, y)
        return ("carta", vid) if vid is not None else (None, None)

    def rett(self, vid, dx=0.0, dy=0.0):
        """Il rettangolo della carta che si vede, in pixel della tela: tutta se e' intera, la barra del nome se e' coperta nella pila. None se non si vede."""
        pl = self.pila_di(vid)
        if pl is None or (pl["zona"] != "main" and self.nascosta()):
            return None
        x, _y, s_ = self.pos_px(pl)
        w, h, off, _p = misure(s_)
        k = pl["carte"].index(vid)
        y = self.ys_px(pl)[k]
        intera = vid == pl["carte"][-1] or vid == pl.get("aperta")
        alto = h if intera else (self.ys_px(pl)[k + 1] - y if k + 1 < len(pl["carte"]) else h)
        return x + dx, y + dy, x + w + dx, y + alto + dy

    def carta_a(self, x, y):
        if self.hud_su(x - self.cv.canvasx(0), y - self.cv.canvasy(0)):      # sotto l'HUD le carte non si prendono
            return None
        return self._carta_a(x, y)

    def _carta_a(self, x, y):
        """La carta sotto il punto, dalla geometria delle pile (non dai pezzi disegnati): in ogni punto della carta, compreso il numero delle copie che sporge a
        sinistra; fra due carte che si coprono vince quella sopra (disegnata dopo)."""
        su_fascia = self.in_fascia(y)       # sulla fascia solo le sue carte: le pile del mazzo le passano sotto (12 nov 2026)
        for pl in reversed(self.pile):
            if (pl["zona"] != "main") != su_fascia:
                continue
            px, _py, s_ = self.pos_px(pl)
            w, h, _off, _p = misure(s_)
            sporge = round(14 * max(s_, 0.75))
            ys = self.ys_px(pl)
            for k in range(len(pl["carte"]) - 1, -1, -1):
                if px - sporge <= x <= px + w and ys[k] <= y <= ys[k] + h:
                    return pl["carte"][k]
        return None

    def muovi_barra(self, e):
        d = self.separa
        cy = self.cv.canvasy(e.y)
        self.hs = int(max(0, min(max(370, self.cv.winfo_height() * 0.8), d["hs0"] + cy - d["y0"])))      # fino alla scala piu' grande delle carte, o all'80% della tela
        if d["attesa"] is None:     # un disegno alla volta: i movimenti del mouse arrivano piu' in fretta di un disegno
            def fai():
                d["attesa"] = None
                self.disegna()
            d["attesa"] = self.cv.after(16, fai)

    # ------------------------------------------------ la geometria (in scala M)
    def fascia(self):
        """Dove finisce la fascia della sideboard sulla tela, in pixel: la barra."""
        return self.hs

    def inizio_mazzo(self):
        """Dove comincia il mazzo sulla tela, in pixel."""
        return self.oy("main")

    def posizioni(self, pila):
        """La y di ogni carta della pila (scala M): sfalsate; dopo la carta aperta, lo spazio di una carta intera."""
        _w, h, off, _p = misure(1.0)
        ys, y, dopo = [], pila["y"], False
        for vid in pila["carte"]:
            ys.append(y)
            y += (h + APERTA) if vid == pila.get("aperta") and vid != pila["carte"][-1] else off
        return ys

    def ingombro(self, pila):
        w, h, _off, _p = misure(1.0)
        ys = self.posizioni(pila) or [pila["y"]]
        return pila["x"], pila["y"], pila["x"] + w, ys[-1] + h

    def info(self, vid):
        n = self.voci[vid]["nome"]
        return self.carte_db.get(n) or self.carte_db.get(n.split(" // ")[0].strip()) or {}

    def ordine(self, vid):
        n, c = self.voci[vid]["nome"], self.info(vid)
        tipo = (c.get("tipo") or "").split(" // ")[0]
        terra = "Land" in tipo
        return (terra, 99 if terra else c.get("cmc", 0), "Creature" not in tipo, n)

    def gruppo(self, vid, modo):
        c = self.info(vid)
        tipo = (c.get("tipo") or "").split(" // ")[0]
        if "Land" in tipo:
            return 9
        if modo == "cost":
            return min(int(c.get("cmc", 0) or 0), 7)
        return 0 if "Creature" in tipo else 1 if ("Instant" in tipo or "Sorcery" in tipo) else 2

    # ------------------------------------------------ Arrange: per costo, per gruppi, per connessioni, mixed (13 nov 2026)
    # Autore: «in board editor creiamo 3 diversi tipi di arrange network: per carte costo mana, per gruppi e per connessioni / poi un mixed per casi in cui abbiamo
    # tutti e 3 in modo che cmq il programma stakki in maniera ordinata carte e gruppi senza lasciare gli elementi sparsi in giro». In nessun modo un gruppo si
    # rompe (nome, colore, nota e carte restano insieme): ogni gruppo e' un blocco intero, e il modo decide cosa sta in cima e come stanno le carte dentro. Fino a
    # quel giorno Arrange network rifaceva le pile e lasciava le label dov'erano, vuote o intorno a carte che non c'entravano.
    # Il menu in tre sezioni, accanto ad Add card (13 nov 2026 sera, Autore: «afianco a add card metterei il menù arrange: con gli arragiamenti per carte, poi
    # sezione per gruppi, poi sezione per connessioni / gli arrangiamenti per carte usi quelli più classici, per gruppi li metti sempre uno sotto l'altro, per
    # connessioni fai in modo che le connessioni siano belle visibili»). CARDS sono le colonne classiche dei deck builder (costo, tipo, colore, rarita'), le terre
    # sempre in fondo; GROUPS un gruppo per riga, uno sotto l'altro; CONNECTIONS la rete che scorre da sinistra a destra (sotto).
    SEZIONI_ARRANGE = (
        ("CARDS", (("costo", "By mana cost", "One column per mana value, lands last · the groups below, whole"),
                   ("tipo", "By type", "Creatures, planeswalkers, instants, sorceries, artifacts, enchantments, lands"),
                   ("colore", "By color", "White, blue, black, red, green, multicolor, colorless, lands"),
                   ("rarita", "By rarity", "Mythic, rare, uncommon, common, lands"))),
        ("GROUPS", (("gruppi", "One under the other", "Every group on its own row, its cards side by side · loose cards below by cost"),
                    ("gruppi_costo", "One under the other · by cost", "Every group on its own row, its cards in cost columns"))),
        ("CONNECTIONS", (("rete", "Network", "Parents left, children right, a free lane between columns: every arrow in sight"),
                         ("misto", "Network with groups", "The same flow with whole groups as nodes · the other groups, then the loose cards"))))
    ARRANGE = tuple(v for _s, vv in SEZIONI_ARRANGE for v in vv)
    CRITERI = {"costo": "cost", "tipo": "type", "colore": "color", "rarita": "rarity"}     # i modi della sezione CARDS -> la colonna di ogni carta

    def menu_disponi(self):
        """Il menu del pulsante Arrange: tre sezioni (carte, gruppi, connessioni), ogni modo con la riga che dice cosa fa. Si apre sotto il pulsante, nello stile
        comune dei mini-menu (menu_board)."""
        self.nome_chiudi()
        m = MB.Menu(self.tk, self.F, self.fin, "Arrange the board", chiudi=self.nome_chiudi)
        self._nome_pop = m.p
        for sezione, modi in self.SEZIONI_ARRANGE:
            m.sezione(sezione)
            for modo, nome, riga in modi:
                m.voce(nome, riga, lambda modo=modo: self.disponi_modo(modo, inquadra=True))
        m.piede("Groups stay whole in every mode · Undo brings the board back")
        m.p.voci = m.voci
        return m.posa(sotto=self.b_arrange)

    def colonna(self, vid, crit):
        """La colonna di una carta negli Arrange per carte: le classiche dei deck builder, le terre sempre in fondo (99). crit: cost, type, color, rarity.
        Colore e rarita' da carte_db se li ha («colori», «rarita»: le prove), se no dal database di Arena (colore_rarita_arena)."""
        if crit == "cost":
            return self.gruppo(vid, "cost")
        tipi = self.tipi_di(vid)
        if "land" in tipi:
            return 99
        if crit == "type":
            return next((i for i, t in enumerate(("creature", "planeswalker", "instant", "sorcery", "artifact", "enchantment", "battle")) if t in tipi), 7)
        c, nome = self.info(vid), self.voci[vid]["nome"]
        col_a, rar_a = colore_rarita_arena(nome) if ("colori" not in c or "rarita" not in c) else ("", None)
        if crit == "color":
            col = c.get("colori", col_a) or ""
            return 6 if not col else 5 if len(col) > 1 else "WUBRG".index(col) if col in "WUBRG" else 6
        r = c.get("rarita", rar_a)
        r = {"M": 5, "R": 4, "U": 3, "C": 2}.get(r, r)
        return {5: 0, 4: 1, 3: 2, 2: 3, 1: 3}.get(r, 4)

    def struttura(self):
        """Chi sta in quale gruppo, prima di riordinare: ogni pila del mazzo va alla label piu' piccola che contiene il suo centro (come quando la label si sposta),
        ogni label alla label piu' piccola che la contiene tutta; le copie dei gruppi non contengono niente. -> ({k: [vid]}, {k: label madre o None}, [vid liberi])."""
        E = self.etichette
        area = lambda k: E[k]["w"] * E[k]["h"]
        dentro = lambda k, x, y: E[k]["x"] <= x <= E[k]["x"] + E[k]["w"] and E[k]["y"] <= y <= E[k]["y"] + E[k]["h"]
        piene = [k for k, lb in enumerate(E) if not lb.get("copia")]
        padre = {}
        for k, lb in enumerate(E):      # a parita' d'area decide l'indice: niente giri
            cand = [j for j in piene if j != k and (area(j) > area(k) or (area(j) == area(k) and j < k))
                    and dentro(j, lb["x"], lb["y"]) and dentro(j, lb["x"] + lb["w"], lb["y"] + lb["h"])]
            padre[k] = min(cand, key=lambda j: (area(j), j)) if cand else None
        carte, libere = {k: [] for k in piene}, []
        for pl in self.pile:
            if pl["zona"] != "main":
                continue
            r = self.ingombro(pl)
            cand = [k for k in piene if dentro(k, (r[0] + r[2]) / 2, (r[1] + r[3]) / 2)]
            (carte[min(cand, key=lambda j: (area(j), j))] if cand else libere).extend(pl["carte"])
        return carte, padre, libere

    def disponi_rete(self, salva=True):
        """Il vecchio Arrange network: ora e' il modo By connections. -> quante carte libere ha messo in rete (0: niente connessioni, niente toccato)."""
        return self.disponi_modo("rete", salva=salva)

    def disponi_modo(self, modo="misto", salva=True, inquadra=False):
        """Riordina il mazzo sul foglio in uno dei modi di ARRANGE, sulla griglia, senza sovrapposizioni. I gruppi restano interi: una label e' un blocco con le
        sue carte (e le label che ha dentro) e si ridimensiona sul contenuto; la copia di un gruppo va accanto al suo gruppo.
        CARDS (costo, tipo, colore, rarita): le carte libere in colonne (colonna), le terre in fondo; sotto i gruppi, con le carte nelle stesse colonne.
        GROUPS (gruppi, gruppi_costo): ogni gruppo su una riga sua, uno sotto l'altro, con le carte una accanto all'altra o in colonne per costo, e i gruppi che
        ha dentro ancora uno sotto l'altro; sotto le carte libere per costo.
        CONNECTIONS (rete, misto): la rete da sinistra a destra, i padri a sinistra dei figli, una colonna vuota fra un livello e l'altro, ognuno all'altezza
        dei suoi padri e dei suoi figli; i giri chiusi rotti dove si chiudono; in misto un gruppo e' un nodo, e una connessione fra una sua carta e una carta
        fuori lo lega. Sideboard e comandante restano; i dot tornano a meta' fra ingressi e uscite.
        -> CARDS le carte libere; GROUPS i gruppi; CONNECTIONS i nodi della rete. La rete senza connessioni e GROUPS senza gruppi non toccano niente e lo
        dicono (0)."""
        self.sfiltra()      # col filtro acceso le carte nascoste stavano nelle pile vecchie: finirebbero in due pile (il disegno rifiltra)
        w, h, off, _p = misure(1.0)
        su = lambda y: -(-y // PASSO_Y) * PASSO_Y               # il passo verticale della griglia, per eccesso
        TOP = su(TIT_L + PAD_L)                                 # dal bordo alto della label alla prima carta: il titolo e l'aria, sulla griglia
        LX = PASSO_X // 2 - (PAD_L + 14)                        # la colonna del blocco -> il bordo sinistro della label (le carte a mezza colonna)
        DW = PASSO_X + SPAZIO - 2 * PAD_L - 20                  # colonne del blocco -> larghezza della label (a destra l'aria del pallino)
        W_, _H = self.misura_tela()
        larga = max(4, int((max(800, W_ / self.zoom) - MARGINE) // PASSO_X))       # quante colonne stanno nella finestra: li' si va a capo
        E = self.etichette
        carte_l, padre, libere = self.struttura()
        main = {}
        for i, v in self.voci.items():
            if v["zona"] == "main":
                main.setdefault(v["nome"], i)
        archi = [(p_, c_) for p_, c_, _f in self.rete.legami(set(main)) if p_ != c_]
        archi += [(p_, c_) for q in self.punti for (p_, c_), r in self.vie.items() if r == q and p_ in main and c_ in main and (p_, c_) not in archi]
        if modo == "rete" and not archi:
            self.filtra()
            self.dici("No connections between the deck's cards to arrange")
            return 0
        if modo in ("gruppi", "gruppi_costo") and not E:
            self.filtra()
            self.dici("No groups to arrange: select some cards and make one from ≡ on the frame")
            return 0
        nuove = []

        def blocco_pila(vids):
            vids = list(vids)
            return dict(c=1, h=h + (len(vids) - 1) * off, metti=lambda bx, by: nuove.append(dict(zona="main", x=bx, y=by, carte=vids, aperta=None)))

        def pile_per(vids, crit="cost"):
            """Le carte in colonne secondo crit (colonna), ognuna in ordine di costo; oltre MAX_PILA la colonna si divide."""
            gr = collections.OrderedDict()
            for i in sorted(vids, key=self.ordine):
                gr.setdefault(self.colonna(i, crit), []).append(i)
            return [blocco_pila(cc[a:a + MAX_PILA]) for _g, cc in sorted(gr.items()) for a in range(0, len(cc), MAX_PILA)]
        pile_costo = pile_per

        def impacca(blocchi, max_c):
            """In righe, da sinistra, a capo oltre max_c colonne. -> le posizioni (colonna, y), le colonne usate, l'altezza."""
            col = y = alta = usate = 0
            pos = []
            for b in blocchi:
                if col and col + b["c"] > max_c:
                    y, col, alta = su(y + alta + SPAZIO * 2), 0, 0
                pos.append((col, y))
                col += b["c"]
                alta, usate = max(alta, b["h"]), max(usate, col)
            return pos, usate, (y + alta if blocchi else 0)

        def blocco_label(k, stile, impila=False):
            """Il blocco di un gruppo. stile: «fila» (le carte una accanto all'altra, al massimo sei per riga) o un criterio di colonna (cost, type, color,
            rarity: le carte in colonne). impila: le carte su una riga che va a capo nella finestra, e ogni gruppo che ha dentro su una riga sua, sotto."""
            lb = E[k]
            if lb.get("copia"):         # la copia di un gruppo: le sue righe di carte, la misura la decide lei
                self.misura_copia(k)
                T = max(2, -(-(lb["w"] + DW) // PASSO_X))

                def metti_c(bx, by):
                    lb["x"], lb["y"] = bx + LX, by
                return dict(c=T, h=lb["h"], metti=metti_c)
            vids = sorted(carte_l.get(k, []), key=self.ordine)
            figlie = sorted((j for j in padre if padre[j] == k), key=lambda j: (E[j]["y"], E[j]["x"]))
            carte_b = [blocco_pila([v]) for v in vids] if stile == "fila" else pile_per(vids, stile)
            sotto = [blocco_label(j, stile, impila) for j in figlie]
            dentro = carte_b + sotto
            if impila:      # uno sotto l'altro: le carte su righe larghe quanto la finestra, poi un gruppo per riga
                pos, cols, alta = impacca(carte_b, max(3, larga - 2))
                for b in sotto:
                    y_ = su(alta + SPAZIO * 2) if alta else 0
                    pos.append((0, y_))
                    cols, alta = max(cols, b["c"]), y_ + b["h"]
            else:
                pos, cols, alta = impacca(dentro, 6 if stile == "fila" else 10 ** 6)
            cols, alta = max(cols, 1), max(alta, h)         # una label vuota tiene il posto di una carta: ci si lascia una carta dentro
            T, H = max(cols + 1, 3), TOP + max(alta, h) + PAD_L     # almeno tre colonne: il nome si legge accanto alle icone del titolo

            def metti(bx, by):
                lb["x"], lb["y"], lb["w"], lb["h"] = bx + LX, by, T * PASSO_X - DW, H
                for b, (c, y) in zip(dentro, pos):
                    b["metti"](bx + PASSO_X // 2 + c * PASSO_X, by + TOP + y)
            return dict(c=T, h=H, metti=metti)

        def ordina_gruppi(ks):
            """I gruppi nell'ordine in cui stanno sul foglio (righe dall'alto, da sinistra), ognuno seguito dalle sue copie."""
            ks = list(ks)
            base = sorted((k for k in ks if not E[k].get("copia")), key=lambda k: (E[k]["y"], E[k]["x"]))
            copie = sorted((k for k in ks if E[k].get("copia")), key=lambda k: (E[k]["y"], E[k]["x"]))
            out = []
            for k in base:
                out.append(k)
                out += [j for j in copie if j not in out and E[k].get("id") and E[j].get("origine") == E[k].get("id")]
            return out + [j for j in copie if j not in out]

        y0 = 0

        def sezione(blocchi):
            nonlocal y0
            if not blocchi:
                return
            pos, _cols, alta = impacca(blocchi, larga)
            for b, (c, y) in zip(blocchi, pos):
                b["metti"](MARGINE + c * PASSO_X, y0 + y)
            y0 = su(y0 + alta + 3 * PASSO_Y)

        def rete(nodo_di, blocco_di, chiave):
            """La rete a livelli coi nodi che nodo_di da' alle carte (None: fuori). -> i nodi messi."""
            nonlocal y0
            ar = []
            for p_, c_ in archi:
                a, b = nodo_di(p_), nodo_di(c_)
                if a is not None and b is not None and a != b and (a, b) not in ar:
                    ar.append((a, b))
            nodi = sorted({n for e in ar for n in e}, key=chiave)
            if not nodi:
                return []
            figli, padri, stato, tieni = collections.defaultdict(list), collections.defaultdict(list), {}, []

            def visita(n):      # i giri chiusi: un arco che torna su un antenato nella visita si salta
                stato[n] = 1
                for a, b in ar:
                    if a == n and stato.get(b) != 1:
                        tieni.append((a, b))
                        if b not in stato:
                            visita(b)
                stato[n] = 2
            for n in nodi:
                if n not in stato:
                    visita(n)
            for a, b in dict.fromkeys(tieni):
                figli[a].append(b)
                padri[b].append(a)
            livello = {}

            def liv(n):
                if n not in livello:
                    livello[n] = 0 if not padri[n] else 1 + max(liv(a) for a in padri[n])
                return livello[n]
            for n in nodi:
                liv(n)
            # chi non ha padri va subito prima del suo primo figlio: una freccia che salta una colonna passerebbe sopra le carte di quella in mezzo
            for n in sorted(nodi, key=lambda n: -livello[n]):
                if not padri[n] and figli[n]:
                    livello[n] = min(livello[c] for c in figli[n]) - 1
            usati = {v: i for i, v in enumerate(sorted(set(livello.values())))}
            colonne = collections.defaultdict(list)
            for n in nodi:
                livello[n] = usati[livello[n]]
                colonne[livello[n]].append(n)
            k_max = max(colonne)
            media = lambda n, vicini, pos, dopo: (sum(pos[m] for m in vicini[n] if m in pos) / sum(1 for m in vicini[n] if m in pos)
                                                   if any(m in pos for m in vicini[n]) else dopo)
            for _passata in range(4):       # l'ordine nella colonna per baricentro dei vicini: meno incroci
                for k in range(1, k_max + 1):
                    pos = {n: i for i, n in enumerate(colonne[k - 1])}
                    colonne[k].sort(key=lambda n: media(n, padri, pos, len(pos)))
                for k in range(k_max - 1, -1, -1):
                    pos = {n: i for i, n in enumerate(colonne[k + 1])}
                    colonne[k].sort(key=lambda n: media(n, figli, pos, len(pos)))
            blocchi = {n: blocco_di(n) for n in nodi}
            # La rete scorre da sinistra a destra (13 nov 2026 sera, Autore: «per connessioni fai in modo che le connessioni siano belle visibili»). Le
            # frecce vanno dal pallino alla base del padre a quello alla base del figlio: coi padri sopra i figli ogni freccia arrivava al figlio passando
            # dietro tutta la sua carta. Coi padri a sinistra la freccia corre sotto le carte, orizzontale quando padre e figlio stanno alla stessa altezza
            # (ognuno si mette all'altezza media dei padri, poi i padri a quella dei figli), e fra una colonna e l'altra resta una colonna vuota, la corsia.
            # Ogni livello scende di una riga della griglia (SCALINO) rispetto ai suoi padri: alla stessa altezza le frecce fra due gruppi correvano tutte
            # sulla stessa riga sotto le carte, una sopra l'altra, e ne sembrava una sola (la foto sul mazzo vero, 13 nov 2026). Con lo scalino e la corsia la
            # pendenza e' 1/13: all'altezza del bordo della carta del figlio la freccia passa ancora sotto la carta.
            CORSIA, VG, SCALINO = 1, 3 * PASSO_Y, PASSO_Y
            x_col, c = {}, 0
            for k in range(k_max + 1):
                x_col[k] = c
                c += max(blocchi[n]["c"] for n in colonne[k]) + CORSIA
            ypos = {}

            def impila_colonna(k, voluto):
                fondo = 0
                for n in colonne[k]:
                    y_ = su(max(voluto(n, fondo), fondo))
                    ypos[n] = y_
                    fondo = y_ + blocchi[n]["h"] + VG
            altezza_di = lambda vicini, n, fondo, d: (sum(ypos[m] for m in vicini[n] if m in ypos) / sum(1 for m in vicini[n] if m in ypos) + d
                                                      if any(m in ypos for m in vicini[n]) else fondo)
            for k in range(k_max + 1):
                impila_colonna(k, lambda n, f: altezza_di(padri, n, f, SCALINO))
            for k in range(k_max - 1, -1, -1):
                impila_colonna(k, lambda n, f: altezza_di(figli, n, f, -SCALINO) if figli[n] else ypos.get(n, f))
            alto = min(ypos.values())       # il backward pass puo' portare un padre sopra lo zero: la rete riparte da y0
            ypos = {n: y_ - alto for n, y_ in ypos.items()}
            for n in nodi:
                blocchi[n]["metti"](MARGINE + x_col[livello[n]] * PASSO_X, y0 + ypos[n])
            y0 = su(y0 + max(ypos[n] + blocchi[n]["h"] for n in nodi) + 110)     # con l'aria per le frecce sotto l'ultima riga
            return nodi

        cima = [k for k in range(len(E)) if padre[k] is None]
        sciolte = set(libere)
        gr_s = lambda n: f"{n} group{'s' * (n != 1)}"
        if modo in self.CRITERI:
            crit = self.CRITERI[modo]
            sezione(pile_per(libere, crit))
            sezione([blocco_label(k, crit) for k in ordina_gruppi(cima)])
            per = {"cost": "mana cost", "type": "type", "color": "color", "rarity": "rarity"}[crit]
            n_fatti, cosa = len(libere), f"Arranged by {per}: the loose cards in columns, lands last · {gr_s(len(cima))} below, whole"
        elif modo in ("gruppi", "gruppi_costo"):
            for k in ordina_gruppi(cima):       # uno sotto l'altro: ogni gruppo su una riga sua, a sinistra
                b = blocco_label(k, "fila" if modo == "gruppi" else "cost", impila=True)
                b["metti"](MARGINE, y0)
                y0 = su(y0 + b["h"] + 3 * PASSO_Y)
            sezione(pile_per(libere, "cost"))
            n_fatti, cosa = len(cima), f"Arranged by groups: {gr_s(len(cima))} one under the other · the loose cards below by cost"
        elif modo == "rete":
            nodi = rete(lambda n: n if main[n] in sciolte else None, lambda n: blocco_pila([main[n]]), lambda n: self.ordine(main[n]))
            messe = {main[n] for n in nodi}
            sezione([blocco_label(k, "cost") for k in ordina_gruppi(cima)])
            sezione(pile_costo([v for v in libere if v not in messe]))
            n_fatti = len(nodi)
            cosa = (f"Arranged as a network: {len(nodi)} linked cards, parents left, children right · groups and the other cards below" if nodi
                    else "The connections all touch cards in groups: groups and loose cards arranged, try Network with groups")
        else:
            top = {}
            for k, vv in carte_l.items():
                t = k
                while padre[t] is not None:
                    t = padre[t]
                for v in vv:
                    top[v] = t
            nodo = lambda n: n if main[n] in sciolte else ("L", top[main[n]]) if main[n] in top else None
            chiave = lambda n: (False, -1, False, "~" + E[n[1]]["nome"]) if isinstance(n, tuple) else self.ordine(main[n])
            nodi = rete(nodo, lambda n: blocco_label(n[1], "fila") if isinstance(n, tuple) else blocco_pila([main[n]]), chiave)
            in_rete = {n[1] for n in nodi if isinstance(n, tuple)}
            messe = {main[n] for n in nodi if not isinstance(n, tuple)}
            altri = [k for k in ordina_gruppi(cima) if k not in in_rete]
            sezione([blocco_label(k, "fila") for k in altri])
            sezione(pile_costo([v for v in libere if v not in messe]))
            n_fatti = len(nodi)
            cosa = (f"Network with groups: {len(messe)} cards and {gr_s(len(in_rete))} in the flow · {gr_s(len(altri))} more, then the loose cards by cost"
                    if nodi else f"Network with groups: no connections · {gr_s(len(altri))}, then the loose cards by cost")
        self.pile = [pl for pl in self.pile if pl["zona"] != "main"] + nuove
        self.vuota_sel()
        self.rimetti_punti(main)
        self.disegna()
        if salva:
            self.salva()
        if inquadra:
            self.inquadra_tutto()
        self.dici(cosa)
        return n_fatti

    def rimetti_punti(self, main):
        """I dot a meta' fra i loro ingressi e le loro uscite (due giri, per le catene)."""
        w, h, _off, _p = misure(1.0)
        for _giro in range(2):
            for q in self.punti:
                fonti, uscite = [], []
                for kk, v in self.ingressi(q):
                    if kk == "c" and v in main:
                        pl = self.pila_di(main[v])
                        fonti.append((pl["x"] + w / 2, pl["y"] + h + 9))
                    elif kk == "p" and v in self.punti:
                        fonti.append((self.punti[v]["x"], self.punti[v]["y"]))
                for (_a, c_), r in self.vie.items():
                    if r == q and c_ in main:
                        pl = self.pila_di(main[c_])
                        uscite.append((pl["x"] + w / 2, pl["y"] + h + 9))
                uscite += [(self.punti[r]["x"], self.punti[r]["y"]) for r in self.punti if ("p", q) in self.ingressi(r)]
                pts = [(sum(x_ for x_, _y in g) / len(g), sum(y_ for _x, y_ in g) / len(g)) for g in (fonti, uscite) if g]
                if pts:
                    gx, gy = a_griglia(sum(x_ for x_, _y in pts) / len(pts) + (0 if len(pts) > 1 else 40),
                                       sum(y_ for _x, y_ in pts) / len(pts) + (0 if len(pts) > 1 else 40), mezza=True)
                    # un dot sopra una carta o un gruppo non si vede e non si prende: scende sotto l'ostacolo (13 nov 2026, dalle foto di Arrange)
                    ostacoli = [self.ingombro(pl) for pl in self.pile if pl["zona"] == "main"]
                    ostacoli += [(lb["x"], lb["y"], lb["x"] + lb["w"], lb["y"] + lb["h"]) for lb in self.etichette]
                    for _ in range(12):
                        r_ = next((r_ for r_ in ostacoli if r_[0] - 12 <= gx <= r_[2] + 12 and r_[1] - 12 <= gy <= r_[3] + 34), None)
                        if r_ is None:
                            break
                        gy = a_griglia(gx, r_[3] + 48, mezza=True)[1]
                    self.punti[q]["x"], self.punti[q]["y"] = gx, gy

    def fascia_sta(self):
        """Le carte della fascia stanno tutte nella larghezza della finestra? (La fascia e' ferma in cima alla finestra: quel che esce a destra non si vede mai.
        Sotto l'HUD, semitrasparente, una carta si vede ancora: la disposizione salvata resta.)"""
        if self.nascosta():
            return True
        w, _h, _off, _p = misure(1.0)
        W_, _H = self.misura_tela()
        destra = max((pl["x"] + w for pl in self.pile if pl["zona"] != "main"), default=0) * self.sf()
        return destra <= W_ - 8

    def pile_fascia(self):
        """Le pile della fascia per l'apertura: prima il comandante e il compagno, poi la sideboard per costo, una carta per pila finche' stanno nella larghezza
        della fascia (fuori dall'HUD); se no a pile di 2 o 3 (la fascia ne mostra una e due sfalsate). Fino al 13 nov 2026 una carta per pila sempre: con 15 carte
        diverse in sideboard le ultime finivano oltre il bordo destro della finestra, e la fascia, ferma, non si sposta mai per mostrarle."""
        w, _h, _off, _p = misure(1.0)
        W_, _H = self.misura_tela()
        s_ = max(self.sf(), SPARISCE)
        posti = max(1, int((W_ - (INFO_L + 28) - MARGINE) / s_ // (w + SPAZIO)))
        cmd = sorted((i for i, v in self.voci.items() if v["zona"] == "cmd"), key=self.ordine)
        side = sorted((i for i, v in self.voci.items() if v["zona"] == "side"), key=self.ordine)
        liberi = max(1, posti - len(cmd) - (1 if cmd else 0))
        per = 1 if len(side) <= liberi else min(3, -(-len(side) // liberi))
        pile, x = [], MARGINE
        for i in cmd:
            pile.append(dict(zona="cmd", x=x, y=0, carte=[i], aperta=None))
            x += w + SPAZIO
        if cmd:
            x += SPAZIO
        for a in range(0, len(side), per):
            pile.append(dict(zona="side", x=x, y=0, carte=side[a:a + per], aperta=None))
            x += w + SPAZIO
        return pile

    def disponi(self, modo="cost", salva=True):
        """Le pile in ordine: per costo (una colonna per costo, le terre in fondo) o per tipo (creature, istantanei e stregonerie, il resto, le terre).
        Nella fascia le carte una accanto all'altra, prima il comandante e il compagno. Le pile si allungano quanto basta perche' il mazzo stia in una riga."""
        self.sfiltra()      # le carte nascoste dal filtro tornano prima: se no finirebbero in due pile (il disegno rifiltra)
        W_, _H = self.misura_tela()
        # la larghezza vera della tela (13 nov 2026): la finestra appena nata e' ancora nascosta e la tela misurava 1 pixel, quindi «larga» era 800 e le colonne
        # dei costi si univano in 4 (1, 2, 3+ e le terre). Se l'HUD copre l'angolo del mazzo, ci pensa l'inquadratura dell'apertura
        larga = max(800, W_ / self.zoom)
        w, h, off, _p = misure(1.0)
        pile = self.pile_fascia()
        gruppi = collections.OrderedDict()
        for i in sorted((i for i, v in self.voci.items() if v["zona"] == "main"), key=self.ordine):
            gruppi.setdefault(self.gruppo(i, modo), []).append(i)
        entrano = max(1, int((larga - MARGINE) // (w + SPAZIO)))
        # piu' colonne di quante ne entrano (il tavolo stretto del builder): si uniscono i costi piu' alti, le terre restano a parte; a capo una pila finirebbe sotto il fondo
        while len(gruppi) > entrano:
            magie = [k for k in sorted(gruppi) if k != 9]
            if len(magie) < 2:
                break
            gruppi[magie[-2]] = gruppi[magie[-2]] + gruppi.pop(magie[-1])
        lunga =next((k for k in (MAX_PILA, 12, 14, 16, 20) if sum(-(-len(c) // k) for c in gruppi.values()) <= entrano), 20)
        x, y, alta = MARGINE, 0, 0
        for _g, carte in sorted(gruppi.items()):
            for a in range(0, len(carte), lunga):
                pezzo = carte[a:a + lunga]
                if x + w > larga - MARGINE and x > MARGINE:        # a capo: una riga nuova sotto la piu' alta, sulla griglia
                    x, y, alta = MARGINE, -(-(y + alta + SPAZIO * 2) // PASSO_Y) * PASSO_Y, 0
                pile.append(dict(zona="main", x=x, y=y, carte=pezzo, aperta=None))
                alta = max(alta, h + (len(pezzo) - 1) * off)
                x += w + SPAZIO
        self.pile = pile
        self.disegna()
        if salva:
            self.salva()

    # ------------------------------------------------ il disegno
    def disegna(self):
        cv = self.cv
        self.nascondi()
        self.sfiltra()          # il filtro per tipo si rifa' a ogni disegno: le carte nuove, le pile rifatte, le copie cambiate
        self.filtra()
        if getattr(self, "c_filtri", None) is not None:
            self.disegna_filtri()
        cv.delete("all")
        self._puntini, self._bagliore = None, None
        self.metti_puntini()
        L = max(cv.winfo_width(), 400)
        hs = self.hs
        self._fx, self._fy = cv.canvasx(0), cv.canvasy(0)
        fx, fy = self._fx, self._fy
        conti = collections.Counter()
        for v in self.voci.values():
            conti[v["zona"]] += v["q"]
        destra = max([L] + [self.ingombro_px(pl)[2] + MARGINE for pl in self.pile])
        # niente piu' il rettangolo scuro «sopra il mazzo» (dal foglio a -50000 fino alla barra): da quando la fascia sta ferma in cima alla finestra, scorrendo
        # in su o inquadrando un foglio con carte sopra l'inizio del mazzo appariva come una seconda fascia vuota, con le carte dentro (13 nov 2026)
        cv.create_rectangle(fx - 50000, fy - 50000, fx + 50000, fy + hs, fill=C["fondo"], width=0, tags=("fascia", "fascia_fondo"))     # la fascia, in cima alla vista
        if hs >= 22:
            cv.create_text(fx + MARGINE, fy + 8, text=f"SIDEBOARD · {conti['side']}", fill=C["titolo"], font=self.F(8, True), anchor="nw", tags=("fascia",))
        cv.create_text(MARGINE, hs + 8, text=f"DECK · {conti['main']}" + ("" if hs >= 22 else f"   ·   SIDEBOARD · {conti['side']}"), fill=C["titolo"], font=self.F(8, True),
                       anchor="nw")
        cmd = [pl for pl in self.pile if pl["zona"] == "cmd"]
        if cmd and not self.nascosta():
            x0, y0 = min(self.ingombro_px(pl)[0] for pl in cmd) - 16 * self.sf(), fy + ETICHETTA - 6
            x1, y1 = max(self.ingombro_px(pl)[2] for pl in cmd) + 6, max(self.ingombro_px(pl)[3] for pl in cmd) + 6
            cv.create_rectangle(x0, y0, x1, y1, outline="#c9a227", width=1, tags=("fascia",))
            cv.create_text(x0 + 4, y0 - 2, text="COMPANION" if all(self.voci[i]["nome"] in self.compagno for pl in cmd for i in pl["carte"]) else "COMMANDER",
                           fill="#c9a227", font=self.F(7, True), anchor="sw", tags=("fascia",))
        self.disegna_etichette()        # le label sotto le carte
        legate = {n for p_, c_, _f in self.rete.legami({v["nome"] for v in self.voci.values()}) for n in (p_, c_)}      # le carte coperte con una freccia hanno il pallino piccolo
        tot = conti["main"] + conti["side"]
        self.disegna_info(conti, tot)
        for pl in sorted(self.pile, key=lambda q: q["zona"] != "main"):       # prima il mazzo, poi la fascia sopra
            if pl["zona"] != "main" and self.nascosta():        # la fascia chiusa: le sue carte non ci sono piu'
                continue
            x, _y, s_ = self.pos_px(pl)
            ys = self.ys_px(pl)
            for k, vid in enumerate(pl["carte"]):
                intera = vid == pl["carte"][-1] or vid == pl.get("aperta")
                self.carta(vid, x, ys[k], intera and pl["zona"] != "cmd", s_)
                if intera or self.voci[vid]["nome"] in legate:
                    self.nodo(vid)
        bb = cv.bbox("all") or (0, 0, L, 400)
        H = max(cv.winfo_height(), 300)      # mezza finestra d'aria a destra e sotto: col tasto centrale il foglio si sposta anche quando il mazzo ci sta tutto
        cv.configure(scrollregion=(0, 0, max(bb[2] + MARGINE, L) + L // 2, max(bb[3] + MARGINE * 2, H) + H // 2))
        self.barra(destra)
        self.disegna_rete()
        self.disegna_note()
        self.disegna_sel()
        self.disegna_outliner()
        cv.tag_raise("nodo")
        self.fascia_sopra()

    def tag_fascia(self):
        """I tag di tutto quello che sta nella fascia della sideboard: la fascia, le sue carte e i loro strumenti e note."""
        tags = {"fascia"}
        for pl in self.pile:
            if pl["zona"] != "main":
                for vid in pl["carte"]:
                    tags |= {f"c{vid}", f"n{vid}", f"s{vid}", f"ni{vid}", f"nn{vid}", f"nb{vid}"}
        return tags

    def fascia_sopra(self):
        """La fascia sopra il foglio del mazzo (che le scorre sotto), le sue carte sopra la fascia, la barra e l'HUD sopra tutto."""
        cv = self.cv
        if self.gpu:        # lo zoom immediato della rotella non la ingrandisce (Autore, 12 nov 2026: «sistema lo zoom sideboard»)
            cv.senza_zoom(set() if self.nascosta() else self.tag_fascia())
        if self.nascosta():
            cv.tag_raise("barra")
            return
        cv.tag_raise("fascia")
        for pl in self.pile:
            if pl["zona"] != "main":
                for vid in pl["carte"]:
                    cv.tag_raise(f"c{vid}")
        for t_ in ("punto", "nodo", "scambia", "nota", "nota_b", "label_nb", "sel", "sel_menu", "barra"):        # gli strumenti restano sopra le carte, come sempre
            cv.tag_raise(t_)
        if not self.gpu:
            cv.tag_raise("hud")

    def barra(self, destra):
        """La barra fra la fascia e il foglio: una linea e, nel mezzo, il segno ▲▼ disegnato che dice che si trascina su e giu'. Sopra le carte."""
        cv = self.cv
        L = max(cv.winfo_width(), 400)
        y = self._fy + self.hs
        cv.create_line(-50000, y, 50000, y, fill=C["filo"], width=1, tags=("barra", "fascia"))
        cx = cv.canvasx(0) + L / 2
        # con la fascia chiusa del tutto (hs 0: in sola lettura senza sideboard) il segno resta intero sotto il bordo alto, non tagliato a meta' (13 nov 2026)
        cv.create_image(cx - 30, max(y - 9, self._fy), image=segno_barra(), anchor="nw", tags=("barra", "fascia"))
        cv.tag_raise("barra")

    def carta(self, vid, x, y, intera, s=1.0):
        """Una carta: l'immagine con l'ombra (o il riquadro col nome finche' non c'e'), il numero delle copie accanto al nome e, se si vede intera e il mazzo si cambia,
        il contatore. Tutti i pezzi col tag della carta, cosi' si muovono insieme."""
        cv, F = self.cv, self.F
        w, h, _off, p = misure(s)
        v = self.voci[vid]
        tag = ("carta", f"c{vid}")
        g2 = foto_gpu(v["nome"]) if self.gpu else None
        im = None if self.gpu else foto_carta(self.tk, v["nome"], s)
        if g2 is not None:          # sulla scheda: la carta a 2x, scalata dalla scheda; lo zoom non la rifa'
            k = s / 2
            cv.create_image(x - g2[1] * k, y - g2[1] * k, image=g2[0], anchor="nw", tags=tag, scala=k)
        elif im is not None:
            cv.create_image(x - p, y - p, image=im, anchor="nw", tags=tag)
        else:
            cv.create_rectangle(x, y, x + w, y + h, fill=C["cap"], outline=C["filo"], tags=tag)
            cv.create_text(x + w / 2 + 6, y + 10, text=v["nome"], width=w - 28, fill=C["testo"], font=F(8, True), anchor="n", justify="center", tags=tag)
        # il numero delle copie, sul bordo sinistro all'altezza del nome: si legge anche quando la carta e' coperta dalle altre
        bs = max(s, 0.75)       # il numero resta leggibile anche sulle carte piccole (la fascia bassa, lo zoom indietro)
        bl, bh = round(26 * bs), round(17 * bs)
        cy = y + h * 0.072
        # sulle carte piccole la pillola sta dentro la carta, in alto a sinistra (13 nov 2026, Autore: «sistema i contatori che coprono le carte»): sporgendo a
        # sinistra copriva la carta accanto, perche' fra due pile restano 20 pixel per lo zoom
        px_ = x - round(14 * bs) if s >= 0.75 else x + 2
        cv.create_image(px_, cy - bh / 2, image=pillola(bl, bh, (16, 16, 20, 235), C["accento"]), anchor="nw", tags=tag)
        cv.create_text(px_ + bl / 2, cy, text=f"{v['q']}x", fill="#ffffff", font=F(max(7, round(8 * bs)), True), tags=tag)
        if intera and self.modifica:
            self.contatore_disegna(vid, x, y, w, h, s)

    def contatore_disegna(self, vid, x, y, w, h, s=1.0):
        """Il contatore sulla carta intera, in basso al centro: − N +. Il + si spegne al limite. Sempre della stessa misura, a qualunque zoom, come pallini, ⇄, icone
        e linee (Autore, 10 nov 2026: «lascia che i pulsanti vari e le linee mantengano la loro dimensione anche zoom in / non rimpicciolirli»); prima scalava con
        la carta."""
        cv, F = self.cv, self.F
        v = self.voci[vid]
        # Mai sopra le carte accanto (13 nov 2026, Autore: «sistema i contatori che coprono le carte»): a misura fissa il contatore e' largo 98 pixel, e a zoom
        # basso la carta ne ha 44. Pieno quando ci sta (CONT_PIENO); piu' stretta, solo − e + piccoli dentro gli angoli in basso della carta (il numero lo dice
        # la pillola «Nx»); sotto CONT_MINIMO niente: per cambiare le copie ci si avvicina.
        if w < CONT_MINIMO:
            return
        if w < CONT_PIENO:
            lato = 18 if w >= 64 else 15
            pieno = self.totale(v["nome"]) >= self.limite(v["nome"])
            yb = y + h - lato - 4
            cv.create_image(x + 3, yb, image=tondo_segno(lato, C["cap"], "-", "#ffffff"), anchor="nw", tags=("ctrl", f"meno{vid}", f"c{vid}"))
            cv.create_image(x + w - 3 - lato, yb, image=tondo_segno(lato, C["cap"] if pieno else C["accento"], "+", C["muto"] if pieno else "#ffffff"),
                            anchor="nw", tags=("ctrl", f"piu{vid}", f"c{vid}"))
            return
        s = 1.0
        lato = round(24 * s)
        pl_l, pl_h = round(98 * s), round(32 * s)
        cx, cy = x + w / 2, y + h - pl_h / 2 - round(10 * s)
        cv.create_image(cx - pl_l / 2, cy - pl_h / 2, image=pillola(pl_l, pl_h, (16, 16, 20, 225), C["filo"]), anchor="nw", tags=("carta", f"c{vid}"))
        pieno = self.totale(v["nome"]) >= self.limite(v["nome"])
        cv.create_image(cx - pl_l / 2 + round(4 * s), cy - lato / 2, image=tondo_segno(lato, C["cap"], "-", "#ffffff"), anchor="nw", tags=("ctrl", f"meno{vid}", f"c{vid}"))
        cv.create_image(cx + pl_l / 2 - round(4 * s) - lato, cy - lato / 2, image=tondo_segno(lato, C["cap"] if pieno else C["accento"], "+", C["muto"] if pieno else "#ffffff"),
                        anchor="nw", tags=("ctrl", f"piu{vid}", f"c{vid}"))
        cv.create_text(cx, cy, text=str(v["q"]), fill="#ffffff", font=F(max(9, round(11 * s)), True), tags=("carta", f"c{vid}"))

    # ------------------------------------------------ il contatore e il limite
    def limite(self, nome):
        if self._limite is not None:
            return self._limite(nome)
        try:
            import costruttore_mazzi
            return costruttore_mazzi.limite(nome, self.formato, self.carte_db)
        except Exception:
            return 10 ** 6 if nome in MS.BASI else 4

    def totale(self, nome):
        return sum(v["q"] for v in self.voci.values() if v["nome"] == nome and v["zona"] in ("main", "side"))

    def contatore(self, e):
        it = self.cv.find_withtag("current")
        if it:
            self.contatore_su(it[0])

    def contatore_su(self, it):
        """Il − o il + del contatore: una copia in meno o in piu'."""
        for t in self.cv.gettags(it):
            if t.startswith("piu") and t[3:].isdigit():
                return self.cambia_copie(int(t[3:]), +1)
            if t.startswith("meno") and t[4:].isdigit():
                return self.cambia_copie(int(t[4:]), -1)

    def cambia_copie(self, vid, d):
        v = self.voci.get(vid)
        if v is None or not self.modifica or v["zona"] == "cmd":
            return False
        if d > 0 and self.totale(v["nome"]) >= self.limite(v["nome"]):
            return False
        v["q"] += d
        if v["q"] <= 0:
            self.togli(vid)
        self.mazzo_cambiato()
        self.disegna()
        self.salva()
        return True

    def togli(self, vid):
        pl = self.pila_di(vid)
        del self.voci[vid]
        for _pl, _tolta, carte in self._riposte:        # una carta nascosta dal filtro: esce anche dalle carte tenute da parte
            carte[:] = [x for x in carte if x[1] != vid]
        if pl is not None:
            pl["carte"].remove(vid)
            if pl.get("aperta") == vid:
                pl["aperta"] = None
            if not pl["carte"]:
                self.pile.remove(pl)

    # ------------------------------------------------ col builder: allinearsi, ricevere le carte dalla Collection, cercare per nome
    def allinea(self, main, side, comandante=None):
        """Il mazzo e' cambiato nel builder: le copie si rimettono uguali, le carte nuove vanno sulla pila del loro costo (o in una pila nuova), quelle tolte escono.
        La disposizione delle altre resta. -> True se e' cambiato qualcosa."""
        voluto = collections.Counter()
        for zona, carte in (("main", main or {}), ("side", side or {}), ("cmd", comandante or {})):
            for n, q in carte.items():
                if q > 0:
                    voluto[(n, zona)] += q
        ora = collections.Counter({(v["nome"], v["zona"]): v["q"] for v in self.voci.values()})
        if ora == voluto:
            return False
        for vid in list(self.voci):
            v = self.voci[vid]
            q = voluto.get((v["nome"], v["zona"]), 0)
            if q <= 0:
                self.togli(vid)
            else:
                v["q"] = q
        nuove = []
        for (n, zona), q in voluto.items():
            if (n, zona) not in ora:
                nuove.append(self.nuova_voce(n, zona, q))
        self.carica_mancanti()
        self.disegna()
        # la carta arrivata dal builder (doppio clic in Collection) va nello spazio isolato a destra di tutto: se e' fuori dalla vista, il foglio la porta in
        # vista (13 nov 2026: prima arrivava fuori dallo schermo e sembrava che il doppio clic non avesse fatto niente)
        if nuove:
            self.mostra_carta(nuove[-1])
        self.salva()
        return True

    def posto_isolato(self):
        """Dove va una carta nuova del mazzo: una colonna vuota a destra di tutto (pile, label, dot), sulla griglia; le carte arrivate dopo, sotto, nella stessa colonna."""
        w, h, _off, _p = misure(1.0)
        arrivi = [pl for pl in self.pile if pl.get("arrivo") and pl["zona"] == "main"]
        altre = [pl for pl in self.pile if pl["zona"] == "main" and not pl.get("arrivo")]
        destra = max([pl["x"] + w for pl in altre] + [lb["x"] + lb["w"] for lb in self.etichette] + [p_["x"] + 30 for p_ in self.punti.values()], default=MARGINE)
        x = a_griglia(destra + PASSO_X, 0)[0]
        sotto = [self.posizioni(pl)[-1] + h for pl in arrivi if pl["x"] == x]
        y = a_griglia(x, max(sotto) + 2 * PASSO_Y)[1] if sotto else 0
        return x, y

    def nuova_voce(self, nome, zona, q=1, pila=None, xy=None):
        """Una carta nuova sul tavolo: sulla pila data, o alla posizione xy (in scala 1, dentro la sua zona), o nel mazzo in uno spazio isolato (posto_isolato),
        o nella fascia in una pila nuova in fondo alla riga."""
        vid = max(self.voci, default=-1) + 1
        self.voci[vid] = dict(nome=nome, zona=zona, q=q)
        if pila is not None:
            pila["carte"].append(vid)
            return vid
        w, _h, _off, _p = misure(1.0)
        if xy is not None:
            x, y = xy
            self.pile.append(dict(zona=zona, x=round(x, 2), y=0 if zona != "main" else round(y, 2), carte=[vid], aperta=None))
            return vid
        if zona == "main":      # in uno spazio isolato, a destra della rete, una sotto l'altra (Autore, 10 nov 2026: «se le inserisco per doppio clic devono
            # apparire in uno spazio isolato»); fino a quel giorno andavano sulla pila del loro costo
            x, y = self.posto_isolato()
            self.pile.append(dict(zona="main", x=x, y=y, carte=[vid], aperta=None, arrivo=True))
            return vid
        stesse = [q for q in self.pile if q["zona"] in ((zona, "cmd") if zona in ("side", "cmd") else (zona,))]
        y = 0 if zona in ("side", "cmd") else min((q["y"] for q in stesse), default=0)
        riga = [q["x"] for q in stesse if q["y"] == y]
        self.pile.append(dict(zona=zona, x=max(riga) + w + SPAZIO if riga else MARGINE, y=y, carte=[vid], aperta=None))
        return vid

    def sopra(self, x_root, y_root):
        """Il punto dello schermo sta sul tavolo? (la Collection lo chiede mentre trascini una carta)"""
        try:
            return self.fin.winfo_exists() and self.fin.winfo_containing(x_root, y_root) is self.cv
        except Exception:
            return False

    def punto(self, x_root, y_root):
        """Dallo schermo alla tela, in pixel della tela."""
        return x_root - self.cv.winfo_rootx() + self.cv.canvasx(0), y_root - self.cv.winfo_rooty() + self.cv.canvasy(0)

    def evidenzia(self, x_root, y_root, on=True):
        """Mentre una carta della Collection passa sul tavolo: il bordo azzurro sulla pila dove cadrebbe."""
        self.cv.delete("bersaglio")
        if not on or not self.sopra(x_root, y_root):
            return
        b = self.bersaglio(*self.punto(x_root, y_root))
        if b is not None:
            x0, y0, x1, y1 = self.ingombro_px(b)
            self.cv.create_rectangle(x0 - 4, y0 - 4, x1 + 4, y1 + 4, outline=C["accento"], width=2, tags="bersaglio")

    def ricevi(self, nome, x_root=None, y_root=None, zona=None):
        """Una copia di una carta dalla Collection (o dalla ricerca): cade dove la lasci. Sulla stessa carta della zona le copie si sommano; sulla pila sotto il mouse ci si
        impila; nella fascia va in sideboard. Oltre il limite no. -> True se e' entrata."""
        if not self.modifica:
            return False
        self.cv.delete("bersaglio")
        b, xy = None, None
        if x_root is not None:
            mx, my = self.punto(x_root, y_root)
            b = self.bersaglio(mx, my)
            zona = b["zona"] if b is not None else ("side" if self.in_fascia(my) else "main")
            s_ = self.sc(zona)
            w, _h, _off, _p = misure(s_)
            xy = ((mx - w / 2 - self.ox(zona)) / s_, (my - 20 - self.oy(zona)) / s_)
        zona = zona or "main"
        if self.totale(nome) >= self.limite(nome):
            self.dici(f"{nome}: max {self.limite(nome)} copies")
            return False
        gemella = next((i for i, v in self.voci.items() if v["nome"] == nome and v["zona"] == zona), None)
        if gemella is not None:
            self.voci[gemella]["q"] += 1
            nuova = gemella
        else:
            nuova = self.nuova_voce(nome, zona, 1, pila=b, xy=xy if b is None and x_root is not None else None)
        self.mazzo_cambiato()
        self.carica_mancanti()
        self.disegna()
        if x_root is None:      # dalla ricerca: la carta in vista (lasciata col mouse e' gia' dove la guardi)
            self.mostra_carta(nuova)
        self.salva()
        return True

    # ------------------------------------------------ le connessioni padre -> figlio: il pallino sotto le carte
    def nodo(self, vid):
        """Il pallino della carta: alla base, al centro, se la carta si vede intera (16 pixel); se e' coperta nella pila, piccolo sul bordo destro della sua barra del
        nome (10 pixel, solo se ha una freccia). Si tira su un'altra carta; le frecce partono e arrivano qui."""
        pt = self.nodo_xy(vid) if not self.sola else None       # il pallino e' uno strumento: in sola lettura no
        if pt:
            x, y, rr = pt
            self.cv.create_image(x - rr, y - rr, image=pallino_nodo(2 * rr), anchor="nw", tags=("nodo", f"n{vid}"))
            v = self.voci[vid]
            pl_ = self.pila_di(vid)
            larga = misure(self.pos_px(pl_)[2])[0] if pl_ is not None else BASE_W      # le carte piccole: solo il pallino, la fila intera usciva dalla carta
            if rr == 8 and self.modifica and v["zona"] != "cmd" and larga >= STRUMENTI_MIN:       # alla base delle carte intere, nei mazzi che si cambiano: il ⇄ accanto al pallino
                self.cv.create_image(x + 22 - 8, y - 8, image=segno_scambia(16), anchor="nw", tags=("scambia", f"s{vid}"))
                if v["nome"] not in self.note:      # e a sinistra il + nota (Autore, 12 nov 2026: «aggiungere note va accanto al pallino giallo di collegamento
                    # sulle carte»; prima era in alto a destra della carta sotto il mouse)
                    self.cv.create_image(x - 22 - 9, y - 9, image=segno_nota(18, False), anchor="nw", tags=("nota", "nota_n", f"nn{vid}"))

    def scambia_apri(self, vid):
        """Il ⇄ sotto la carta: una casella accanto, scrivi il nome, le carte della collezione che combaciano (prima quelle che hai, con le copie), Invio o il clic
        la mettono al posto di questa (Autore, 9 nov 2026: «un pulsante sotto la carta che ci permette di sostituirla con un'altra carta dalla collezione»)."""
        tk, F = self.tk, self.F
        self.scambia_chiudi()
        v = self.voci[vid]
        m = MB.Menu(tk, F, self.fin, "Replace card", chiudi=self.scambia_chiudi)       # lo stile comune dei mini-menu (menu_board, 13 nov 2026)
        p = self._scambio = m.p
        tk.Label(m.corpo, text=f"{v['nome']}  ·  {v['q']}x", bg=MB.FONDO, fg="#ffffff", font=F(9, True), anchor="w").pack(fill="x", padx=12, pady=(6, 0))
        m.sezione("With")
        r_ = m.riga()
        var = tk.StringVar()
        e = m.campo(r_, var, larga=36)
        lista = m.lista(r_)
        m.piede("Type a name · Enter replaces · Esc closes · cards you own first")
        voci = []

        def aggiorna(*_a):
            voci[:] = self.scambia_trova(var.get(), v["nome"])
            lista.delete(0, "end")
            for n, q in voci:
                lista.insert("end", f"{n}   ·   x{q}" if q else f"{n}   ·   not owned")
            if voci:
                lista.selection_set(0)

        def scegli(*_a):
            sel = lista.curselection()
            if voci:
                self.scambia(vid, voci[sel[0] if sel else 0][0])
            self.scambia_chiudi()
            return "break"

        def muovi(dd):
            sel = lista.curselection()
            i = max(0, min(len(voci) - 1, (sel[0] if sel else -1) + dd))
            lista.selection_clear(0, "end"); lista.selection_set(i); lista.see(i)
            return "break"
        var.trace_add("write", aggiorna)
        e.bind("<Return>", scegli); e.bind("<Escape>", lambda ev: self.scambia_chiudi())
        e.bind("<Down>", lambda ev: muovi(1)); e.bind("<Up>", lambda ev: muovi(-1))
        lista.bind("<ButtonRelease-1>", scegli)
        bb = self.cv.bbox(f"s{vid}") or self.cv.bbox(f"c{vid}")
        x = self.cv.winfo_rootx() + int(bb[0] - self.cv.canvasx(0)) if bb else self.fin.winfo_pointerx()
        y = self.cv.winfo_rooty() + int(bb[3] - self.cv.canvasy(0)) + 4 if bb else self.fin.winfo_pointery()
        m.posa(xy=(x, y), fuoco=e)
        return p

    # ------------------------------------------------ le note personali (12 nov 2026)
    # Autore: «aggiungiamo la possibilita' di aggiungere note personali ai gruppi o individualmente alle carte. le note sono espandibili o chiudibili, editabili
    # e cancellabili». Una nota per carta (per nome: vale anche per le copie in sideboard) e una per label. Chiusa e' l'icona del foglietto in alto a destra della
    # carta (sul titolo della label); il clic la apre o la chiude, il clic sul riquadro aperto la modifica. In modalita' edit il foglietto vuoto col + nello stesso
    # angolo ne fa una nuova;
    # nella label, Note... nel menu ≡. Il riquadro ha una misura fissa a ogni zoom, come gli strumenti. Si salvano con la disposizione del Board.
    def nota_box(self, x, y, testo, tags, larga=230):
        """Il riquadro della nota aperta: il testo che va a capo, su un fondo ambra scuro col bordo ambra. -> (x0, y0, x1, y1)."""
        cv = self.cv
        t = cv.create_text(x + 10, y + 8, text=testo, width=larga - 20, anchor="nw", fill="#f3e3c3", font=self.F(8), tags=tags + ("nota",))
        bb = cv.bbox(t) or (x, y, x + larga, y + 30)
        r = cv.create_rectangle(x, y, x + larga, bb[3] + 8, fill="#2a2214", outline="#f0ad4e", width=1, tags=tags + ("nota",))
        cv.tag_lower(r, t)
        return x, y, x + larga, bb[3] + 8

    def disegna_note(self):
        """Le note delle carte: l'icona sulla carta intera che ha una nota, il riquadro se e' aperta; il ✎ per farne una nuova (modalita' edit)."""
        cv = self.cv
        for pl in self.pile:
            if pl["zona"] != "main" and self.nascosta():
                continue
            for vid in pl["carte"]:
                if not (vid == pl["carte"][-1] or vid == pl.get("aperta")):
                    continue
                r = self.rett(vid)
                if r is None:
                    continue
                nome = self.voci[vid]["nome"]
                n = self.note.get(nome)
                if n:
                    cv.create_image(r[2] - 26, r[1] + 6, image=segno_nota(20, True), anchor="nw", tags=("nota", "nota_i", f"ni{vid}"))
                    if n.get("aperta"):
                        self.nota_box(r[2] + 8, r[1], n["testo"], ("nota_b", f"nb{vid}"))
        self._nota_su = None
        self.nota_hover(getattr(self, "_nota_hover", None))
        cv.tag_raise("nota")
        cv.tag_raise("nota_b")
        cv.tag_raise("label_nb")

    def nota_hover(self, vid):
        """Dal 12 nov 2026 il + nota sta fisso alla base della carta, accanto al pallino (nodo): qui resta solo chi e' sotto il mouse."""
        self._nota_hover = vid

    def nota_di(self, tipo, chiave):
        if tipo == "c":
            return (self.note.get(chiave) or {}).get("testo", "")
        lb = self.etichette[chiave] if isinstance(chiave, int) and 0 <= chiave < len(self.etichette) else {}
        return lb.get("nota", "")

    def metti_nota(self, tipo, chiave, testo):
        """Scrive (o, col testo vuoto, cancella) la nota di una carta (tipo «c», per nome) o di una label (tipo «l», per indice). Una nota scritta si apre."""
        testo = (testo or "").strip()
        if tipo == "c":
            if testo:
                self.note[chiave] = dict(testo=testo, aperta=True)
            else:
                self.note.pop(chiave, None)
        elif isinstance(chiave, int) and 0 <= chiave < len(self.etichette):
            lb = self.etichette[chiave]
            if testo:
                lb["nota"], lb["nota_aperta"] = testo, True
            else:
                lb.pop("nota", None); lb.pop("nota_aperta", None)
        self.disegna()
        self.salva()
        self.dici("Note saved" if testo else "Note deleted")

    def apri_nota(self, tipo, chiave):
        """Apre o chiude la nota (si vede in tutte e due le modalita')."""
        if tipo == "c" and chiave in self.note:
            self.note[chiave]["aperta"] = not self.note[chiave].get("aperta")
        elif tipo == "l" and isinstance(chiave, int) and 0 <= chiave < len(self.etichette) and self.etichette[chiave].get("nota"):
            lb = self.etichette[chiave]
            lb["nota_aperta"] = not lb.get("nota_aperta")
        else:
            return
        self.disegna()
        self.salva()

    def editor_nota(self, tipo, chiave):
        """La finestrella per scrivere la nota: il testo su piu' righe, Save (Ctrl+Invio), Delete se c'e', Esc chiude. Solo in modalita' edit."""
        if not self.modifica:
            return None
        tk, F = self.tk, self.F
        self.nota_chiudi()
        titolo = chiave if tipo == "c" else (self.etichette[chiave]["nome"] if 0 <= chiave < len(self.etichette) else "Label")
        m = MB.Menu(tk, F, self.fin, f"Note · {titolo}", chiudi=self.nota_chiudi, colore="#f0ad4e")      # lo stile comune dei mini-menu, col filo ambra delle note
        p = self._nota_pop = m.p
        testo = m.campo(m.riga(pady=(8, 2)), None, larga=40, righe=6)
        testo.insert("1.0", self.nota_di(tipo, chiave))

        def salva(*_a):
            self.metti_nota(tipo, chiave, testo.get("1.0", "end"))
            self.nota_chiudi()
            return "break"
        voci_ = [("Save", salva, "salva")]
        if self.nota_di(tipo, chiave):
            voci_.append(("Delete", lambda: (self.metti_nota(tipo, chiave, ""), self.nota_chiudi()), "pericolo"))
        m.pulsanti(voci_ + [("Cancel", self.nota_chiudi, "secondario")])
        m.piede("Ctrl+Enter saves · Esc closes")
        testo.bind("<Control-Return>", salva)
        testo.bind("<Escape>", lambda ev: self.nota_chiudi())
        m.posa(fuoco=testo)
        self.pronta_nota = salva        # le prove salvano da qui
        self.testo_nota = testo
        return p

    def nota_chiudi(self):
        p = getattr(self, "_nota_pop", None)
        if p is not None:
            try:
                p.destroy()
            except Exception:
                pass
        self._nota_pop = None

    def cerca_copia(self, k, vecchia):
        """La casella col nome per cambiare (vecchia) o aggiungere (None) una carta della copia k: le carte che combaciano, prima quelle che hai."""
        tk, F = self.tk, self.F
        self.scambia_chiudi()
        m = MB.Menu(tk, F, self.fin, "Replace card" if vecchia else "Add a card", chiudi=self.scambia_chiudi)      # lo stile comune dei mini-menu
        p = self._scambio = m.p
        if vecchia:
            tk.Label(m.corpo, text=vecchia, bg=MB.FONDO, fg="#ffffff", font=F(9, True), anchor="w").pack(fill="x", padx=12, pady=(6, 0))
        m.sezione("With" if vecchia else "Card")
        r_ = m.riga()
        var = tk.StringVar()
        e = m.campo(r_, var, larga=36)
        lista = m.lista(r_)
        m.piede("Type a name · Enter or double-click picks · Esc closes · cards you own first")
        voci = []

        def aggiorna(*_a):
            voci[:] = self.scambia_trova(var.get(), vecchia or "")
            lista.delete(0, "end")
            for n, q in voci:
                lista.insert("end", f"{n}   ·   x{q}" if q else f"{n}   ·   not owned")
            if voci:
                lista.selection_set(0)

        def scegli(*_a):
            sel = lista.curselection()
            if voci:
                self.cambia_copia(k, vecchia, voci[sel[0] if sel else 0][0])
            self.scambia_chiudi()
        var.trace_add("write", aggiorna)
        e.bind("<Return>", scegli); lista.bind("<Double-Button-1>", scegli)
        e.bind("<Escape>", lambda ev: self.scambia_chiudi())
        m.posa(fuoco=e)
        p.scelta = dict(var=var, scegli=scegli)         # per le prove
        return p

    def scambia_chiudi(self):
        p = getattr(self, "_scambio", None)
        if p is not None:
            try:
                p.destroy()
            except Exception:
                pass
        self._scambio = None

    def scambia_trova(self, testo, escludi=None, quante=40):
        """Le carte per il ⇄: quelle del formato (se il tavolo le ha, il builder) o della collezione, che contengono il testo; prima quelle che hai, poi quelle che
        cominciano col testo. -> [(nome, copie che hai)]."""
        t = testo.strip().lower()
        if len(t) < 2:
            return []
        try:
            import dati_app
            mie = dati_app.collezione()[0] or {}
        except Exception:
            mie = {}
        nomi = self.nomi_ricerca() if callable(self.nomi_ricerca) else (self.nomi_ricerca or list(mie))
        trovate = [n for n in nomi if t in n.lower() and n != escludi]
        trovate.sort(key=lambda n: (not mie.get(n), not n.lower().startswith(t), len(n), n))
        return [(n, mie.get(n, 0)) for n in trovate[:quante]]

    def scambia(self, vid, nuovo):
        """La carta nuova prende il posto della vecchia: stessa pila, stessa zona, le stesse copie fino al limite del formato. Se nella zona c'e' gia', le copie si
        sommano su quella. Le connessioni della vecchia passano alla nuova (Autore, 9 nov 2026: «quando cambio una carta se ha delle connessioni deve
        mantenerle»); se la vecchia resta nel mazzo in un'altra zona, tiene anche le sue."""
        v = self.voci.get(vid)
        if v is None or not nuovo or nuovo == v["nome"] or not self.modifica or v["zona"] == "cmd":
            return False
        vecchio = v["nome"]
        posto = max(0, self.limite(nuovo) - self.totale(nuovo))
        q = min(v["q"], posto)
        if q <= 0:
            self.dici(f"{nuovo}: already at the limit")
            return False
        gemella = next((i for i, x in self.voci.items() if i != vid and x["nome"] == nuovo and x["zona"] == v["zona"]), None)
        if gemella is not None:
            self.voci[gemella]["q"] += q
            self.togli(vid)
        else:
            v["nome"], v["q"] = nuovo, q
        resta = any(x["nome"] == vecchio for x in self.voci.values())
        passate = self.rete.rinomina(vecchio, nuovo, self.carte_db, tieni=resta)
        if not resta:
            self.vie = {((nuovo if a == vecchio else a), (nuovo if b == vecchio else b)): q for (a, b), q in self.vie.items()}
            for p_ in self.punti.values():
                p_["ingressi"] = [["c", nuovo] if (k == "c" and v == vecchio) else [k, v] for k, v in p_.get("ingressi", [])]
        self.dici(f"{vecchio} → {nuovo}: replaced ({q}x)" + (f", {passate} link{'s' if passate != 1 else ''} kept" if passate else ""))
        self.mazzo_cambiato()
        self.carica_mancanti()
        self.disegna()
        self.salva()
        return True

    def nodo_xy(self, vid, dx=0.0, dy=0.0):
        """(x, y, raggio) del pallino della carta, spostato di dx, dy (la carta che si trascina). None se la carta non si vede."""
        pl = self.pila_di(vid)
        if pl is None or (pl["zona"] != "main" and self.nascosta()):
            return None
        x, _y, s_ = self.pos_px(pl)
        w, h, off, _p = misure(s_)
        k = pl["carte"].index(vid)
        y = self.ys_px(pl)[k]
        if vid == pl["carte"][-1] or vid == pl.get("aperta"):
            return x + w / 2 + dx, y + h + 9 + dy, 8
        return x + w + dx, y + off * 0.5 + dy, 5

    def vid_nome(self, nome):
        """La carta col nome che si vede: prima nel mazzo, poi nella fascia."""
        cand = [i for i, v in self.voci.items() if v["nome"] == nome]
        cand.sort(key=lambda i: self.voci[i]["zona"] != "main")
        return next((i for i in cand if self.rett(i) is not None), None)

    @staticmethod
    def segmento(a, b):
        """La freccia fra due pallini (x, y, raggio): dritta, dal bordo del pallino del padre al bordo di quello del figlio, staccata di 2 pixel. None se si toccano."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        lung = (dx * dx + dy * dy) ** 0.5
        if lung < a[2] + b[2] + 10:
            return None
        ux, uy = dx / lung, dy / lung
        return (a[0] + ux * (a[2] + 2), a[1] + uy * (a[2] + 2)), (b[0] - ux * (b[2] + 2), b[1] - uy * (b[2] + 2))

    def legami_visti(self):
        """[(padre, figlio, vid padre, vid figlio)] delle connessioni fra carte che si vedono."""
        out = []
        for p_, c_, _fam in self.rete.legami({v["nome"] for v in self.voci.values()}):
            va, vb = self.vid_nome(p_), self.vid_nome(c_)
            if va is not None and vb is not None:
                out.append((p_, c_, va, vb))
        return out

    def punto_xy(self, pid, dx=0.0, dy=0.0):
        p_ = self.punti[pid]
        return p_["x"] * self.zoom + dx, self.oy("main") + p_["y"] * self.zoom + dy, R_PUNTO

    def uscita_xy(self, pid):
        """Il pallino d'oro del dot: a destra, staccato."""
        x, y, r = self.punto_xy(pid)
        return x + r + 9, y

    def fine_xy(self, fine, mobili=None, dx=0.0, dy=0.0):
        """Dove sta un capo di un pezzo di linea: ("c", vid) il pallino della carta, ("p", id) il dot; spostato di dx, dy se e' fra quelli che si trascinano."""
        k, v = fine
        sp = (dx, dy) if mobili is not None and fine in mobili else (0.0, 0.0)
        if k == "c":
            return self.nodo_xy(v, *sp) if v in self.voci else None
        return self.punto_xy(v, *sp) if v in self.punti else None

    def pezzi(self):
        """I pezzi di linea da disegnare: dict(a, b, freccia, link=(vid padre, vid figlio) o None, links, punto, ingresso, stile). Una connessione senza dot e' un
        pezzo solo, con la punta. Un dot ha un pezzo per ogni ingresso (una carta o un altro dot: un dot riceve piu' frecce, Autore 10 nov 2026) e un pezzo con
        la punta per ogni figlio, uno solo anche se ci passano le connessioni di piu' padri (links)."""
        out, gruppi = [], {}
        for p_, c_, va, vb in self.legami_visti():
            q = self.vie.get((p_, c_))
            if q in self.punti and p_ in self.fonti(q):
                gruppi.setdefault((q, vb), []).append((va, vb))
            else:
                out.append(dict(a=("c", va), b=("c", vb), freccia=True, link=(va, vb), links=[(va, vb)], punto=None, stile=(va, vb)))
        for (q, vb), links in gruppi.items():
            out.append(dict(a=("p", q), b=("c", vb), freccia=True, link=links[0], links=links, punto=None, stile=links[0]))
        for q in self.punti:
            sotto = set(self.sotto_punto(q))
            for k, v in self.ingressi(q):
                if k == "c":
                    va = self.vid_nome(v)
                    if va is None:
                        continue
                    stile = next((l_ for (q2, _vb), links in gruppi.items() if q2 in sotto for l_ in links if l_[0] == va), None)
                    out.append(dict(a=("c", va), b=("p", q), freccia=False, link=None, punto=q, ingresso=("c", v), stile=stile))
                elif v in self.punti:
                    out.append(dict(a=("p", v), b=("p", q), freccia=False, link=None, punto=q, ingresso=("p", v), stile=None))
        return out

    def stile_pezzo(self, pz):
        if pz.get("stile"):
            return self.stile_px(*pz["stile"])
        w = RS.SPESSORI[1]
        return RS.PERLA, w, (round(7 + 2.2 * w), round(8 + 2.2 * w), round(2.6 + 0.9 * w))

    def disegna_rete(self):
        """Le linee padre -> figlio, dritte da pallino a pallino o spezzate dai dot, SOTTO le carte (Autore, 9 nov 2026: «le linee passano dietro le carte e mai
        sopra») e sopra le label. Sulla scheda una linea per pezzo; in Tk un'immagine sola in antialias (2x ridotta; 1x se sarebbe troppo grande). Non prendono i
        clic: la carta si cerca nella geometria delle pile, la linea solo nel vuoto. Mentre trascini l'immagine si nasconde e i pezzi diventano linee della tela
        (frecce_vive). Un'immagine per freccia costava di piu' (misurato su UW Bouncer, 10 ms a movimento invece di 4)."""
        from PIL import Image, ImageDraw, ImageTk
        cv = self.cv
        cv.delete("rete"); cv.delete("rete_hover"); cv.delete("punto")
        self._img_rete, self._segmenti, self._tronchi, self._arco, self._arco_t, self._barra_box = None, [], [], None, None, None
        self._pezzi = self.pezzi()
        for pz in self._pezzi:
            a, b = self.fine_xy(pz["a"]), self.fine_xy(pz["b"])
            pz["sg"] = self.segmento(a, b) if a and b else None
            if pz["sg"] is None:
                continue
            if pz["link"]:
                self._segmenti.append((pz["link"][0], pz["link"][1], pz["sg"][0], pz["sg"][1]))
            else:
                self._tronchi.append((pz["punto"], pz["sg"][0], pz["sg"][1], pz["ingresso"]))
        visti = [pz for pz in self._pezzi if pz["sg"]]
        if visti and self.gpu:      # sulla scheda video: linee con la punta, l'antialias lo fa la scheda (MSAA); niente immagine da rifare
            for pz in visti:
                col, w, ash = self.stile_pezzo(pz)
                a, b = pz["sg"]
                cv.create_line(a[0], a[1], b[0], b[1], fill=col, width=w, arrow="last" if pz["freccia"] else "none", arrowshape=ash, capstyle="round", tags="rete")
        elif visti:
            xs = [x for pz in visti for x in (pz["sg"][0][0], pz["sg"][1][0])]
            ys = [y for pz in visti for y in (pz["sg"][0][1], pz["sg"][1][1])]
            x0, y0 = int(min(xs)) - 14, int(min(ys)) - 14
            x1, y1 = int(max(xs)) + 14, int(max(ys)) + 14
            K = 2 if (x1 - x0) * (y1 - y0) * 4 <= 16_000_000 else 1
            im = Image.new("RGBA", ((x1 - x0) * K, (y1 - y0) * K), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            for pz in visti:
                col, w, ash = self.stile_pezzo(pz)
                rgb = tuple(int(col.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                a, b = pz["sg"]
                A, B = ((a[0] - x0) * K, (a[1] - y0) * K), ((b[0] - x0) * K, (b[1] - y0) * K)
                if not pz["freccia"]:
                    d.line([A, B], fill=rgb + (235,), width=max(1, round(w * K)))
                    continue
                ang = math.atan2(B[1] - A[1], B[0] - A[0])
                L, AP = ash[1] * K, 0.42
                base = (B[0] - L * 0.8 * math.cos(ang), B[1] - L * 0.8 * math.sin(ang))       # la linea finisce dentro la punta, non la buca
                d.line([A, base], fill=rgb + (235,), width=max(1, round(w * K)))
                d.polygon([B, (B[0] - L * math.cos(ang - AP), B[1] - L * math.sin(ang - AP)), (B[0] - L * math.cos(ang + AP), B[1] - L * math.sin(ang + AP))],
                          fill=rgb + (255,))
            if K > 1:
                im = im.resize((x1 - x0, y1 - y0), Image.LANCZOS)
            self._img_rete = ImageTk.PhotoImage(im)
            cv.create_image(x0, y0, image=self._img_rete, anchor="nw", tags="rete")
        for pid in self.punti:      # i dot, sopra le linee e sotto le carte; accanto il pallino d'oro da cui parte una linea nuova (come quello delle carte)
            pt = self.punto_xy(pid)
            cv.create_image(pt[0] - R_PUNTO, pt[1] - R_PUNTO, image=pallino_punto(2 * R_PUNTO), anchor="nw", tags=("punto", f"p{pid}"))
            if not self.sola:
                ox, oy_ = self.uscita_xy(pid)
                cv.create_image(ox - 5, oy_ - 5, image=pallino_nodo(10), anchor="nw", tags=("punto", f"p{pid}", "punto_out", f"po{pid}"))
        if cv.find_withtag("carta"):
            cv.tag_lower("rete", "carta")
        # i dot sopra le carte, come i pallini (10 nov 2026): sono nodi da toccare, e il centro di una linea fra le basi di padre e figlio cade spesso dentro la
        # carta del figlio; sotto le carte un dot messo col chiodo spariva e non si prendeva piu'. Le linee restano dietro le carte.
        cv.tag_raise("punto")
        cv.tag_raise("nodo")
        cv.tag_raise("scambia")

    def stile_px(self, va, vb):
        """(colore, spessore, punta) della freccia: il colore e l'importanza scelti da Autore, di partenza grigio perlato e sottile (9 nov 2026)."""
        col, w = self.rete.colore_spessore(self.voci[va]["nome"], self.voci[vb]["nome"])
        return col, w, (round(7 + 2.2 * w), round(8 + 2.2 * w), round(2.6 + 0.9 * w))

    @staticmethod
    def distanza(pt, a, b):
        """Distanza del punto dal segmento a-b."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        l2 = dx * dx + dy * dy or 1.0
        t = max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / l2))
        qx, qy = a[0] + t * dx, a[1] + t * dy
        return ((pt[0] - qx) ** 2 + (pt[1] - qy) ** 2) ** 0.5

    def arco_a(self, x, y, raggio=7):
        """La freccia piu' vicina al punto, entro raggio pixel: (padre vid, figlio vid, a, b) o None."""
        meglio, dmin = None, raggio
        for sg in getattr(self, "_segmenti", []):
            dd = self.distanza((x, y), sg[2], sg[3])
            if dd <= dmin:
                meglio, dmin = sg, dd
        return meglio

    def barretta(self, a, b, icone):
        """I pulsantini di una linea accesa in una barretta accanto al suo centro, staccata dalla linea, uguale per ogni lunghezza (Autore, 10 nov 2026: «in linee
        troppo corte non appaiono tutti i pulsantini come quello dei colori»; prima stavano lungo la linea a 24 pixel dal centro e su una linea corta finivano sopra i
        pallini o fuori). icone: [(immagine, tag)]. Il chiodo mette il dot a meta' della linea. -> il riquadro della barretta."""
        (ax, ay), (bx, by) = a, b
        mx, my = (ax + bx) / 2, (ay + by) / 2
        lung = max(1.0, ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5)
        nx, ny = -(by - ay) / lung, (bx - ax) / lung        # la perpendicolare verso l'alto; per una linea verticale, a destra
        if ny > 0 or (ny == 0 and nx < 0):
            nx, ny = -nx, -ny
        L, H = len(icone) * 24 + 6, 28
        meta = abs(nx) * L / 2 + abs(ny) * H / 2
        cx, cy = mx + nx * (12 + meta), my + ny * (12 + meta)
        x0, y0 = cx - L / 2, cy - H / 2
        self.cv.create_image(x0, y0, image=pillola(round(L), H, (16, 16, 20, 235), C["filo"]), anchor="nw", tags=("rete_hover", "rete_barra"))
        for k, (img, tag) in enumerate(icone):
            self.cv.create_image(x0 + 5 + k * 24, y0 + 4, image=img, anchor="nw", tags=("rete_hover", tag))
        self._chiodo = (mx, my)
        self._barra_box = (min(x0, mx) - 10, min(y0, my) - 10, max(x0 + L, mx) + 10, max(y0 + H, my) + 10)       # la zona dove la linea resta accesa
        self.cv.tag_raise("rete_barra")
        for _img, tag in icone:
            self.cv.tag_raise(tag)
        return x0, y0, x0 + L, y0 + H

    def accendi_arco(self, sg):
        """La freccia sotto il puntatore: piu' chiara, e accanto al suo centro la barretta: il chiodo (un dot), la ✕ (la toglie), i colori."""
        if sg is not None and self._arco is not None and sg[:2] == self._arco[:2]:
            return
        self.cv.delete("rete_hover")
        self._arco, self._arco_t, self._barra_box = sg, None, None
        if sg is None:
            return
        (ax, ay), (bx, by) = sg[2], sg[3]
        col, w, ash = self.stile_px(sg[0], sg[1])
        self.cv.create_line(ax, ay, bx, by, fill=chiaro(col), width=w + 1.6, arrow="last", arrowshape=(ash[0] + 1, ash[1] + 2, ash[2] + 1), capstyle="round",
                            tags=("rete_hover", "rete_hl"))
        if self.cv.find_withtag("carta"):
            self.cv.tag_lower("rete_hl", "carta")
        self._chiodo_su = ("link", sg)
        self.barretta(sg[2], sg[3], [(segno_chiodo(20), "rete_c"), (segno_x(20), "rete_x"), (segno_stile(20), "rete_s")])

    def tronco_a(self, x, y, raggio=7):
        """Il pezzo d'ingresso di un dot piu' vicino al punto: (dot, a, b, ingresso), o None."""
        meglio, dmin = None, raggio
        for tr in self._tronchi:
            dd = self.distanza((x, y), tr[1], tr[2])
            if dd <= dmin:
                meglio, dmin = tr, dd
        return meglio

    def accendi_tronco(self, tr):
        """L'ingresso di un dot sotto il puntatore: piu' chiaro, e accanto al suo centro la barretta: il chiodo e la ✕ che toglie quell'ingresso."""
        if self._arco_t is not None and tr[0] == self._arco_t[0] and tr[3] == self._arco_t[3]:
            return
        cv = self.cv
        cv.delete("rete_hover")
        self._arco, self._arco_t = None, tr
        (ax, ay), (bx, by) = tr[1], tr[2]
        cv.create_line(ax, ay, bx, by, fill=chiaro(RS.PERLA), width=RS.SPESSORI[1] + 1.6, capstyle="round", tags=("rete_hover", "rete_hl"))
        if cv.find_withtag("carta"):
            cv.tag_lower("rete_hl", "carta")
        self._chiodo_su = ("tronco", tr)
        self.barretta(tr[1], tr[2], [(segno_chiodo(20), "rete_c"), (segno_x(20), "rete_xt")])

    def togli_arco(self, sg):
        """Toglie la connessione della freccia: la riga d'aiuto lo dice."""
        pa, pb = self.voci[sg[0]]["nome"], self.voci[sg[1]]["nome"]
        for a, b in self.fratelli(pa, pb):      # da un dot: tutte le connessioni che passano da quel pezzo
            if (a, b) in self.rete.figli:
                self.rete.lega(a, b, self.carte_db)       # gia' c'e': lega la toglie
            self.via_tolta(a, b)
        self.dici(f"{pa} → {pb}: unlinked")
        self._arco = None
        self.disegna()
        self.salva()

    def destro(self, e):
        """Il tasto destro: su un dot lo toglie (la linea torna dritta), su una freccia nel vuoto la toglie. In sola lettura niente."""
        if self.sola:
            return
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        sopra = self.pezzo_a(cx, cy)
        if sopra[0] == "punto":
            return self.togli_punto(sopra[1])
        if sopra[0] not in (None, "rete_x", "rete_s", "rete_c", "rete_xt"):
            return
        sg = self.arco_a(cx, cy)
        if sg is not None:
            return self.togli_arco(sg)
        tr = self.tronco_a(cx, cy)
        if tr is not None:
            self.togli_ingresso(tr[0], tr[3])

    def dici(self, testo):
        """Una riga in testa alla finestrella dei comandi per 4 secondi, poi torna il titolo."""
        self.aiuto.configure(text=testo, fg=FG_DICI)
        self.aiuto.after(4000, lambda: self.aiuto.winfo_exists() and self.aiuto.configure(text=self.aiuto_base, fg=FG_AIUTO))

    def frecce_vive(self, d):
        """All'inizio di un trascinamento: i pezzi di linea delle carte e dei dot presi passano a linee della tela, che seguono il mouse; le altre restano ferme.
        Tutte le linee ferme di prima si nascondono: nessuna traccia vecchia (fino al 9 nov 2026 sulla scheda se ne nascondeva una sola)."""
        d["mobili"] = {("c", c) for c in d["prese"]} | {("p", q) for q in d.get("punti") or ()}
        d["vive"] = []
        if not any(pz["a"] in d["mobili"] or pz["b"] in d["mobili"] for pz in self._pezzi):
            return
        cv = self.cv
        cv.delete("rete_hover")
        cv.itemconfigure("rete", state="hidden")
        for pz in self._pezzi:
            col, w, ash = self.stile_pezzo(pz)
            punta = "last" if pz["freccia"] else "none"
            if pz["a"] in d["mobili"] or pz["b"] in d["mobili"]:
                it = cv.create_line(0, 0, 1, 1, fill=col, width=w, arrow=punta, arrowshape=ash, capstyle="round", tags="rete_viva")
                d["vive"].append((it, pz))
            elif pz.get("sg"):
                a, b = pz["sg"]
                cv.create_line(a[0], a[1], b[0], b[1], fill=col, width=w, arrow=punta, arrowshape=ash, capstyle="round", tags="rete_viva")
        if cv.find_withtag("carta"):
            cv.tag_lower("rete_viva", "carta")
        for c in d["prese"]:         # la carta presa resta sopra tutto
            cv.tag_raise(f"c{c}")
        cv.tag_raise("nodo")
        cv.tag_raise("scambia")

    def muovi_frecce(self, d):
        """A ogni movimento: i pezzi di linea delle carte e dei dot presi, dai loro capi spostati di quanto si e' mosso il mouse."""
        dx, dy = d["x"] - d["x0"], d["y"] - d["y0"]
        mobili = d.get("mobili") or set()
        for it, pz in d.get("vive", []):
            a, b = self.fine_xy(pz["a"], mobili, dx, dy), self.fine_xy(pz["b"], mobili, dx, dy)
            sg = self.segmento(a, b) if a and b else None
            if sg:
                self.cv.coords(it, sg[0][0], sg[0][1], sg[1][0], sg[1][1])
                self.cv.itemconfigure(it, state="normal")
            else:
                self.cv.itemconfigure(it, state="hidden")

    def nodo_inizio(self, e, vid=None):
        """Premuto il pallino: comincia una freccia da questa carta (il padre). I figli che lo strumento ha imparato per questa carta, se sono nel mazzo,
        si accendono mentre tiri (un suggerimento, non una connessione)."""
        self.nascondi()
        if vid is None:
            vid = next((int(t[1:]) for t in self.cv.gettags("current") if t[0] == "n" and t[1:].isdigit()), None)
        if vid is None or vid not in self.voci:
            return
        bb = self.cv.bbox(f"n{vid}")
        da = self.voci[vid]["nome"]
        nomi = {v["nome"] for v in self.voci.values()}
        imparati = [c for c in RS.figli_imparati(da, self.rete.f_imp) if c in nomi and c != da and (da, c) not in self.rete.figli]
        self.drag = None
        self.tira = dict(da=da, x=(bb[0] + bb[2]) / 2, y=(bb[1] + bb[3]) / 2, mosso=False, imparati=imparati)

    def tira_muovi(self, e):
        t = self.tira
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        if not t["mosso"] and abs(x - t["x"]) + abs(y - t["y"]) < 6:
            return
        t["mosso"] = True
        cv = self.cv
        cv.delete("tirando")
        for n in t["imparati"]:
            vid = self.vid_nome(n)
            rr = self.rett(vid) if vid is not None else None
            if rr:
                cv.create_rectangle(rr[0] - 4, rr[1] - 4, rr[2] + 4, rr[3] + 4, outline="#d6ac2e", width=1, dash=(3, 4), tags="tirando")
        cv.create_line(t["x"], t["y"], x, y, fill="#d6ac2e", width=2, dash=(6, 4), arrow="last", tags="tirando")
        q = self.punto_a(x, y)
        if q is not None and self.ingresso_possibile(q, t):         # il dot che riceve si accende
            px_, py_, r_ = self.punto_xy(q)
            cv.create_rectangle(px_ - r_ - 4, py_ - r_ - 4, px_ + r_ + 4, py_ + r_ + 4, outline="#d6ac2e", width=2, tags="tirando")
            return
        vid = self.carta_a(x, y)
        if vid is not None and self.voci[vid]["nome"] != t["da"]:        # il figlio si accende mentre ci passi
            rr = self.rett(vid)
            if rr:
                cv.create_rectangle(rr[0] - 3, rr[1] - 3, rr[2] + 3, rr[3] + 3, outline="#d6ac2e", width=2, tags="tirando")

    def tira_fine(self, e):
        """Lasciato su un'altra carta: padre -> figlio, o la connessione tolta se c'era gia'. La riga d'aiuto dice cosa e' successo."""
        t, self.tira = self.tira, None
        self.cv.delete("tirando")
        if not t["mosso"]:
            return
        q = self.punto_a(self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        if q is not None:       # lasciata su un dot: il dot la riceve, e' il suo ingresso
            return self.ricevi_punto(q, t)
        if t.get("punto") is not None:
            return self.tira_fine_punto(t, self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        vb = self.carta_a(self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        b = self.voci[vb]["nome"] if vb is not None else None
        esito = self.rete.lega(t["da"], b, self.carte_db)
        if esito is None:
            return
        fam = self.rete.figli.get((t["da"], b)) or []
        testo = f"{t['da']} → {b}: " + ("linked" + (f" ({RS.etichetta(fam)})" if fam else "") if esito == "nuova" else "unlinked")
        self.aiuto.configure(text=testo, fg=FG_DICI)
        self.aiuto.after(4000, lambda: self.aiuto.winfo_exists() and self.aiuto.configure(text=self.aiuto_base, fg=FG_AIUTO))
        self.disegna()
        # la connessione e' un gesto come gli altri: nello storico (Undo) e da salvare (13 nov 2026, lo stress: in modalita' edit la connessione col pallino non
        # entrava nello storico, Save restava spento e chiudendo il Board senza domanda la connessione si perdeva)
        self.salva()

    def ricerca(self, padre):
        """La ricerca veloce per nome: scrivi, le carte del formato che combaciano (prima quelle che cominciano cosi'), frecce e Invio; Maiuscolo+Invio in sideboard."""
        tk, F = self.tk, self.F
        box = tk.Frame(padre, bg=C["filo"], padx=1, pady=1); box.pack(side="left", padx=(18, 0))
        self.v_cerca = tk.StringVar()
        e = self.e_cerca = tk.Entry(box, textvariable=self.v_cerca, width=30, bg=C["scheda"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(10))
        e.pack(ipady=4, padx=6)
        segnaposto = "Add card…"

        def vuoto(on):
            if on and not self.v_cerca.get():
                e.configure(fg=C["muto"]); self.v_cerca.set(segnaposto)
            elif not on and self.v_cerca.get() == segnaposto:
                self.v_cerca.set(""); e.configure(fg=C["titolo"])
        vuoto(True)
        e.bind("<FocusIn>", lambda ev: vuoto(False))
        e.bind("<FocusOut>", lambda ev: (vuoto(True), self.fin.after(150, self.chiudi_scelte)))
        self.scelte = dict(pop=None, lista=None, voci=[])
        self.v_cerca.trace_add("write", lambda *a: self.cerca_nomi())
        e.bind("<Down>", lambda ev: self.muovi_scelta(1)); e.bind("<Up>", lambda ev: self.muovi_scelta(-1))
        e.bind("<Return>", lambda ev: self.scegli(zona="main")); e.bind("<Shift-Return>", lambda ev: self.scegli(zona="side"))
        e.bind("<Escape>", lambda ev: (self.chiudi_scelte(), self.v_cerca.set(""), "break")[2])

    def trova(self, testo, quante=10):
        t = testo.strip().lower()
        if len(t) < 2:
            return []
        nomi = self.nomi_ricerca() if callable(self.nomi_ricerca) else (self.nomi_ricerca or [])
        inizio = [n for n in nomi if n.lower().startswith(t)]
        dentro = [n for n in nomi if t in n.lower() and not n.lower().startswith(t)]
        return (sorted(inizio, key=len) + sorted(dentro, key=len))[:quante]

    def cerca_nomi(self):
        testo = self.v_cerca.get()
        if testo == "Add card…" or self.fin.focus_get() is not self.e_cerca:
            return
        voci = self.trova(testo)
        self.scelte["voci"] = voci
        if not voci:
            self.chiudi_scelte()
            return
        tk = self.tk
        if self.scelte["pop"] is None or not self.scelte["pop"].winfo_exists():
            p = self.scelte["pop"] = tk.Toplevel(self.fin); p.overrideredirect(True); p.configure(bg=C["filo"])
            l = self.scelte["lista"] = tk.Listbox(p, bg=C["cap"], fg=C["testo"], selectbackground=C["accento"], selectforeground="#ffffff", relief="flat", bd=0,
                                                  highlightthickness=0, font=self.F(10), activestyle="none", height=10, width=34)
            l.pack(padx=1, pady=1)
            l.bind("<ButtonRelease-1>", lambda ev: self.scegli(zona="main"))
        l = self.scelte["lista"]
        l.delete(0, "end")
        for n in voci:
            l.insert("end", n)
        l.configure(height=len(voci))
        l.selection_clear(0, "end"); l.selection_set(0)
        e = self.e_cerca
        self.scelte["pop"].geometry(f"+{e.winfo_rootx() - 7}+{e.winfo_rooty() + e.winfo_height() + 6}")

    def muovi_scelta(self, d):
        l = self.scelte.get("lista")
        if not self.scelte["voci"] or l is None or not l.winfo_exists():
            return "break"
        sel = l.curselection()
        i = max(0, min(len(self.scelte["voci"]) - 1, (sel[0] if sel else -1) + d))
        l.selection_clear(0, "end"); l.selection_set(i); l.see(i)
        return "break"

    def scegli(self, zona="main"):
        voci = self.scelte["voci"]
        if not voci:
            return "break"
        l = self.scelte.get("lista")
        sel = l.curselection() if l is not None and l.winfo_exists() else ()
        nome = voci[sel[0] if sel else 0]
        self.ricevi(nome, zona=zona)
        self.v_cerca.set("")
        self.chiudi_scelte()
        self.e_cerca.focus_set()
        return "break"

    def chiudi_scelte(self):
        p = self.scelte.get("pop") if hasattr(self, "scelte") else None
        if p is not None:
            try:
                p.destroy()
            except Exception:
                pass
            self.scelte["pop"] = None

    # ------------------------------------------------ le immagini che mancano
    def carica_mancanti(self):
        da_fare = [n for n in {v["nome"] for v in self.voci.values()} if not os.path.exists(CAP.file_mini(n)) and not os.path.exists(CAP.file_immagine(n)) and n not in self.attese]
        if not da_fare:
            return
        self.attese.update(da_fare)

        def lavora():
            for n in da_fare:
                try:
                    if not self.fin.winfo_exists():
                        return
                except Exception:
                    return
                CAP.scarica_immagine(n)
                self.pronte.append(n)
        threading.Thread(target=lavora, daemon=True).start()
        self.fin.after(200, self.raccogli)

    def raccogli(self):
        if not self.fin.winfo_exists():
            return
        arrivate = False
        while self.pronte:
            self.attese.discard(self.pronte.popleft()); arrivate = True
        if arrivate and self.drag is None:
            self.disegna()
        if self.attese:
            self.fin.after(250, self.raccogli)

    # ------------------------------------------------ cliccare, trascinare, impilare
    def sotto_al_mouse(self):
        """La carta sotto l'ultimo punto del mouse (clic o movimento)."""
        return self.carta_a(*self._xy) if self._xy else None

    def pila_di(self, vid):
        for pl in self.pile:
            if vid in pl["carte"]:
                return pl
        return None

    def premi(self, e):
        self.nascondi()
        if self._xy is None:
            self._xy = (self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        vid = self.sotto_al_mouse()
        pl = self.pila_di(vid) if vid is not None else None
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        if pl is None or pl["zona"] == "cmd":
            self.drag = None
            if pl is None:      # il vuoto: il riquadro di selezione (Maiuscolo: aggiunge a quella che c'e')
                self.banda = dict(x0=x, y0=y, x=x, y=y, aggiungi=bool(e.state & 0x1))
            return
        if e.state & 0x4:       # Ctrl+clic: la pila entra o esce dalla selezione
            self.drag = None
            if self.in_sel(pl):
                self.sel = [q for q in self.sel if q is not pl]
            else:
                self.sel.append(pl)
            self.disegna_sel()
            return
        if not self.in_sel(pl) and (self.sel or self.sel_punti or self.sel_label):        # una carta fuori dalla selezione: la selezione si scioglie
            self.vuota_sel()
        gruppo = list(self.sel) if self.in_sel(pl) else None       # una pila della selezione: si sposta tutta la selezione, anche se e' una pila sola
        prese = [c for q in gruppo for c in q["carte"]] if gruppo else list(pl["carte"]) if e.state & 0x1 else [vid]
        px, _py, _s = self.pos_px(pl)
        self.drag = dict(prese=prese, da=pl, x0=x, y0=y, x=x, y=y, mosso=False, vid=vid, x_presa=px,
                         y_presa=self.ys_px(pl)[pl["carte"].index(prese[0])] if not gruppo else 0, gruppo=gruppo,
                         etichette=sorted(self.sel_label) if gruppo else [], punti=list(self.sel_punti) if gruppo else [])
        for c in prese:
            self.cv.tag_raise(f"c{c}")
            self.cv.tag_raise(f"n{c}")
            self.cv.tag_raise(f"s{c}")

    def trascina(self, e):
        if self.separa:
            return self.muovi_barra(e)
        if self.tira:
            return self.tira_muovi(e)
        if self.banda:
            return self.banda_muovi(e)
        if self.ridim:
            return self.ridim_muovi(e)
        d = self.drag
        if d is None:
            return
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        d["ex"], d["ey"] = e.x, e.y
        if not d["mosso"] and abs(x - d["x0"]) + abs(y - d["y0"]) >= 3:       # da qui e' un trascinamento; prima la carta segue lo stesso, senza ritardo
            d["mosso"] = True
            self.frecce_vive(d)
        self.sposta_presi(d, x - d["x"], y - d["y"])
        d["x"], d["y"] = x, y
        if not d["mosso"]:
            return
        self.muovi_frecce(d)
        if d.get("gruppo") is None:
            self.accendi_bersaglio(x, y)
        self.bordo_scorre()

    def sposta_presi(self, d, dx, dy):
        """Sposta sulla tela quello che si trascina: le carte prese coi loro pallini e il ⇄, i contorni della selezione, le label prese."""
        cv = self.cv
        for c in d["prese"]:
            cv.move(f"c{c}", dx, dy)
            cv.move(f"n{c}", dx, dy)
            cv.move(f"s{c}", dx, dy)
        if d.get("gruppo") is not None:
            cv.move("sel", dx, dy)
        for k in d.get("etichette") or ():
            cv.move(f"l{k}", dx, dy)
        for q in d.get("punti") or ():
            cv.move(f"p{q}", dx, dy)

    def accendi_bersaglio(self, x, y):
        self.cv.delete("bersaglio")
        b = self.bersaglio(x, y)
        if b is not None:
            x0, y0, x1, y1 = self.ingombro_px(b)
            self.cv.create_rectangle(x0 - 4, y0 - 4, x1 + 4, y1 + 4, outline=C["accento"], width=2, tags="bersaglio")

    def bordo_scorre(self):
        """Col mouse a meno di 40 pixel da un bordo, mentre trascini, il foglio scorre da solo, a ogni fotogramma (16 ms), piu' veloce piu' sei vicino al bordo, e
        la carta resta sotto il mouse. Prima scorreva a scatti, una riga intera a ogni movimento."""
        d = self.drag
        if d is None or not d.get("mosso") or d.get("scorre"):
            return
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        if W < 200 or H < 200:      # la tela non ancora a misura (una finestra di prova nascosta): niente bordi
            return
        def v(p, lato):
            return -round((40 - p) / 40 * 18) if p < 40 else round((40 - (lato - p)) / 40 * 18) if p > lato - 40 else 0
        vx, vy = v(d["ex"], W), v(d["ey"], H)
        if not vx and not vy:
            return
        cv = self.cv
        cv.scan_mark(0, 0)
        cv.scan_dragto(-vx, -vy, gain=1)
        self.sposta_presi(d, vx, vy)
        d["x"] += vx; d["y"] += vy
        self.muovi_frecce(d)
        if d.get("gruppo") is None:
            self.accendi_bersaglio(d["x"], d["y"])
        d["scorre"] = cv.after(16, lambda: (d.pop("scorre", None), self.bordo_scorre()))

    def bersaglio(self, x, y, d=None):
        """La pila sotto il mouse (pixel della tela): ci si impila solo lasciando la carta sopra un'altra pila, se no la carta resta libera dove la lasci. Escluse le
        pile che si stanno spostando, quelle del comandante e quelle della fascia chiusa, e la pila da cui viene la carta: tirata fuori, la carta se ne stacca dovunque
        la lasci (10 nov 2026, Autore: «quando sposto delle carte in un punto senza il grid snap scattano spostandosi in un punto leggermente differente»: la carta
        in cima tirata di poco fuori dalla sua pila aveva il mouse ancora sopra la pila e ci tornava, indietro di quanto l'avevi spostata; e al rilascio il
        trascinamento era gia' chiuso, quindi anche la pila tirata via tutta contava come bersaglio: il bordo azzurro diceva libera, la carta tornava a posto).
        d: il trascinamento, se non e' piu' in self.drag (il rilascio)."""
        d = d or self.drag
        su_fascia = self.in_fascia(y)       # sulla fascia solo le pile della fascia, sul foglio solo quelle del mazzo (12 nov 2026)
        for pl in reversed(self.pile):
            if pl["zona"] == "cmd" or (d and pl is d["da"]) or (pl["zona"] != "main") != su_fascia:
                continue
            x0, y0, x1, y1 = self.ingombro_px(pl)
            if x0 - 4 <= x <= x1 + 4 and y0 - 4 <= y <= y1 + 4:
                return pl
        return None

    def rilascia(self, e):
        import time as _tm
        if self.drag is not None and self.drag.get("mosso"):
            self._fine_drag = _tm.time()
        if self.drag is not None and self.drag.get("scorre"):
            self.cv.after_cancel(self.drag.pop("scorre"))
        if self.separa:     # la barra lasciata: la fascia resta a quell'altezza
            d, self.separa = self.separa, None
            if d["attesa"] is not None:
                self.cv.after_cancel(d["attesa"])
            self.disegna(); self.salva()
            return
        if self.tira:
            return self.tira_fine(e)
        if self.banda:
            return self.banda_fine()
        if self.ridim:
            self.ridim = None
            self.disegna(); self.salva()
            return
        d, self.drag = self.drag, None
        self.cv.delete("bersaglio")
        if d is None:
            return
        if not d["mosso"]:      # un clic: la carta torna dove era (si era spostata di meno di 3 pixel) e la pila si apre o si chiude, fra un attimo
            self.sposta_presi(d, d["x0"] - d["x"], d["y0"] - d["y"])
            if d["vid"] is not None:
                self.sel_carta = d["vid"]       # la carta scelta: F la inquadra
                self.disegna_sel(); self.disegna_outliner()
                self.clic = self.cv.after(230, lambda: self.apri_pila(d["vid"]))
            return
        if d.get("gruppo") is not None:     # la selezione o la label: tutte le pile insieme, alla stessa distanza fra loro, senza impilarsi
            return self.lascia_gruppo(d)
        b = self.bersaglio(d["x"], d["y"], d)
        da = d["da"]
        if self.sola:       # in sola lettura una carta non passa fra mazzo e sideboard: lasciata nell'altra zona torna al suo posto
            verso = b["zona"] if b is not None else ("side" if self.in_fascia(d["y"]) else "main")
            if verso != da["zona"]:
                self.disegna()
                return
        for c in d["prese"]:
            da["carte"].remove(c)
            if da.get("aperta") == c:
                da["aperta"] = None
        if b is not None:
            b["carte"].extend(d["prese"])
            zona = b["zona"]
        else:       # libera: una pila nuova dove e' finita la prima carta presa (nella fascia se il mouse e' sopra la barra)
            nx, ny = d["x_presa"] + d["x"] - d["x0"], d["y_presa"] + d["y"] - d["y0"]
            zona = "side" if self.in_fascia(d["y"]) else "main"
            s_ = self.sc(zona)
            bx, by = (nx - self.ox(zona)) / s_, (ny - self.oy(zona)) / s_
            if self.griglia:        # libera mentre la trascini, sulla griglia quando la lasci, in una cella libera
                gx, gy = self.cella_libera(zona, bx, by if zona == "main" else 0, len(d["prese"]))
            else:
                gx, gy = round(bx, 2), round(by, 2)       # dove la lasci, al pixel (prima a passi di 2)
            b = dict(zona=zona, x=gx, y=0 if zona != "main" else gy, carte=list(d["prese"]), aperta=None)
            self.pile.append(b)
        if not da["carte"]:
            self.pile.remove(da)
        cambiate = False
        for c in d["prese"]:
            cambiate |= self.metti_in_zona(c, zona)
        if cambiate:
            self.mazzo_cambiato()
        self.disegna()
        self.salva()

    def metti_in_zona(self, vid, zona):
        """La carta passa nella zona; se li' c'e' gia' la stessa carta, le copie si sommano su quella (una carta per nome e zona). -> True se mazzo o sideboard cambiano."""
        v = self.voci[vid]
        if v["zona"] == zona:
            return False
        gemella = next((i for i, x in self.voci.items() if i != vid and x["nome"] == v["nome"] and x["zona"] == zona), None)
        if gemella is not None:
            self.voci[gemella]["q"] += v["q"]
            self.togli(vid)
        else:
            v["zona"] = zona
        return True

    def apri_pila(self, vid):
        """Il clic su una carta in mezzo alla pila la apre: si vede intera col suo contatore, le altre scendono. Sull'ultima, o sulla carta gia' aperta, la pila si richiude."""
        self.clic = None
        pl = self.pila_di(vid)
        if pl is None:
            return
        nuova = None if (vid == pl["carte"][-1] or pl.get("aperta") == vid) else vid
        for q in self.pile:
            q["aperta"] = None
        pl["aperta"] = nuova
        self.disegna()

    def doppio(self, e):
        """Doppio clic: UNA copia passa fra mazzo e sideboard, sulla stessa carta se dall'altra parte c'e' gia', se no in una pila nuova in fondo alla zona."""
        if self.sola:
            return
        if self.clic is not None:
            self.cv.after_cancel(self.clic); self.clic = None
        if e is not None:
            cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
            sopra = self.pezzo_a(cx, cy)
            if sopra[0] == "label_t":
                self.drag = None
                return self.rinomina_etichetta(sopra[1])
            if sopra[0] is None and self.linea_a(cx, cy) is not None:
                self.drag = None
                self.stile_chiudi()
                return self.inserisci_punto(cx, cy)
            if self.vicino_barra(cy, cx) or sopra[0] in ("ctrl", "nodo"):
                return
            self._xy = (cx, cy)
        vid = self.sotto_al_mouse()
        pl = self.pila_di(vid) if vid is not None else None
        if pl is None or pl["zona"] == "cmd":
            return
        v = self.voci[vid]
        verso = "side" if v["zona"] == "main" else "main"
        gemella = next((i for i, x in self.voci.items() if x["nome"] == v["nome"] and x["zona"] == verso), None)
        if gemella is not None:
            self.voci[gemella]["q"] += 1
        else:       # una pila nuova in fondo alla prima riga della zona
            w, _h, _off, _p = misure(1.0)
            stesse = [q for q in self.pile if q["zona"] in ((verso, "cmd") if verso == "side" else (verso,))]
            y = 0 if verso == "side" else min((q["y"] for q in stesse), default=0)
            riga = [q["x"] for q in stesse if q["y"] == y]
            nuovo = max(self.voci) + 1
            self.voci[nuovo] = dict(nome=v["nome"], zona=verso, q=1)
            self.pile.append(dict(zona=verso, x=max(riga) + w + SPAZIO if riga else MARGINE, y=y, carte=[nuovo], aperta=None))
        v["q"] -= 1
        if v["q"] <= 0:
            self.togli(vid)
        self.drag = None
        self.mazzo_cambiato()
        self.disegna()
        self.salva()

    def mazzo_cambiato(self):
        if not self.modifica:
            return
        lista, side = self.liste()
        if self.editore is not None:        # nel builder: il mazzo e' suo, lo salva lui (col suo Save)
            self.editore(lista, side)
        self.cambiato = True        # da solo: il mazzo si scrive con Save (scrivi_tutto), non a ogni gesto (12 nov 2026)
        if self.al_cambio:
            self.al_cambio(lista, side)

    def liste(self):
        lista, side = collections.Counter(), collections.Counter()
        for v in self.voci.values():
            if v["zona"] == "main":
                lista[v["nome"]] += v["q"]
            elif v["zona"] == "side":
                side[v["nome"]] += v["q"]
        return dict(lista), dict(side)

    # ------------------------------------------------ salvare e riprendere la disposizione
    def salva(self):
        """Dopo ogni gesto. In modalita' edit il gesto entra nello storico e il file aspetta Save (12 nov 2026); in sola lettura si scrive la disposizione."""
        if self.modifica:
            self.registra()
            return
        self.scrivi()

    def scrivi(self):
        if not self.chiave or (self.sola and not self.sposta):        # in sola lettura si salva solo la disposizione delle carte spostate (10 nov 2026)
            return
        try:
            salva_tavolo(self.chiave, dict(v=2, zoom=self.zoom, fascia=self.hs, etichette=[dict(lb) for lb in self.etichette], note=dict(self.note),
                                                    nascoste=[[n, z] for n, z in sorted(self.occhi)],
                                                    punti=[dict(id=q, **p_) for q, p_ in self.punti.items()], vie=[[a, b, q] for (a, b), q in self.vie.items()], pile=[dict(zona=pl["zona"], x=pl["x"], y=pl["y"], carte=[[self.voci[c]["nome"], self.voci[c]["q"]] for c in carte_])
                                                                    for pl, carte_ in self.pile_tutte()]), self.file_tavoli)
        except OSError as e:
            print("tavolo: non salvato:", e)

    def riprendi(self):
        """La disposizione salvata, sempre (Autore, 9 nov 2026: «alla riapertura mantenga il posizionamento che ho creato delle carte»): ogni carta che c'e'
        ancora torna al suo posto, con le copie di adesso; una carta nuova va sulla pila del suo costo (o in una pila nuova), una tolta sparisce. Fino a quel giorno la
        disposizione tornava solo se il mazzo era identico copia per copia, e il builder la teneva sotto un'altra chiave (e per un mazzo nuovo, senza id, non la salvava).
        Un mazzo che si cambia torna zona per zona; uno di Arena o del meta per nome (li' mazzo e sideboard sul tavolo sono solo una disposizione)."""
        if not self.chiave:
            return False
        tutte = carica_tavoli(self.file_tavoli)
        t = tutte.get(self.chiave) or (tutte.get(self.chiave_vecchia) if self.chiave_vecchia else None)
        if not t or not all(isinstance(c, list) for pl in t.get("pile", []) for c in pl["carte"]):     # una disposizione del primo giro (una carta per copia): si rifa'
            return False
        self.etichette = [dict(nome=str(x.get("nome") or "Label"), x=x["x"], y=x["y"], w=x["w"], h=x["h"], colore=x.get("colore") or GRIGIO_L,
                               lucchetto=x.get("lucchetto", True), **({"nota": str(x["nota"]), "nota_aperta": bool(x.get("nota_aperta"))} if x.get("nota") else {}),
                               **({"id": str(x["id"])} if x.get("id") else {}), **({"nascosta": True} if x.get("nascosta") else {}),
                               **({"copia": True, "carte": {str(n): int(q) for n, q in (x.get("carte") or {}).items()}, "origine": x.get("origine")}
                                  if x.get("copia") else {}))
                          for x in t.get("etichette") or [] if all(k in x for k in ("x", "y", "w", "h"))]
        self.note = {str(n): dict(testo=str(v.get("testo")), aperta=bool(v.get("aperta"))) for n, v in (t.get("note") or {}).items()
                     if isinstance(v, dict) and v.get("testo")}
        self.occhi = {(str(n), str(z)) for n, z in (t.get("nascoste") or []) if z in ("main", "side", "cmd")}
        self.punti = {}
        for x in t.get("punti") or []:
            if not all(k in x for k in ("id", "x", "y")):
                continue
            ing = x.get("ingressi")
            if ing is None:         # il primo giro: un ingresso solo, il dot prima o il padre
                ing = [["p", int(x["da"])]] if x.get("da") is not None else [["c", x["padre"]]] if x.get("padre") else []
            self.punti[int(x["id"])] = dict(x=x["x"], y=x["y"], ingressi=[[k, int(v) if k == "p" else v] for k, v in ing])
        self.vie = {(a, b): int(q) for a, b, q in t.get("vie") or [] if int(q) in self.punti}
        ora = collections.Counter()
        for v in self.voci.values():
            ora[(v["nome"], v["zona"])] += v["q"]
        per_nome = collections.Counter()
        for (n, z), q in ora.items():
            if z != "cmd":
                per_nome[n] += q
        nuova = t.get("v") == 2
        _w, h, off, _p = misure(1.0)
        vecchio_inizio = 2 * ETICHETTA + h + 2 * off + 28       # la disposizione del primo giro: y assolute, il mazzo cominciava qui (scala 1)
        voci, pile, resto, messe = {}, [], dict(ora), 0
        for pl in t["pile"]:
            carte = []
            for n, q_salvato in pl["carte"]:
                if self.modifica or pl["zona"] == "cmd":
                    q = resto.pop((n, pl["zona"]), 0)
                else:       # di Arena o del meta: il nome conta, la zona e' quella che gli hai dato sul tavolo
                    q = min(q_salvato, per_nome[n])
                    per_nome[n] -= q
                if q > 0:
                    i = len(voci)
                    voci[i] = dict(nome=n, zona=pl["zona"], q=q)
                    carte.append(i)
            if carte:
                y = pl["y"] if nuova else (max(0, pl["y"] - vecchio_inizio) if pl["zona"] == "main" else 0)
                pile.append(dict(zona=pl["zona"], x=pl["x"], y=y if pl["zona"] == "main" else 0, carte=carte, aperta=None))
                messe += len(carte)
        if not messe:
            return False
        self.voci, self.pile = voci, pile
        if self.modifica:
            mancanti = resto.items()
        else:
            mancanti = [((n, z), min(q, per_nome[n])) for (n, z), q in ora.items() if z != "cmd" and per_nome[n] > 0]
            mancanti += [((n, z), q) for (n, z), q in resto.items() if z == "cmd" and not any(v["nome"] == n and v["zona"] == "cmd" for v in voci.values())]
        for (n, z), q in mancanti:
            if q > 0:
                if not self.modifica and z != "cmd":
                    per_nome[n] -= q
                self.nuova_voce(n, z, q)
        self.zoom = float(t["zoom"]) if nuova and t.get("zoom") else SCALE.get(t.get("taglia"), 1.0)
        self.hs = int(t["fascia"]) if nuova and t.get("fascia") is not None else FASCIA_DEF
        self.l_zoom.configure(text=f"{round(self.zoom * 100)}%")
        return True

    # ------------------------------------------------ lo storico: Undo, Redo, Save (12 nov 2026)
    def foto_stato(self):
        """Tutto quello che un gesto puo' cambiare: le carte e le pile (anche quelle tenute da parte dal filtro), le label, le note, i dot, la rete."""
        import copy
        return copy.deepcopy(dict(voci=self.voci, pile=[dict(zona=pl["zona"], x=pl["x"], y=pl["y"], carte=list(c_)) for pl, c_ in self.pile_tutte()],
                                  etichette=self.etichette, note=self.note, punti=self.punti, vie=self.vie, figli=self.rete.figli, stili=self.rete.stili,
                                  occhi=sorted(self.occhi)))

    def registra(self):
        if not self.storia:
            return
        f = self.foto_stato()
        if f == self.storia[self.passo]:
            return
        del self.storia[self.passo + 1:]
        if self.salvato_a > self.passo:      # lo stato salvato era un Redo che non c'e' piu'
            self.salvato_a = -1
        self.storia.append(f)
        self.passo += 1
        if len(self.storia) > 200:      # il tetto: i gesti piu' vecchi escono
            self.storia.pop(0); self.passo -= 1; self.salvato_a -= 1
        self.aggiorna_salva()

    @property
    def da_salvare(self):
        return self.modifica and bool(self.storia) and self.passo != self.salvato_a

    def ripristina(self, f):
        import copy
        f = copy.deepcopy(f)
        self.nascondi()
        self._riposte = []
        self.voci = f["voci"]
        self.pile = [dict(p_, aperta=None) for p_ in f["pile"]]
        self.etichette, self.note, self.punti, self.vie = f["etichette"], f["note"], f["punti"], f["vie"]
        self.rete.figli, self.rete.stili = f["figli"], f["stili"]
        self.occhi = {tuple(x) for x in f.get("occhi") or []}
        self.sel, self.sel_punti, self.sel_label, self.sel_carta = [], set(), set(), None
        if self.modifica:
            lista, side = self.liste()
            if self.editore is not None:
                self.editore(lista, side)
            self.cambiato = True
            if self.al_cambio:
                self.al_cambio(lista, side)
        self.disegna()
        self.aggiorna_salva()

    def annulla(self):
        """Undo (Ctrl+Z): il gesto di prima."""
        if not self.modifica or self.passo <= 0:
            self.dici("Nothing to undo")
            return False
        self.passo -= 1
        self.ripristina(self.storia[self.passo])
        self.dici("Undo")
        return True

    def ripeti(self):
        """Redo (Ctrl+Y o Ctrl+Shift+Z): il gesto annullato."""
        if not self.modifica or self.passo >= len(self.storia) - 1:
            self.dici("Nothing to redo")
            return False
        self.passo += 1
        self.ripristina(self.storia[self.passo])
        self.dici("Redo")
        return True

    def salva_tutto(self):
        """Save: col builder salva lui il mazzo e poi chiama scrivi_tutto; da solo scrive mazzo, disposizione e rete."""
        if self.salvataggio is not None:
            self.salvataggio()
        else:
            self.scrivi_tutto()
        self.dici("Saved")

    def scrivi_tutto(self):
        if not self.modifica:
            return
        if self.editore is None and self.modificabile:
            sez, mid = self.modificabile
            lista, side = self.liste()
            MS.cambia(sez, mid, f=self.file_mazzi, lista=lista, side=side)
        self.scrivi()
        self.rete.salva(forza=True)
        self.salvato_a = self.passo
        self.aggiorna_salva()

    def aggiorna_salva(self):
        """Save col punto quando ci sono modifiche da salvare; Undo e Redo spenti quando non c'e' niente."""
        b = getattr(self, "b_salva", None)
        if b is not None and b.winfo_exists():
            b.metti("Save ●" if self.da_salvare else "Save", False)
        for chi, attivo in (("b_undo", self.passo > 0), ("b_redo", self.passo < len(self.storia) - 1)):
            w = getattr(self, chi, None)
            if w is not None and w.winfo_exists():
                w.spegni(not attivo)

    def nuova_chiave(self, chiave, chiave_rete=None):
        """Il mazzo del builder ha appena preso il suo id (il primo Save): da qui la disposizione e la rete si salvano sotto la sua chiave."""
        if chiave and chiave != self.chiave:
            self.chiave = chiave
            self.salva()
        if chiave_rete and self.rete.chiave != chiave_rete:
            self.rete.chiave = chiave_rete
            self.rete.salva()

    # ------------------------------------------------ la carta grande al passaggio del mouse
    def passa(self, e):
        import time as _tm
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        self._xy = (cx, cy)
        if self.drag is None and not self.tira and self.hud_su(e.x, e.y):
            self.nascondi()
            self.cv.configure(cursor="hand2" if self.hud_su(e.x, e.y) == "testa" else "")
            return
        pezzo = self.pezzo_a(cx, cy)[0]
        if self.drag is None and not self.tira:
            self.nota_hover(self.carta_a(cx, cy))
        self.bagliore_label(cx, cy if self.drag is None and not self.tira else None)
        bx_ = getattr(self, "_barra_box", None)
        verso_barra = bool(bx_ and (self._arco or self._arco_t) and bx_[0] <= cx <= bx_[2] and bx_[1] <= cy <= bx_[3])
        if self.drag is None and not self.tira and not self.sola and not verso_barra and pezzo not in ("rete_x", "rete_s", "rete_c", "rete_xt"):
            sg = self.arco_a(cx, cy) if pezzo is None else None
            tr = self.tronco_a(cx, cy) if pezzo is None and sg is None else None
            if tr is not None:
                self.accendi_tronco(tr)
            else:
                self.accendi_arco(sg)
        self.cv.configure(cursor="sb_v_double_arrow" if self.vicino_barra(cy, cx) and pezzo is None else "hand2" if pezzo in ("nodo", "ctrl", "rete_x", "rete_s", "rete_c", "rete_xt", "punto_out", "scambia", "label_x", "label_l", "label_m", "sel_menu",
                                                                                                                                         "nota_i", "nota_b", "nota_n", "label_n", "label_nb")
                          or self._arco else "fleur" if pezzo in ("carta", "label_t", "punto") else "size_nw_se" if pezzo == "label_r" else "")
        if self.drag is not None or _tm.time() - self._fine_drag < 0.8:
            return
        vid = self.sotto_al_mouse()
        if vid == self.hover["cid"]:
            return
        self.nascondi()
        self.hover["cid"] = vid
        if vid is not None:
            self.hover["timer"] = self.cv.after(450, lambda: self.mostra(vid))

    def nascondi(self):
        h = self.hover
        if h["timer"] is not None:
            try:
                self.cv.after_cancel(h["timer"])
            except Exception:
                pass
        if h["pop"] is not None:
            try:
                h["pop"].destroy()
            except Exception:
                pass
        h.update(cid=None, timer=None, pop=None)

    def mostra(self, vid):
        h = self.hover
        h["timer"] = None
        if self.drag is not None or h["cid"] != vid or vid not in self.voci:
            return
        n = self.voci[vid]["nome"]
        if not os.path.exists(CAP.file_immagine(n)):
            return
        try:
            img = self.lista.immagine(n)
        except Exception:
            return
        bb = self.cv.bbox(f"c{vid}")
        if not bb:
            return
        p = h["pop"] = self.tk.Toplevel(self.fin)
        p.overrideredirect(True)
        p.configure(bg=C["fondo"])
        self.tk.Label(p, image=img, bd=0, bg=C["fondo"]).pack()
        p.update_idletasks()
        w, hh = p.winfo_reqwidth(), p.winfo_reqheight()
        rx = self.cv.winfo_rootx() - int(self.cv.canvasx(0))
        ry = self.cv.winfo_rooty() - int(self.cv.canvasy(0))
        x = rx + bb[2] + 8
        if x + w > self.fin.winfo_rootx() + self.fin.winfo_width():
            x = rx + bb[0] - w - 8
        y = max(self.fin.winfo_rooty(), min(ry + bb[1], self.fin.winfo_rooty() + self.fin.winfo_height() - hh))
        p.geometry(f"{w}x{hh}+{x}+{y}")

    # ------------------------------------------------ la fine
    # ------------------------------------------------ la selezione, il gruppo e le label (Autore, 9 nov 2026: «possiamo mettere la possibilita' di selezionare ad
    # area piu' carte e spostarle mantenendo le connessioni?», «label di carte dentro le quali diamo un nome»)
    def in_sel(self, pl):
        return any(q is pl for q in self.sel)

    def disegna_sel(self):
        """Il contorno azzurro di ogni pila selezionata, sopra le carte e sotto i pallini."""
        cv = self.cv
        cv.delete("sel")
        cv.delete("sel_c")
        if self.sel_carta in self.voci and not self.sel and not self.sel_punti and not self.sel_label:      # la carta scelta, col filo azzurro
            rc = self.rett(self.sel_carta)
            if rc:
                cv.create_rectangle(rc[0] - 3, rc[1] - 3, rc[2] + 3, rc[3] + 3, outline=C["accento"], width=2, tags="sel_c")
        self.sel = [q for q in self.sel if any(q is p_ for p_ in self.pile)]
        for q in self.sel:
            if q["zona"] != "main" and self.nascosta():
                continue
            x0, y0, x1, y1 = self.ingombro_px(q)
            m = round(14 * max(self.sc(q["zona"]), 0.75))
            cv.create_rectangle(x0 - m - 4, y0 - 5, x1 + 5, y1 + 5, outline=C["accento"], width=2, tags="sel")
        self.sel_punti = {q for q in self.sel_punti if q in self.punti}
        for q in self.sel_punti:
            x, y, r = self.punto_xy(q)
            cv.create_rectangle(x - r - 4, y - r - 4, x + r + 4, y + r + 4, outline=C["accento"], width=2, tags=("sel", f"p{q}"))
        self.sel_label = {k for k in self.sel_label if k < len(self.etichette)}
        for k in self.sel_label:
            x0, y0, x1, y1 = self.lb_px(k)
            cv.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=C["accento"], width=2, tags="sel")
        cor = self.cornice_sel()
        if cor:     # la cornice intorno a tutta la selezione, e fuori, in alto a destra, le tre linee del menu (Autore, 10 nov 2026: «l'iconcina mettila fuori dalla
            # selezione in alto a dx»; prima stava al centro)
            cv.create_rectangle(*cor, outline=C["accento"], width=1, dash=(6, 4), tags=("sel", "sel_cornice"))
            cv.create_image(cor[2] + 6, cor[1], image=segno_menu(26), anchor="nw", tags=("sel", "sel_menu"))
        cv.tag_raise("sel")
        cv.tag_raise("nodo")
        cv.tag_raise("sel_menu")

    def vuota_sel(self):
        self.sel, self.sel_punti, self.sel_label = [], set(), set()
        self.sel_carta = None
        self.disegna_sel()

    def cornice_sel(self):
        """La cornice della selezione, in pixel della tela: intorno alle pile, ai dot e alle label selezionati. None senza selezione."""
        rr = []
        for q in self.sel:
            if q["zona"] != "main" and self.nascosta():
                continue
            x0, y0, x1, y1 = self.ingombro_px(q)
            m = round(14 * max(self.sc(q["zona"]), 0.75))
            rr.append((x0 - m - 4, y0 - 5, x1 + 5, y1 + 5))
        for q in self.sel_punti:
            if q in self.punti:
                x, y, r = self.punto_xy(q)
                rr.append((x - r - 4, y - r - 4, x + r + 4 + 14, y + r + 4))
        for k in self.sel_label:
            if k < len(self.etichette):
                rr.append(self.lb_px(k))
        if not rr:
            return None
        return min(r[0] for r in rr) - 12, min(r[1] for r in rr) - 12, max(r[2] for r in rr) + 12, max(r[3] for r in rr) + 12

    def gruppo_inizio(self, cx, cy):
        """Premuto dentro la cornice della selezione: si trascina tutto, pile, dot e label, anche una pila sola."""
        piles = list(self.sel)
        self.drag = dict(prese=[c for q in piles for c in q["carte"]], da=None, x0=cx, y0=cy, x=cx, y=cy, mosso=False, vid=None, x_presa=0, y_presa=0,
                         gruppo=piles, etichette=sorted(self.sel_label), punti=list(self.sel_punti))

    def banda_muovi(self, e):
        b = self.banda
        b["x"], b["y"] = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        self.cv.delete("banda")
        self.cv.create_rectangle(min(b["x0"], b["x"]), min(b["y0"], b["y"]), max(b["x0"], b["x"]), max(b["y0"], b["y"]), outline=C["accento"], width=1, dash=(4, 3),
                                 tags="banda")

    def banda_fine(self):
        """Lasciato il riquadro: le pile che tocca sono la selezione (con Maiuscolo si aggiungono). Un clic nel vuoto la scioglie."""
        b, self.banda = self.banda, None
        self.cv.delete("banda")
        if abs(b["x"] - b["x0"]) + abs(b["y"] - b["y0"]) < 3:
            if (self.sel or self.sel_punti or self.sel_label) and not b["aggiungi"]:
                self.vuota_sel()
            return
        X0, X1 = sorted((b["x0"], b["x"]))
        Y0, Y1 = sorted((b["y0"], b["y"]))
        nuove = []
        for pl in self.pile:
            if pl["zona"] == "cmd" or (pl["zona"] != "main" and self.nascosta()):
                continue
            a = self.ingombro_px(pl)
            if a[0] <= X1 and a[2] >= X0 and a[1] <= Y1 and a[3] >= Y0:
                nuove.append(pl)
        self.sel = (list(self.sel) if b["aggiungi"] else []) + [q for q in nuove if not (b["aggiungi"] and self.in_sel(q))]
        punti = {q for q in self.punti if (lambda pt: X0 <= pt[0] <= X1 and Y0 <= pt[1] <= Y1)(self.punto_xy(q))}
        self.sel_punti = (self.sel_punti | punti) if b["aggiungi"] else punti
        label = {k for k in range(len(self.etichette)) if (lambda r: X0 <= r[0] and r[2] <= X1 and Y0 <= r[1] and r[3] <= Y1)(self.lb_px(k))}
        self.sel_label = (self.sel_label | label) if b["aggiungi"] else label
        self.disegna_sel()
        if self.sel or self.sel_punti or self.sel_label:
            self.dici("Selected: drag inside the frame to move them together · ≡ in the middle: label")

    def lascia_gruppo(self, d):
        """Lasciato un gruppo (la selezione, o le pile di una label): ogni pila si sposta dello stesso passo, nella sua zona (nella fascia solo in orizzontale), le
        label prese pure. Le connessioni restano: sono fra le carte, non fra i posti."""
        dx, dy = d["x"] - d["x0"], d["y"] - d["y0"]
        # sulla griglia (10 nov 2026): il primo elemento del gruppo va nella cella piu' vicina e tutto il resto si sposta dello stesso passo, cosi' le distanze
        # restano; per zona, perche' mazzo e fascia hanno scale diverse
        passo = {}
        if not self.griglia:        # la griglia spenta: tutto dello stesso passo del mouse
            for zona in ("main", "side"):
                s_ = self.sc(zona) or 1.0
                passo[zona] = (dx / s_, dy / s_ if zona == "main" else 0)
        for zona in ("main", "side") if self.griglia else ():
            pl0 = next((pl for pl in d["gruppo"] if pl["zona"] == zona), None)
            if pl0 is not None:
                s_ = self.sc(zona) or 1.0
                gx, gy = a_griglia(pl0["x"] + dx / s_, pl0["y"] + dy / s_)
                passo[zona] = (gx - pl0["x"], (gy - pl0["y"]) if zona == "main" else 0)
        if "main" not in passo:
            z = self.zoom
            etq = list(d.get("etichette") or ())
            if etq:     # una label da sola: il suo interno sulla griglia
                lb = self.etichette[etq[0]]
                ix, iy = lb["x"] + PAD_L + 14 + dx / z, lb["y"] + TIT_L + PAD_L + dy / z
                gx, gy = a_griglia(ix, iy)
                passo["main"] = (gx - ix + dx / z, gy - iy + dy / z)
            elif d.get("punti"):        # un dot da solo: a meta' colonna
                p_ = self.punti.get(d["punti"][0])
                if p_ is not None:
                    gx, gy = a_griglia(p_["x"] + dx / z, p_["y"] + dy / z, mezza=True)
                    passo["main"] = (gx - p_["x"], gy - p_["y"])
            else:
                passo["main"] = (dx / z, dy / z)
        if self.griglia and "main" in passo and any(pl["zona"] == "main" for pl in d["gruppo"]):        # le pile del gruppo non finiscono sopra altre pile
            passo["main"] = self.passo_libero(d["gruppo"], passo["main"], (dx / self.zoom, dy / self.zoom))
        for pl in d["gruppo"]:
            ddx, ddy = passo.get(pl["zona"], (0, 0))
            pl["x"] += ddx
            if pl["zona"] == "main":
                pl["y"] += ddy
        ddx, ddy = passo["main"]
        for k in d.get("etichette") or ():
            lb = self.etichette[k]
            lb["x"] += ddx
            lb["y"] += ddy
        for q in d.get("punti") or ():
            if q in self.punti:
                self.punti[q]["x"] += ddx
                self.punti[q]["y"] += ddy
        self.disegna()
        self.salva()

    def occupato(self, zona, r, ignora=()):
        """Il rettangolo r (coordinate del mazzo, scala 1) tocca una pila della zona che non e' fra quelle da ignorare?"""
        for pl in self.pile:
            if pl["zona"] != zona or not pl["carte"] or any(pl is q for q in ignora):
                continue
            a = self.ingombro(pl)
            if a[0] < r[2] - 1 and r[0] < a[2] - 1 and a[1] < r[3] - 1 and r[1] < a[3] - 1:
                return True
        return False

    def cella_libera(self, zona, x, y, n, ignora=()):
        """La cella della griglia per una pila di n carte lasciata in (x, y): la piu' vicina, e se e' occupata da un'altra pila, la cella libera piu' vicina al punto
        (Autore, 10 nov 2026: «ha ancora alcuni difettini di autosnap nel movimento»: una carta lasciata accanto a una pila poteva agganciarsi sulla sua colonna e
        finirle sopra). Si cerca fino a 3 colonne e 24 righe di distanza."""
        w, h, off, _p = misure(1.0)
        alta = h + (max(1, n) - 1) * off
        cand = []
        gx, gy = a_griglia(x, y)
        for i in range(-3 * CELLE_X, 3 * CELLE_X + 1):
            for j in (range(-24 * CELLE_Y, 24 * CELLE_Y + 1) if zona == "main" else (0,)):
                cx, cy = gx + i * CELLA_X, (gy + j * CELLA_Y) if zona == "main" else 0
                cand.append(((cx - x) ** 2 + (cy - y) ** 2, cx, cy))
        cand.sort()
        altre = [self.ingombro(pl) for pl in self.pile if pl["zona"] == zona and pl["carte"] and not any(pl is q for q in ignora)]
        for _d, cx, cy in cand:
            if not any(a[0] < cx + w - 1 and cx < a[2] - 1 and a[1] < cy + alta - 1 and cy < a[3] - 1 for a in altre):
                return cx, cy
        return a_griglia(x, y if zona == "main" else 0)

    def passo_libero(self, gruppo, passo, voluto):
        """Il passo del gruppo sulla griglia: quello del primo elemento, e se una pila del gruppo finirebbe sopra una pila che non ne fa parte, il passo libero piu'
        vicino a quello voluto (il movimento del mouse)."""
        main = [pl for pl in gruppo if pl["zona"] == "main"]
        rett = [self.ingombro(pl) for pl in main]

        def libero(dx, dy):
            return not any(self.occupato("main", (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy), ignora=gruppo) for r in rett)
        if libero(*passo):
            return passo
        cand = sorted((((passo[0] + i * CELLA_X - voluto[0]) ** 2 + (passo[1] + j * CELLA_Y - voluto[1]) ** 2), passo[0] + i * CELLA_X, passo[1] + j * CELLA_Y)
                      for i in range(-3 * CELLE_X, 3 * CELLE_X + 1) for j in range(-24 * CELLE_Y, 24 * CELLE_Y + 1))
        for _d, dx, dy in cand:
            if libero(dx, dy):
                return dx, dy
        return passo

    def membri(self, k):
        """Le pile del mazzo dentro la label (il centro della pila nel riquadro) e le label tutte dentro di lei."""
        lb = self.etichette[k]
        if lb.get("copia"):        # un gruppo duplicato ha le sue carte scritte, non pile del mazzo
            self._punti_dentro = []
            return [], []
        dentro = lambda cx, cy: lb["x"] <= cx <= lb["x"] + lb["w"] and lb["y"] <= cy <= lb["y"] + lb["h"]
        pile = [pl for pl in self.pile if pl["zona"] == "main" and dentro(*(lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2))(self.ingombro(pl)))]
        altre = [j for j, l2 in enumerate(self.etichette) if j != k and lb["x"] <= l2["x"] and l2["x"] + l2["w"] <= lb["x"] + lb["w"]
                 and lb["y"] <= l2["y"] and l2["y"] + l2["h"] <= lb["y"] + lb["h"]]
        self._punti_dentro = [q for q, p_ in self.punti.items() if dentro(p_["x"], p_["y"])]
        return pile, altre

    def etichetta_inizio(self, k, cx, cy):
        """Premuto il titolo di una label: col lucchetto chiuso si trascina lei con le sue pile, i suoi dot e le label dentro (le connessioni seguono); col lucchetto
        aperto si sposta da sola, cosi' la porti sopra altre carte per metterle dentro (Autore, 10 nov 2026)."""
        if self.sel or self.sel_punti or self.sel_label:
            self.vuota_sel()
        if not self.etichette[k].get("lucchetto", True):
            self.drag = dict(prese=[], da=None, x0=cx, y0=cy, x=cx, y=cy, mosso=False, vid=None, x_presa=0, y_presa=0, gruppo=[], etichette=[k], punti=[])
            return
        pile, altre = self.membri(k)
        self.drag = dict(prese=[c for pl in pile for c in pl["carte"]], da=None, x0=cx, y0=cy, x=cx, y=cy, mosso=False, vid=None, x_presa=0, y_presa=0,
                         gruppo=pile, etichette=[k] + altre, punti=list(self._punti_dentro))

    def lucchetto_label(self, k):
        """Il lucchetto sul titolo della label: chiuso, la label si sposta con quello che ha dentro; aperto, da sola."""
        if k is None or not 0 <= k < len(self.etichette):
            return
        lb = self.etichette[k]
        lb["lucchetto"] = not lb.get("lucchetto", True)
        self.disegna()
        self.salva()
        self.dici(f"«{lb['nome']}» " + ("locked: it moves with its cards" if lb["lucchetto"] else "unlocked: it moves alone, drop it over other cards to take them in"))

    def menu_label(self, k):
        """Il menu della label (Autore, 10 nov 2026: «al centro della cornice un'icona a 3 linee: e' li' che voglio il menu della label: nome e colore»): dalla
        cornice della selezione fa una label nuova intorno alla selezione; dal titolo di una label la cambia (nome, colore, lucchetto, nota, Duplicate, Swap, Delete).
        Nello stile comune dei mini-menu (menu_board, 13 nov 2026). Invio salva, Esc chiude."""
        tk, F = self.tk, self.F
        self.stile_chiudi()
        self.nome_chiudi()
        nuova = k is None
        if nuova and not any(q["zona"] == "main" for q in self.sel) and not self.sel_punti and not self.sel_label:
            self.dici("Select the cards first: drag a box on the empty sheet, or Ctrl+click the piles")
            return None
        lb = None if nuova else self.etichette[k]
        scelto = dict(colore=(lb.get("colore") if lb else None) or GRIGIO_L)
        m = MB.Menu(tk, F, self.fin, "New group" if nuova else "Group", chiudi=self.nome_chiudi)
        p = self._nome_pop = m.p
        m.sezione("Name")
        var = tk.StringVar(value=lb["nome"] if lb else "")
        e = m.campo(m.riga(), var, larga=30)
        m.sezione("Color")
        colori = [("Gray", GRIGIO_L)] + list(RS.COLORI)
        cvc = tk.Canvas(m.riga(), width=len(colori) * 28, height=28, bg=MB.FONDO, highlightthickness=0, cursor="hand2"); cvc.pack(anchor="w")

        def tinte():
            cvc.delete("all")
            for i, (_n, hx) in enumerate(colori):
                x = i * 28 + 3
                if hx == scelto["colore"]:
                    cvc.create_rectangle(x - 2, 2, x + 22, 26, outline=MB.NEON, width=2)
                cvc.create_rectangle(x + 2, 6, x + 18, 22, fill=hx, outline="#ffffff" if hx == scelto["colore"] else C["filo"], width=1)

        def colore(c):
            scelto["colore"] = c
            if lb is not None:
                lb["colore"] = c
                self.disegna(); self.salva()
            tinte()

        def clic(ev):
            i = int(ev.x // 28)
            if 0 <= i < len(colori):
                colore(colori[i][1])
        cvc.bind("<Button-1>", clic)

        def applica(*_a):
            n = var.get().strip()
            self.nome_chiudi()
            if nuova:
                self.crea_etichetta(n or "Label", scelto["colore"])
            else:
                lb["nome"] = n or lb["nome"]
                lb["colore"] = scelto["colore"]
                self.disegna(); self.salva()
            return "break"
        if not nuova:
            m.sezione("Group")
            chiusa = lb.get("lucchetto", True)
            r_l = m.voce("Locked: moves with its cards" if chiusa else "Unlocked: moves alone",
                         "Click to unlock it" if chiusa else "Click to lock it", lambda: None, chiudi=False)

            def lucchetto(_e=None):
                self.lucchetto_label(k)
                on = self.etichette[k].get("lucchetto", True)
                lab = [w_ for w_ in r_l.winfo_children()[1].winfo_children()]
                lab[0].configure(text="Locked: moves with its cards" if on else "Unlocked: moves alone")
                lab[1].configure(text="Click to unlock it" if on else "Click to lock it")
            for w_ in [r_l] + list(r_l.winfo_children()) + list(r_l.winfo_children()[1].winfo_children()):
                w_.bind("<Button-1>", lucchetto)
            m.voci["lock"] = lucchetto
            m.voce("Note…", "A note on this group, on its title", lambda: self.editor_nota("l", k), colore="#f0ad4e")
            if self.modifica:       # i gruppi (12 nov 2026): duplicare, scambiare una copia con l'originale, togliere il gruppo con le sue carte
                if lb.get("copia"):
                    m.voce(f"⇄ Swap with «{self.nome_origine(lb)}»", "The copy's cards go in the deck, the original's come here", lambda: self.scambia_gruppo(k))
                else:
                    m.voce("Duplicate", "A copy beside it: change its cards, then Swap", lambda: self.duplica_gruppo(k))
            m.voce("Delete the frame", "The cards stay where they are", lambda: self.togli_etichetta(k), colore=C["rosso"])
            if self.modifica and not lb.get("copia"):
                m.voce("Delete with its cards", "The group and its cards leave the deck", lambda: self.togli_gruppo(k), colore=C["rosso"])
        m.pulsanti([("Create" if nuova else "Save", applica, "salva"), ("Cancel", self.nome_chiudi, "secondario")])
        m.piede("Enter saves · Esc closes · the color changes at once")
        e.bind("<Return>", applica)
        e.bind("<Escape>", lambda ev: self.nome_chiudi())
        tinte()
        m.posa(fuoco=e)
        e.select_range(0, "end")
        p.menu = dict(applica=applica, colore=colore, nome=var)        # per le prove
        p.voci = m.voci
        return p


    def ridim_muovi(self, e):
        """L'angolo in basso a destra della label: la misura, a passi di un disegno per fotogramma."""
        r = self.ridim
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        lb = self.etichette[r["k"]]
        lb["w"] = max(160, round(r["w0"] + (cx - r["x0"]) / self.zoom))
        lb["h"] = max(90, round(r["h0"] + (cy - r["y0"]) / self.zoom))
        if r["attesa"] is None:
            def fai():
                r["attesa"] = None
                self.disegna()
            r["attesa"] = self.cv.after(16, fai)

    def lb_px(self, k):
        lb, z, o = self.etichette[k], self.zoom, self.oy("main")
        return lb["x"] * z, o + lb["y"] * z, (lb["x"] + lb["w"]) * z, o + (lb["y"] + lb["h"]) * z

    def disegna_etichette(self):
        """Ogni label: il riquadro, il titolo col nome (si trascina; doppio clic lo rinomina), la ✕ che la toglie (le carte restano), l'angolo che la allarga."""
        cv, z, o = self.cv, self.zoom, self.oy("main")
        for k, lb in enumerate(self.etichette):
            if not self.etichetta_vista(k):      # col filtro per tipo, il gruppo senza carte a vista si spegne con loro
                continue
            x0, y0 = lb["x"] * z, o + lb["y"] * z
            x1, y1 = x0 + lb["w"] * z, y0 + lb["h"] * z
            th = max(16, TIT_L * z)
            tg = ("label", f"l{k}")
            fz = max(7, round(9 * min(z, 1.6)))
            col = lb.get("colore") or GRIGIO_L
            if lb.get("copia"):
                self.misura_copia(k)
                x1, y1 = x0 + lb["w"] * z, y0 + lb["h"] * z
            cv.create_rectangle(x0, y0, x1, y1, fill=mescola(FONDO_L, col, 0.09), outline=col, width=1, tags=tg, **({"dash": (5, 4)} if lb.get("copia") else {}))
            cv.create_rectangle(x0, y0, x1, y0 + th, fill=mescola(TESTA_L, col, 0.3), outline=col, width=1, tags=tg + ("label_t", f"lt{k}"))
            cv.create_text(x0 + 10, y0 + th / 2, text=lb["nome"].upper(), fill=C["titolo"], font=self.F(fz, True), anchor="w",
                           tags=tg + ("label_t", f"lt{k}"))
            if lb.get("copia"):
                self.disegna_copia(k, x0, y0, x1, th, fz)
            if self.sola:       # in sola lettura la label si vede col suo nome, senza strumenti (la sua nota si', da aprire e chiudere)
                if lb.get("nota"):
                    cv.create_image(x1 - 8 - 18, y0 + th / 2 - 9, image=segno_nota(18, True), anchor="nw", tags=tg + ("nota", "label_n", f"ln{k}"))
                    if lb.get("nota_aperta"):
                        self.nota_box(x0 + 8, y0 + th + 6, lb["nota"], ("label_nb", f"lb{k}"), larga=max(160, min(300, x1 - x0 - 16)))
                continue
            cv.create_image(x1 - 8 - 12, y0 + th / 2 - 6, image=croce(12), anchor="nw", tags=tg + ("label_x", f"lx{k}"))
            chiusa = lb.get("lucchetto", True)      # chiusa: si sposta con quello che ha dentro; aperta: da sola
            cv.create_image(x1 - 30 - 16, y0 + th / 2 - 8, image=DG.lucchetto(16, chiusa, "#f0ad4e" if chiusa else "#d7dce5"), anchor="nw",
                            tags=tg + ("label_l", f"ll{k}"))
            cv.create_image(x1 - 52 - 16, y0 + th / 2 - 8, image=segno_menu(16), anchor="nw", tags=tg + ("label_m", f"lm{k}"))
            # la nota della label (12 nov 2026): l'icona sul titolo, in alto a destra accanto al menu, piena se c'e' la nota, col + se no (Autore: «in alto a
            # destra bello visibile sui gruppi di selezione»); il riquadro sotto il titolo se e' aperta
            cv.create_image(x1 - 76 - 20, y0 + th / 2 - 10, image=segno_nota(20, bool(lb.get("nota"))), anchor="nw", tags=tg + ("nota", "label_n", f"ln{k}"))
            if lb.get("nota"):
                if lb.get("nota_aperta"):
                    self.nota_box(x0 + 8, y0 + th + 6, lb["nota"], ("label_nb", f"lb{k}"), larga=max(160, min(300, x1 - x0 - 16)))
            g = 14
            cv.create_rectangle(x1 - g, y1 - g, x1 - 1, y1 - 1, fill=FONDO_L, outline="", width=0, tags=tg + ("label_r", f"lr{k}"))
            for a in (4, 8, 12):
                cv.create_line(x1 - a, y1 - 3, x1 - 3, y1 - a, fill=SEGNO_L, width=1, tags=tg)

    def crea_etichetta(self, nome=None, colore=None):
        """Una label intorno alla selezione (pile del mazzo, dot, label), col nome e il colore del menu. Senza nome apre il menu. -> la label, o None."""
        main = [q for q in self.sel if q["zona"] == "main"]
        if not main and not self.sel_punti and not self.sel_label:
            self.dici("Select the cards first: drag a box on the empty sheet, or Ctrl+click the piles")
            return None
        if nome is None:
            self.menu_label(None)
            return None
        r = [self.ingombro(q) for q in main]
        r += [(self.punti[q]["x"] - 10, self.punti[q]["y"] - 10, self.punti[q]["x"] + 26, self.punti[q]["y"] + 10) for q in self.sel_punti if q in self.punti]
        r += [(self.etichette[k]["x"], self.etichette[k]["y"], self.etichette[k]["x"] + self.etichette[k]["w"], self.etichette[k]["y"] + self.etichette[k]["h"])
              for k in self.sel_label if k < len(self.etichette)]
        x0, y0 = min(a[0] for a in r) - PAD_L - 14, min(a[1] for a in r) - PAD_L - TIT_L
        x1, y1 = max(a[2] for a in r) + PAD_L, max(a[3] for a in r) + PAD_L
        lb = dict(nome=nome.strip() or "Label", x=round(x0), y=round(y0), w=round(x1 - x0), h=round(y1 - y0), colore=colore or GRIGIO_L, lucchetto=True,
                  id=self.nuovo_id())
        self.etichette.append(lb)
        self.sel, self.sel_punti, self.sel_label = [], set(), set()
        self.disegna()
        self.salva()
        self.dici(f"Label «{lb['nome']}»: drag its title to move it with its cards · lock: open to move it alone · ≡: name and color · ✕ removes")
        return lb

    # ------------------------------------------------ i gruppi (12 nov 2026)
    # Autore: «la possibilita' di duplicare dei gruppi - i gruppi duplicati non portano carte nel mazzo ma permettono la sostituzione veloce delle carte nel gruppo
    # duplicato e la sostituzione veloce di un gruppo di carte nuovo contro quello da cui e' stato copiato / la possibilita' di cancellare un gruppo con tutto il suo
    # contenuto in carte / la possibilita' di cancellare un gruppo vuoto dopo aver spostato fuori da esso le carte». Un gruppo e' una label. La copia tiene le sue
    # carte scritte (nome e copie), una per riga col ⇄ che la cambia; «+ Add card» ne aggiunge una; Swap mette nel mazzo le carte della copia al posto di quelle
    # del gruppo da cui viene, e la copia prende quelle di prima (un altro Swap torna indietro).
    def nuovo_id(self):
        import random
        return "g" + "".join(random.choice("0123456789abcdef") for _ in range(8))

    def nome_origine(self, lb):
        o = next((x for x in self.etichette if x.get("id") and x.get("id") == lb.get("origine")), None)
        return o["nome"] if o else "?"

    def carte_gruppo(self, k):
        """Le carte del mazzo dentro il gruppo k: {nome: copie} (solo il mazzo, non la fascia)."""
        pile, _a = self.membri(k)
        out = collections.Counter()
        for pl in pile:
            for vid in pl["carte"]:
                out[self.voci[vid]["nome"]] += self.voci[vid]["q"]
        return dict(out)

    def misura_copia(self, k):
        lb = self.etichette[k]
        righe = len(lb.get("carte") or {}) + 1
        lb["w"] = max(lb.get("w") or 0, 300)
        lb["h"] = TIT_L + 14 + righe * RIGA_COPIA + 10

    def disegna_copia(self, k, x0, y0, x1, th, fz):
        cv, F, z = self.cv, self.F, self.zoom
        lb = self.etichette[k]
        rh = RIGA_COPIA * z
        y = y0 + th + 7 * z
        for i, (nome, q) in enumerate(sorted((lb.get("carte") or {}).items())):
            if i % 2:
                cv.create_rectangle(x0 + 1, y, x1 - 1, y + rh, fill=mescola(FONDO_L, lb.get("colore") or GRIGIO_L, 0.12), width=0, tags=("label", f"l{k}"))
            cv.create_text(x0 + 12, y + rh / 2, text=f"{q}x", fill=C["accento"], font=F(max(7, round(8 * min(z, 1.6))), True), anchor="w", tags=("label", f"l{k}"))
            cv.create_text(x0 + 12 + 30 * min(z, 1.6), y + rh / 2, text=nome, fill=C["titolo"], font=F(max(7, round(9 * min(z, 1.6)))), anchor="w",
                           tags=("label", f"l{k}"))
            if not self.sola:
                cv.create_image(x1 - 8 - 16, y + rh / 2 - 8, image=segno_scambia(16), anchor="nw", tags=("label", f"l{k}", "copia_s", f"cs{k}_{i}"))
                cv.create_image(x1 - 30 - 14, y + rh / 2 - 7, image=croce(14), anchor="nw", tags=("label", f"l{k}", "copia_x", f"cx{k}_{i}"))
            y += rh
        if not self.sola:
            cv.create_text(x0 + 12, y + rh / 2, text="+ Add card", fill=C["accento"], font=F(max(7, round(8 * min(z, 1.6))), True), anchor="w",
                           tags=("label", f"l{k}", "copia_a", f"ca{k}"))
            cv.create_text(x1 - 104, y0 + th / 2, text="SWAP", fill=C["accento"], font=F(fz, True), anchor="e", tags=("label", f"l{k}", "copia_w", f"cw{k}"))

    def duplica_gruppo(self, k):
        """Una copia del gruppo k accanto (a destra): le sue carte scritte, non nel mazzo. -> la copia."""
        if not self.modifica or not 0 <= k < len(self.etichette):
            return None
        self.sfiltra()
        lb = self.etichette[k]
        carte = self.carte_gruppo(k)
        if not carte:
            self.filtra()
            self.dici(f"«{lb['nome']}» is empty: nothing to duplicate")
            return None
        if not lb.get("id"):        # l'id solo quando la copia nasce davvero: prima anche sul gruppo vuoto, un cambio fuori dallo storico (13 nov 2026, lo stress)
            lb["id"] = self.nuovo_id()
        nuova = dict(nome=lb["nome"] + " (copy)", x=round(lb["x"] + lb["w"] + 2 * SPAZIO), y=lb["y"], w=300, h=60, colore=lb.get("colore") or GRIGIO_L, lucchetto=True,
                     id=self.nuovo_id(), copia=True, carte=carte, origine=lb["id"])
        self.etichette.append(nuova)
        self.misura_copia(len(self.etichette) - 1)
        self.disegna(); self.salva()
        self.dici(f"«{nuova['nome']}»: change its cards with ⇄, then ⇄ Swap puts them in the deck instead of «{lb['nome']}»")
        return nuova

    def cambia_copia(self, k, vecchia, nuova, q=None):
        """Nella copia, la carta vecchia diventa la nuova (stesse copie); nuova None la toglie; vecchia None aggiunge la nuova (q copie, 1 di partenza)."""
        lb = self.etichette[k]
        carte = dict(lb.get("carte") or {})
        n = carte.pop(vecchia, 1) if vecchia else (q or 1)
        if nuova:
            carte[nuova] = carte.get(nuova, 0) + n if vecchia is None else max(carte.get(nuova, 0), n)
        lb["carte"] = carte
        self.misura_copia(k)
        self.disegna(); self.salva()

    def scambia_gruppo(self, k):
        """Swap: nel mazzo le carte della copia k al posto di quelle del gruppo da cui viene; la copia prende quelle di prima. -> True se fatto."""
        if not self.modifica or not 0 <= k < len(self.etichette) or not self.etichette[k].get("copia"):
            return False
        self.sfiltra()
        cp = self.etichette[k]
        ko = next((j for j, x in enumerate(self.etichette) if x.get("id") and x.get("id") == cp.get("origine")), None)
        if ko is None:
            self.filtra()
            self.dici("The original group is gone: nothing to swap with")
            return False
        vecchie, nuove = self.carte_gruppo(ko), dict(cp.get("carte") or {})
        for n, q in nuove.items():      # il limite delle copie vale per il mazzo che nasce
            if self.totale(n) - vecchie.get(n, 0) + q > self.limite(n):
                self.filtra()
                self.dici(f"{n}: max {self.limite(n)} copies, the swap would go over")
                return False
        lb = self.etichette[ko]
        pile, _a = self.membri(ko)
        for pl in pile:
            for vid in list(pl["carte"]):
                self.togli(vid)
        w, _h, _off, _p = misure(1.0)
        x, y = lb["x"] + PAD_L + 14, lb["y"] + TIT_L + PAD_L
        for i, (n, q) in enumerate(sorted(nuove.items(), key=lambda t_: t_[0])):
            gx, gy = a_griglia(x + i * PASSO_X, y)
            self.nuova_voce(n, "main", q, xy=(gx, gy))
        lb["w"] = max(lb["w"], round(len(nuove) * PASSO_X + PAD_L * 2 + 14))
        cp["carte"] = vecchie
        self.misura_copia(k)
        self.mazzo_cambiato()
        self.disegna(); self.salva()
        self.dici(f"Swapped: «{lb['nome']}» now has the cards of the copy; ⇄ Swap again to go back")
        return True

    def togli_gruppo(self, k):
        """Il gruppo e tutte le sue carte via dal mazzo (la copia: solo lei)."""
        if not self.modifica or not 0 <= k < len(self.etichette):
            return
        self.sfiltra()
        lb = self.etichette[k]
        n = 0
        if not lb.get("copia"):
            pile, _a = self.membri(k)
            for pl in pile:
                for vid in list(pl["carte"]):
                    n += self.voci[vid]["q"]
                    self.togli(vid)
        self.etichette.pop(k)
        self.sel_label = set()
        if n:
            self.mazzo_cambiato()
        self.disegna(); self.salva()
        self.dici(f"Group «{lb['nome']}» removed with its {n} cards" if n else f"Group «{lb['nome']}» removed")

    def togli_etichetta(self, k):
        if k is None or not 0 <= k < len(self.etichette):
            return
        vuota = not self.etichette[k].get("copia") and not self.membri(k)[0]
        lb = self.etichette.pop(k)
        self.sel_label = set()
        self.disegna()
        self.salva()
        self.dici(f"Empty group «{lb['nome']}» removed" if vuota else f"Label «{lb['nome']}» removed: the cards stay where they are")

    def rinomina_etichetta(self, k, nome=None):
        if k is None or not 0 <= k < len(self.etichette):
            return
        if nome is None:
            return self.chiedi_nome("Rename label", self.etichette[k]["nome"], lambda n: self.rinomina_etichetta(k, n))
        self.etichette[k]["nome"] = nome.strip() or self.etichette[k]["nome"]
        self.disegna()
        self.salva()

    def chiedi_nome(self, titolo, iniziale, fatto):
        """Una casella accanto al puntatore: Invio salva, Esc chiude."""
        tk, F = self.tk, self.F
        self.nome_chiudi()
        m = MB.Menu(tk, F, self.fin, titolo, chiudi=self.nome_chiudi)       # lo stile comune dei mini-menu (menu_board, 13 nov 2026)
        p = self._nome_pop = m.p
        var = tk.StringVar(value=iniziale)
        e = m.campo(m.riga(pady=(8, 2)), var, larga=28)

        def ok(*_a):
            n = var.get().strip()
            self.nome_chiudi()
            if n:
                fatto(n)
            return "break"
        e.bind("<Return>", ok)
        e.bind("<Escape>", lambda ev: self.nome_chiudi())
        m.pulsanti([("Save", ok, "salva"), ("Cancel", self.nome_chiudi, "secondario")])
        m.piede("Enter saves · Esc closes")
        m.posa(fuoco=e)
        e.select_range(0, "end")
        return p

    def nome_chiudi(self):
        p = getattr(self, "_nome_pop", None)
        if p is not None:
            try:
                p.destroy()
            except Exception:
                pass
        self._nome_pop = None

    def stile_apri(self, sg):
        """La tavolozza della freccia (Autore, 9 nov 2026: «possiamo dare colore e pesatura alle linee?», scelta «tutti e due tuoi»): i colori, l'importanza
        1-3 (lo spessore), Unlink. Il clic cambia subito la linea; Esc o un clic sul foglio la chiudono."""
        tk, F = self.tk, self.F
        self.stile_chiudi()
        pa, pb = self.voci[sg[0]]["nome"], self.voci[sg[1]]["nome"]
        m = MB.Menu(tk, F, self.fin, "Link", chiudi=self.stile_chiudi)      # lo stile comune dei mini-menu (menu_board, 13 nov 2026)
        p = self._stile_pop = m.p
        tk.Label(m.corpo, text=f"{pa}  →  {pb}", bg=MB.FONDO, fg="#ffffff", font=F(9, True), anchor="w").pack(fill="x", padx=12, pady=(6, 0))
        m.sezione("Color")
        cv1 = tk.Canvas(m.riga(), width=len(RS.COLORI) * 28 + 4, height=30, bg=MB.FONDO, highlightthickness=0, cursor="hand2"); cv1.pack(anchor="w")
        m.sezione("Width")
        # lo spessore della linea a slider (Autore, 10 nov 2026: «nel pallino di selezione colore metti lo slider di spessore linea»); prima tre riquadri 1-3
        v_sp = tk.DoubleVar(value=self.rete.colore_spessore(pa, pb)[1])
        L_S = len(RS.COLORI) * 28 + 4      # disegnato in antialias come le altre icone (lo Scale di Tk prendeva il colore del fondo e la manopola spariva)
        cv2 = tk.Canvas(m.riga(), width=L_S, height=26, bg=MB.FONDO, highlightthickness=0, cursor="hand2"); cv2.pack(anchor="w")
        x0s, x1s = 10, L_S - 56
        m.pulsanti([("Unlink", lambda: (self.stile_chiudi(), self.togli_arco(sg)), "pericolo")])
        m.piede("The line changes at once · Esc closes")

        def ridisegna():
            col, _w = self.rete.colore_spessore(pa, pb)
            cv1.delete("all")
            for i, (_n, hx) in enumerate(RS.COLORI):
                x = 4 + i * 28 + 12
                if hx == col:
                    cv1.create_rectangle(x - 12, 3, x + 12, 27, outline=MB.NEON, width=2)
                cv1.create_rectangle(x - 8, 7, x + 8, 23, fill=hx, outline="#ffffff" if hx == col else C["filo"], width=1)
            if "slider" in p.stile:
                p.stile["slider"](avvisa=False)

        def imposta(**kw):
            cambiate = [self.rete.imposta_stile(a, b, **kw) for a, b in self.fratelli(pa, pb)]
            if any(cambiate):
                self.disegna()
                self.salva()        # colore e spessore della linea: nello storico e da salvare, come la connessione (13 nov 2026)
            ridisegna()

        def colore(e):
            i = int((e.x - 4) // 28)
            if 0 <= i < len(RS.COLORI):
                imposta(colore=RS.COLORI[i][1])

        attesa = {"id": None}

        def scorre(_v=None):        # lo slider: la linea cambia mentre lo tiri, un disegno ogni 60 ms
            if attesa["id"] is not None:
                p.after_cancel(attesa["id"])
            attesa["id"] = p.after(60, lambda: (attesa.update(id=None), imposta(spessore=round(float(v_sp.get()), 1))))

        def slider(v=None, avvisa=True):
            """Il binario, la parte accesa nel colore della linea, la manopola bianca, il valore in pixel."""
            if v is not None:
                v_sp.set(round(max(RS.SPESSORE_MIN, min(RS.SPESSORE_MAX, v)), 1))
            v = float(v_sp.get())
            xk = x0s + (v - RS.SPESSORE_MIN) / (RS.SPESSORE_MAX - RS.SPESSORE_MIN) * (x1s - x0s)
            col = self.rete.colore_spessore(pa, pb)[0]
            cv2.delete("all")
            cv2._img = DG.tratti(L_S, 26, linee=[([(x0s, 13), (x1s, 13)], C["filo"], 4, None), ([(x0s, 13), (xk, 13)], col, 4, None)],
                                 punti=[(xk, 13, 7, "#ffffff", C["accento"], 1.5)])
            cv2.create_image(0, 0, image=cv2._img, anchor="nw")
            cv2.create_text(L_S - 4, 13, text=f"{v:.1f} px", fill=C["titolo"], font=F(8, True), anchor="e")
            if avvisa:
                scorre()

        def da_x(ev):
            slider(RS.SPESSORE_MIN + max(0.0, min(1.0, (ev.x - x0s) / (x1s - x0s))) * (RS.SPESSORE_MAX - RS.SPESSORE_MIN))
        cv1.bind("<Button-1>", colore)
        cv2.bind("<Button-1>", da_x)
        cv2.bind("<B1-Motion>", da_x)
        p.stile = dict(imposta=imposta, coppia=(pa, pb), slider=slider)      # per le prove
        ridisegna()
        m.posa()
        return p

    def stile_chiudi(self):
        p = getattr(self, "_stile_pop", None)
        if p is not None:
            try:
                p.destroy()
            except Exception:
                pass
        self._stile_pop = None

    # ------------------------------------------------ i dot delle linee, come in Nuke: piu' ingressi, piu' uscite
    def ingressi(self, q):
        return [tuple(x) for x in self.punti[q].get("ingressi", [])]

    def fonti(self, q, visti=None):
        """Le carte da cui arriva il segnale al dot: gli ingressi carta, e le fonti dei dot in ingresso."""
        visti = visti if visti is not None else set()
        if q in visti or q not in self.punti:
            return set()
        visti.add(q)
        out = set()
        for k, v in self.ingressi(q):
            if k == "c":
                out.add(v)
            else:
                out |= self.fonti(v, visti)
        return out

    def sotto_punto(self, q):
        """I dot a valle di q, q compreso: quelli che ricevono da q, anche passando da altri dot."""
        out, cambia = {q}, True
        while cambia:
            cambia = False
            for r in self.punti:
                if r not in out and any(k == "p" and v in out for k, v in self.ingressi(r)):
                    out.add(r)
                    cambia = True
        return list(out)

    def fratelli(self, a, b):
        """Le connessioni che si disegnano nello stesso pezzo di a -> b: se passa da un dot, tutte quelle verso b che passano di li'."""
        q = self.vie.get((a, b))
        if q not in self.punti:
            return [(a, b)]
        return [(s_, c_) for (s_, c_), r in self.vie.items() if r == q and c_ == b and (s_, c_) in self.rete.figli] or [(a, b)]

    def linea_a(self, x, y, raggio=7):
        """Il pezzo di linea piu' vicino al punto: ("link", segmento) un pezzo con la punta, ("tronco", (dot, a, b, ingresso)) l'ingresso di un dot, o None."""
        meglio, dmin = None, raggio
        for sg in self._segmenti:
            dd = self.distanza((x, y), sg[2], sg[3])
            if dd <= dmin:
                meglio, dmin = ("link", sg), dd
        for tr in self._tronchi:
            dd = self.distanza((x, y), tr[1], tr[2])
            if dd <= dmin:
                meglio, dmin = ("tronco", tr), dd
        return meglio

    def inserisci_punto(self, x, y, hit=None):
        """Il chiodo o il doppio clic su una linea la spezza con un dot in quel punto. Su un pezzo con la punta il dot va prima del figlio (con tutte le connessioni
        di quel pezzo); sull'ingresso di un dot, fra l'ingresso e il dot. -> l'id del dot, o None."""
        hit = hit or self.linea_a(x, y)
        if hit is None:
            return None
        q = max(self.punti, default=0) + 1
        fx, fy = x / self.zoom, (y - self.oy("main")) / self.zoom
        if hit[0] == "link":
            a, b = self.voci[hit[1][0]]["nome"], self.voci[hit[1][1]]["nome"]
            prima = self.vie.get((a, b))
            if prima in self.punti and a in self.fonti(prima):
                self.punti[q] = dict(x=fx, y=fy, ingressi=[["p", prima]])
                for k in self.fratelli(a, b):
                    self.vie[k] = q
            else:
                self.punti[q] = dict(x=fx, y=fy, ingressi=[["c", a]])
                self.vie[(a, b)] = q
        else:
            dopo, ing = hit[1][0], list(hit[1][3])
            self.punti[q] = dict(x=fx, y=fy, ingressi=[ing])
            self.punti[dopo]["ingressi"] = [["p", q] if [k, v] == ing else [k, v] for k, v in self.ingressi(dopo)]
        self.disegna()
        self.salva()
        self.dici("Dot added: drag it to move · from its gold dot a new line · drop more lines on it (more inputs) · right-click removes it")
        return q

    def togli_punto(self, q):
        """Il tasto destro sul dot: via il dot, i suoi ingressi vanno ai dot dopo, e le connessioni che passavano di li' vanno al dot in ingresso che porta il loro
        padre, o dritte."""
        p_ = self.punti.pop(q, None)
        if p_ is None:
            return
        ing = [list(x) for x in p_.get("ingressi", [])]
        for r in self.punti.values():
            nuovi = []
            for k, v in r.get("ingressi", []):
                for x in (ing if (k == "p" and v == q) else [[k, v]]):
                    if x not in nuovi:
                        nuovi.append(x)
            r["ingressi"] = nuovi
        for (a, b), v in list(self.vie.items()):
            if v == q:
                via = next((x[1] for x in ing if x[0] == "p" and x[1] in self.punti and a in self.fonti(x[1])), None)
                if via is not None:
                    self.vie[(a, b)] = via
                else:
                    del self.vie[(a, b)]
        self.sel_punti.discard(q)
        self.disegna()
        self.salva()
        self.dici("Dot removed: the lines go straight")

    def togli_ingresso(self, q, ing):
        """La ✕ sull'ingresso di un dot (o il tasto destro): via quell'ingresso, e le connessioni che arrivavano solo da li' (il padre non arriva piu' al dot da
        nessuna parte). Un dot rimasto senza ingressi sparisce."""
        if q not in self.punti:
            return
        self.punti[q]["ingressi"] = [[k, v] for k, v in self.ingressi(q) if (k, v) != tuple(ing)]
        for (a, b), r in list(self.vie.items()):
            if r in self.punti and a not in self.fonti(r):
                del self.vie[(a, b)]
                if (a, b) in self.rete.figli:
                    self.rete.lega(a, b, self.carte_db)
        vuoti = [r for r in self.punti if not self.punti[r].get("ingressi")]
        while vuoti:
            r = vuoti.pop()
            self.punti.pop(r, None)
            for x in self.punti.values():
                x["ingressi"] = [[k, v] for k, v in x.get("ingressi", []) if not (k == "p" and v == r)]
            vuoti += [x for x in self.punti if not self.punti[x].get("ingressi") and x not in vuoti]
            for k_, v_ in list(self.vie.items()):
                if v_ not in self.punti:
                    del self.vie[k_]
        self.disegna()
        self.salva()
        self.dici("Input removed from the dot")

    def via_tolta(self, a, b):
        """La connessione a -> b non c'e' piu': via la sua strada, e i dot che non servono piu' a nessuno (niente connessioni, niente dot dopo), risalendo."""
        q = self.vie.pop((a, b), None)
        coda = [q] if q is not None else []
        while coda:
            q = coda.pop()
            if q not in self.punti or q in self.vie.values() or any(k == "p" and v == q for r in self.punti.values() for k, v in r.get("ingressi", [])):
                continue
            p_ = self.punti.pop(q)
            coda += [v for k, v in p_.get("ingressi", []) if k == "p"]

    def punto_inizio(self, q, cx, cy, tira=False):
        """Premuto un dot: si trascina (con le linee che passano di li'); dal suo pallino d'oro (o con Maiuscolo) parte una linea nuova."""
        if tira:
            self.drag = None
            x, y = self.uscita_xy(q)
            self.tira = dict(da=None, punto=q, x=x, y=y, mosso=False, imparati=[])
            return
        self.drag = dict(prese=[], da=None, x0=cx, y0=cy, x=cx, y=cy, mosso=False, vid=None, x_presa=0, y_presa=0, gruppo=[], etichette=[], punti=[q])

    def punto_a(self, x, y):
        """Il dot sotto il punto (fuori dalle carte), o None."""
        sopra = self.pezzo_a(x, y)
        return sopra[1] if sopra[0] in ("punto", "punto_out") and sopra[1] in self.punti else None

    def ingresso_possibile(self, q, t):
        """Una linea tirata puo' entrare nel dot q? Non dal dot stesso, non da un dot a valle (sarebbe un giro chiuso), non due volte la stessa."""
        p = t.get("punto")
        if p is not None:
            return p != q and p not in self.sotto_punto(q) and ("p", p) not in self.ingressi(q)
        return ("c", t["da"]) not in self.ingressi(q)

    def ricevi_punto(self, q, t):
        """Il dot riceve una linea, da una carta o da un altro dot: un ingresso in piu' (Autore, 10 nov 2026: «i nodi devono poter ricevere piu' frecce»).
        Tutto quello che esce dal dot e dai dot dopo vale anche per il padre nuovo: le connessioni padre nuovo -> figlio nascono (col colore e l'importanza di quelle
        che c'erano). Quella della carta con se stessa no. -> True se e' cambiato."""
        if not self.ingresso_possibile(q, t):
            self.dici("A dot can't take the same input twice, nor an input from itself or from a dot after it")
            return False
        p = t.get("punto")
        ing = ["p", p] if p is not None else ["c", t["da"]]
        self.punti[q].setdefault("ingressi", []).append(ing)
        nuove = self.fonti(p) if p is not None else {t["da"]}
        sotto = set(self.sotto_punto(q))
        uscite = {}
        for (a, c), r in self.vie.items():
            if r in sotto and (a, c) in self.rete.figli:
                uscite.setdefault((c, r), (a, c))
        fatte = 0
        for (c, r), vecchia in uscite.items():
            st = self.rete.stili.get(vecchia)
            for n in nuove:
                if n == c:
                    continue
                if (n, c) not in self.rete.figli:
                    self.rete.lega(n, c, self.carte_db)
                    fatte += 1
                if st:
                    self.rete.imposta_stile(n, c, colore=st.get("colore"), peso=st.get("peso"), spessore=st.get("spessore"))
                self.vie[(n, c)] = r
        self.disegna()
        self.salva()
        chi = t["da"] if p is None else "a dot"
        self.dici(f"Dot input added: {chi}" + (f" · {fatte} new link{'s' if fatte != 1 else ''}" if fatte else ""))
        return True

    def tira_fine_punto(self, t, x, y):
        """La linea tirata da un dot: su una carta, la connessione di ogni padre del dot verso quella carta passa dal dot (rifatta quando ci sono gia' tutte, si
        tolgono); nel vuoto, un dot nuovo dopo questo (una catena, come in Nuke)."""
        q = t["punto"]
        vb = self.carta_a(x, y)
        if vb is None:
            n = max(self.punti, default=0) + 1
            self.punti[n] = dict(x=x / self.zoom, y=(y - self.oy("main")) / self.zoom, ingressi=[["p", q]])
            self.dici("New dot: drag from its gold dot to a card to link")
        else:
            b = self.voci[vb]["nome"]
            padri = sorted(self.fonti(q) - {b})
            if not padri:
                return
            if all((a, b) in self.rete.figli and self.vie.get((a, b)) == q for a in padri):
                for a in padri:
                    self.rete.lega(a, b, self.carte_db)
                    self.via_tolta(a, b)
                self.dici(f"dot → {b}: unlinked")
            else:
                for a in padri:
                    if (a, b) not in self.rete.figli:
                        self.rete.lega(a, b, self.carte_db)
                    self.vie[(a, b)] = q
                self.dici(f"{', '.join(padri)} → {b}: linked through the dot")
        self.disegna()
        self.salva()

    def esc(self):
        """Esc: chiude prima la tavolozza o la casella del nome, poi scioglie la selezione, e solo allora chiude il tavolo."""
        if self._stile_pop is not None or self._nome_pop is not None:
            self.stile_chiudi(); self.nome_chiudi()
            return
        if self.sel or self.sel_punti or self.sel_label:
            self.vuota_sel()
            return
        self.chiudi()

    def chiudi(self, chiedi=True, poi=None):
        """Chiude il Board. In modalita' edit con modifiche non salvate prima chiede: Save, Don't save (il mazzo torna com'era all'ultimo Save), Cancel."""
        if chiedi and self.da_salvare:
            from widget import conferma

            def non_salvare():
                if self.storia and 0 <= self.salvato_a < len(self.storia):
                    self.ripristina(self.storia[self.salvato_a])
                self.chiudi(chiedi=False, poi=poi)
            self.domanda = conferma(self.tk, self.F, self.fin, "Save the changes?", f"You changed «{self.nome}» on the board and did not save.", "Save",
                                    lambda: (self.salva_tutto(), self.chiudi(chiedi=False, poi=poi)), colori=VERDE_P,
                                    altro=("Don't save", non_salvare))
            return False
        self.scambia_chiudi()
        self.stile_chiudi()
        self.nome_chiudi()
        self.nascondi()
        if not self.modifica:
            self.scrivi()
        try:
            self.fin.destroy()
        except Exception:
            pass
        if poi is not None:
            poi()
        if self.cambiato and self.alla_fine:       # il mazzo e' cambiato: la sua scheda si rifa'
            self.alla_fine()


def tutti_widget(w):
    yield w
    for x in w.winfo_children():
        yield from tutti_widget(x)


def prova():
    """Fuori schermo, file temporanei: le pile, il numero delle copie, il contatore coi limiti, la pila che si apre, il trascinamento, l'impilare, il passaggio di zona,
    il salvataggio del mazzo e della disposizione, la ripresa. Con le negative."""
    import tempfile
    import tkinter as tk
    d = tempfile.mkdtemp()
    ft, fm = os.path.join(d, "tavoli.json"), os.path.join(d, "mazzi.json")
    # mai i file di Autore (13 nov 2026: i Board di prova senza file_rete salvavano la loro rete vuota in Log_Arena/sinergie_mazzi.json, 18 voci «build:...»
    # in sei giri, e riscrivevano sinergie_imparate.json): la rete, l'imparato e le disposizioni di default vanno nella cartella della prova
    vero_ = (RS.FILE, RS.IMPARATE, globals()["FILE"])
    RS.FILE, RS.IMPARATE, globals()["FILE"] = os.path.join(d, "rete_tutte.json"), os.path.join(d, "imparate_tutte.json"), os.path.join(d, "tavoli_tutti.json")
    impronta_vera = lambda: [(os.path.getmtime(f_), os.path.getsize(f_)) if os.path.exists(f_) else None for f_ in vero_]
    veri_prima = impronta_vera()
    m = MS.aggiungi("build", dict(nome="Prova", lista={"Lightning Bolt": 4, "Shock": 2, "Opt": 1, "Mountain": 14}, side={"Abrade": 2}), f=fm)
    db = {"Lightning Bolt": dict(cmc=1, tipo="Instant"), "Shock": dict(cmc=1, tipo="Instant"), "Opt": dict(cmc=1, tipo="Instant"),
          "Mountain": dict(cmc=0, tipo="Basic Land — Mountain"), "Abrade": dict(cmc=2, tipo="Instant")}
    lim = lambda n: 10 ** 6 if n in MS.BASI else 4
    root = tk.Tk(); root.withdraw()
    F = lambda n, b=False: ("Poppins Medium" if b else "Poppins", n)
    casi = []
    cambi = []
    t = TavoloCarte(tk, F, root, "Prova", m["lista"], m["side"], carte_db=db, chiave="build:" + m["id"], modificabile=("build", m["id"]),
                    al_cambio=lambda a, b: cambi.append((a, b)), file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    casi.append(("Grid snap: la spunta in alto, accesa di partenza", t.griglia is True and t.b_griglia.cget("text").strip() == "Grid snap"))
    t.griglia = False       # le prove qui sotto lasciano le carte in punti esatti: la griglia ha le sue prove piu' avanti
    voce = lambda n, z="main": next((i for i, v in t.voci.items() if v["nome"] == n and v["zona"] == z), None)
    casi.append(("una carta per nome, non per copia", len(t.voci) == 5 and t.voci[voce("Mountain")]["q"] == 14))
    zone = collections.Counter(pl["zona"] for pl in t.pile)
    casi.append(("le pile: il mazzo per costo, la sideboard una per carta", zone["side"] == 1 and zone["main"] == 2))
    testi = [t.cv.itemcget(i, "text") for i in t.cv.find_all() if t.cv.type(i) == "text"]
    casi.append(("accanto al nome il numero delle copie, su ogni carta", testi.count("4x") == 1 and testi.count("14x") == 1 and testi.count("2x") == 2 and testi.count("1x") == 1))
    # il contatore: fino a 4, contando la sideboard; a 0 la carta esce
    bolt, shock = voce("Lightning Bolt"), voce("Shock")
    casi.append(("al limite il + non aggiunge", not t.cambia_copie(bolt, +1) and t.voci[bolt]["q"] == 4))
    t.cambia_copie(shock, +1)
    sal_prima = next(x for x in MS.carica(fm)["build"] if x["id"] == m["id"])["lista"]["Shock"]
    t.salva_tutto()
    casi.append(("niente salvataggio automatico: prima di Save il file ha ancora le copie di prima (12 nov 2026)", sal_prima == 2))
    casi.append(("il + aggiunge una copia e col Save il mazzo salvato cambia", t.voci[shock]["q"] == 3 and next(x for x in MS.carica(fm)["build"] if x["id"] == m["id"])["lista"]["Shock"] == 3 and cambi))
    abr = voce("Abrade", "side")
    t.cambia_copie(abr, +1); t.cambia_copie(abr, +1)
    casi.append(("il limite conta mazzo e sideboard insieme", t.voci[abr]["q"] == 4 and not t.cambia_copie(abr, +1)))
    opt = voce("Opt")
    t.cambia_copie(opt, -1); t.salva_tutto()
    sal = next(x for x in MS.carica(fm)["build"] if x["id"] == m["id"])
    casi.append(("a 0 la carta esce dal mazzo e dal tavolo", opt not in t.voci and "Opt" not in sal["lista"]))
    # la pila che si apre: la carta in mezzo intera, le altre scendono
    pila = t.pila_di(bolt)
    if len(pila["carte"]) < 2:
        casi.append(("pila di prova con due carte", False))
    else:
        primo = pila["carte"][0]
        prima = t.posizioni(pila)
        t.apri_pila(primo)
        dopo = t.posizioni(pila)
        _w, h, off, _p = misure(1.0)
        casi.append(("il clic in mezzo apre la pila: la carta dopo scende di una carta intera", pila["aperta"] == primo and dopo[1] - dopo[0] == h + APERTA and prima[1] - prima[0] == off))
        cnt = [i for i in t.cv.find_withtag(f"meno{primo}")]
        casi.append(("la carta aperta ha il suo contatore", bool(cnt)))
        t.apri_pila(primo)
        casi.append(("un altro clic la richiude", pila["aperta"] is None))

    def trascina(cid, verso_pila=None, xy=None, shift=False):
        bb = t.cv.bbox(f"c{cid}")
        x0, y0 = bb[0] + 30, bb[1] + 12
        orig = t.sotto_al_mouse
        t.sotto_al_mouse = lambda: cid
        t.premi(type("E", (), dict(x=x0, y=y0, state=1 if shift else 0))())
        t.sotto_al_mouse = orig
        if verso_pila is not None:
            x1, y1, _a, _b = t.ingombro_px(verso_pila)
            dest = (x1 + 30, y1 + 30)
        else:
            dest = xy
        t.trascina(type("E", (), dict(x=(x0 + dest[0]) / 2, y=(y0 + dest[1]) / 2))())
        t.trascina(type("E", (), dict(x=dest[0], y=dest[1]))())
        t.rilascia(type("E", (), dict(x=dest[0], y=dest[1]))())
        root.update()

    mont = t.pila_di(voce("Mountain"))
    n_prima = len(mont["carte"])
    n_cambi = len(cambi)
    trascina(bolt, verso_pila=mont)
    casi.append(("lasciata su una pila si impila sopra, con tutte le copie", mont["carte"][-1] == bolt and len(mont["carte"]) == n_prima + 1 and t.voci[bolt]["q"] == 4))
    casi.append(("dentro il mazzo la lista non cambia", len(cambi) == n_cambi))
    # nella fascia: tutte le copie vanno in sideboard; il doppio clic ne riporta una
    trascina(shock, xy=(900, 60)); t.salva_tutto()
    sal = next(x for x in MS.carica(fm)["build"] if x["id"] == m["id"])
    casi.append(("nella fascia tutte le copie diventano sideboard", t.voci[shock]["zona"] == "side" and "Shock" not in sal["lista"] and sal["side"].get("Shock") == 3))
    orig = t.sotto_al_mouse
    t.sotto_al_mouse = lambda: shock
    t.doppio(None)
    t.sotto_al_mouse = orig
    t.salva_tutto()
    sal = next(x for x in MS.carica(fm)["build"] if x["id"] == m["id"])
    casi.append(("il doppio clic passa UNA copia nel mazzo", sal["lista"].get("Shock") == 1 and sal["side"].get("Shock") == 2 and t.voci[shock]["q"] == 2))
    # riportata nel mazzo dove c'e' gia' la stessa carta: le copie si sommano, una carta per nome e zona
    trascina(shock, xy=(600, t.oy("main") + 400))
    sh_main = [v for v in t.voci.values() if v["nome"] == "Shock" and v["zona"] == "main"]
    casi.append(("nella stessa zona le copie si sommano su una carta sola", len(sh_main) == 1 and sh_main[0]["q"] == 3 and not any(v["nome"] == "Shock" and v["zona"] == "side" for v in t.voci.values())))
    # Maiuscolo: tutta la pila
    pila_m = t.pila_di(voce("Mountain"))
    quante = len(pila_m["carte"])
    trascina(pila_m["carte"][0], xy=(1100, t.oy("main") + 300), shift=True)
    casi.append(("con Maiuscolo si sposta tutta la pila", any(len(pl["carte"]) == quante and pl["x"] > 900 for pl in t.pile)))
    # libera, e lo snap solo sopra un'altra pila: lasciata a 40 pixel da una pila resta da sola, dove l'hai lasciata
    import time as _t

    def aspetta(sec=0.25):
        fine_ = _t.time() + sec
        while _t.time() < fine_:
            root.update(); _t.sleep(0.02)
    mont = t.pila_di(voce("Mountain"))
    bx0, by0, bx1, by1 = t.ingombro_px(mont)
    ab = voce("Abrade", "side")
    trascina(ab, xy=(bx1 + 70, by0 + 20))
    pa = t.pila_di(ab)
    casi.append(("libera: vicino a una pila ma fuori resta da sola, dove l'hai lasciata", pa is not mont and len(pa["carte"]) == 1 and pa["zona"] == "main"
                 and abs(t.pos_px(pa)[0] - (bx1 + 70 - 30)) <= 16))      # presa a 30 pixel dal bordo della figura, che col numero sporge a sinistra
    trascina(ab, verso_pila=mont)
    casi.append(("snap: lasciata sopra la pila si impila", t.pila_di(ab) is mont))
    trascina(ab, xy=(bx1 + 300, by1 + 200))
    casi.append(("de-snap: tirata fuori dalla pila se ne stacca", t.pila_di(ab) is not mont and len(t.pila_di(ab)["carte"]) == 1 and ab not in mont["carte"]))
    # lo zoom: le carte del mazzo piu' grandi, le posizioni salvate (scala 1) uguali
    vb = t.pila_di(voce("Lightning Bolt"))["carte"][-1]
    largo = lambda vid: (lambda b: b[2] - b[0])(t.cv.bbox(t.cv.find_withtag(f"c{vid}")[0]))      # l'immagine della carta (il contatore ha una misura fissa)
    w0, base0 = largo(vb), [(pl["x"], pl["y"]) for pl in t.pile]
    t.zoom_a(1.5); aspetta()
    casi.append(("lo zoom ingrandisce il foglio, non cambia la disposizione", t.zoom == 1.5 and largo(vb) > w0 * 1.35 and [(pl["x"], pl["y"]) for pl in t.pile] == base0))
    z0 = t.zoom
    W_ = lambda d: type("E", (), dict(delta=d, x=300, y=400, state=0))()
    t.rotella(W_(120)); aspetta()
    casi.append(("la rotella zooma", t.zoom > z0))
    t.rotella(W_(-120)); aspetta()
    casi.append(("la rotella indietro torna", abs(t.zoom - z0) <= 0.05))
    # il punto sotto il puntatore resta fermo, anche dopo piu' scatti di fila e il ridisegno finale
    fermo = lambda: (t.cv.canvasx(300) / t.zoom, (t.cv.canvasy(400) - t.oy("main")) / t.zoom)
    f0 = fermo()
    nf = len(_FOTO)
    t.rotella(W_(120)); t.rotella(W_(120)); t.rotella(W_(120))
    if t.gpu:
        casi.append(("sulla scheda lo zoom e' subito: niente ridisegno allo scatto", t.cv.zk > 1.2 and t._zoom_dopo is not None))
    aspetta(0.4)
    f1 = fermo()
    casi.append(("lo zoom tiene fermo il punto sotto il puntatore", abs(f1[0] - f0[0]) < 2 and abs(f1[1] - f0[1]) < 2))
    if t.gpu:
        casi.append(("sulla scheda lo zoom non rifa' le immagini delle carte, e il ridisegno azzera lo zoom immediato", len(_FOTO) == nf and t.cv.zk == 1.0))
    t.rotella(W_(-120)); t.rotella(W_(-120)); t.rotella(W_(-120)); aspetta(0.4)
    t.cv.xview_moveto(0); t.cv.yview_moveto(0); root.update()
    t.pan_inizio(type("E", (), dict(x=500, y=500))()); t.pan_muovi(type("E", (), dict(x=380, y=420))()); t.pan_fine(None); root.update()
    casi.append(("il tasto centrale sposta il foglio", t.cv.canvasx(0) > 0 and t.cv.canvasy(0) > 0 and [(pl["x"], pl["y"]) for pl in t.pile] == base0))
    t.cv.xview_moveto(0); t.cv.yview_moveto(0); root.update()
    t.pan_inizio(type("E", (), dict(x=300, y=300))()); t.pan_muovi(type("E", (), dict(x=2300, y=2300))()); t.pan_fine(None); root.update()
    casi.append(("il pan non ha bordi: oltre l'inizio del foglio, a sinistra e sopra", t.cv.canvasx(0) < -1500 and t.cv.canvasy(0) < -1500))
    t.cv.xview_moveto(0); t.cv.yview_moveto(0); root.update()
    t.zoom_a(9); aspetta()
    casi.append(("lo zoom ha un tetto", t.zoom == ZOOM_MAX))
    misura_ctrl = lambda: sorted({(lambda b_: (round(b_[2] - b_[0]), round(b_[3] - b_[1])))(t.cv.bbox(i_)) for i_ in t.cv.find_withtag("ctrl")})
    t.zoom = ZOOM_MAX; t.disegna(); grandi_ = misura_ctrl()
    t.zoom = 1.0; t.disegna()
    uguali_ = lambda a_, b_: bool(a_) and all(abs(p_[0] - q_[0]) <= 1 and abs(p_[1] - q_[1]) <= 1 for p_ in a_ for q_ in b_)      # un pixel: l'arrotondamento
    casi.append(("i pulsanti − + interi hanno la stessa misura quando la carta e' grande", uguali_(grandi_, misura_ctrl())))

    def ctrl_dentro():
        """Ogni − e + dentro la carta di cui e' (13 nov 2026: «sistema i contatori che coprono le carte»)."""
        ok_ = []
        for i_ in t.cv.find_withtag("ctrl"):
            vid_ = next((int(g_[1:]) for g_ in t.cv.gettags(i_) if g_[0] == "c" and g_[1:].isdigit()), None)
            r_, b_ = t.rett(vid_), t.cv.bbox(i_)
            ok_.append(r_ is not None and b_[0] >= r_[0] - 1 and b_[2] <= r_[2] + 1 and b_[1] >= r_[1] - 1 and b_[3] <= r_[3] + 1)
        return bool(ok_) and all(ok_)
    t.zoom = 0.5; t.disegna()
    dentro_05 = ctrl_dentro()
    t.zoom = ZOOM_MIN; t.disegna()
    dentro_03 = ctrl_dentro()
    casi.append(("a zoom basso (50%, 30%) − e + stanno dentro la loro carta: non coprono le carte accanto", dentro_05 and dentro_03))
    t.zoom = 0.2; t.disegna()
    casi.append(("negativa: sotto i 40 pixel di carta niente contatore (ci si avvicina per cambiare le copie)", not t.cv.find_withtag("ctrl")))
    t.zoom = 1.0; t.disegna()
    t.zoom_a(1.25); aspetta()
    # la fascia: la barra si trascina, le carte della sideboard si rimpiccioliscono fino a sparire
    trascina(ab, xy=(500, 60))      # Abrade torna in sideboard
    sb = ab
    ws = largo(sb)
    # la fascia sta in cima alla finestra (12 nov 2026): la barra e' a hs sotto l'inizio della vista, non a hs sulla tela
    E = lambda x, y: type("E", (), dict(x=x - t.cv.canvasx(0), y=y - t.cv.canvasy(0), state=0))()
    fy_ = lambda: t._fy
    t.premi_tela(E(400, fy_() + t.hs)); t.trascina(E(400, fy_() + t.hs - 110)); t.rilascia(E(400, fy_() + t.hs - 110)); root.update()
    casi.append(("la barra trascinata abbassa la fascia", t.hs == FASCIA_DEF - 110 and t.cv.find_withtag("barra")))
    casi.append(("fascia piu' bassa: le carte della sideboard piu' piccole", t.cv.bbox(f"c{sb}") and largo(sb) < ws * 0.7))
    casi.append(("e il mazzo sale con la barra", t.oy("main") == t.hs + ETICHETTA))
    t.premi_tela(E(400, fy_() + t.hs)); t.trascina(E(400, fy_() - 50)); t.rilascia(E(400, fy_() - 50)); root.update()
    casi.append(("fascia a zero: le carte della sideboard spariscono", t.hs == 0 and t.nascosta() and not t.cv.find_withtag(f"c{sb}")))
    t.premi_tela(E(400, fy_() + 300)); t.rilascia(E(400, fy_() + 300))
    casi.append(("negativa: premuta lontano dalla barra la fascia non si muove", t.hs == 0))
    t.premi_tela(E(400, fy_() + t.hs)); t.trascina(E(400, fy_() + 140)); t.rilascia(E(400, fy_() + 140)); root.update()
    pos = [(pl["zona"], pl["x"], pl["y"], [t.voci[c]["q"] for c in pl["carte"]]) for pl in t.pile]
    posti = {n: next(((pl["x"], pl["y"]) for pl in t.pile for c in pl["carte"] if t.voci[c]["nome"] == n), None) for n in ("Mountain", "Shock")}
    t.salva_tutto(); t.chiudi()
    sal = next(x for x in MS.carica(fm)["build"] if x["id"] == m["id"])
    t2 = TavoloCarte(tk, F, root, "Prova", sal["lista"], sal["side"], carte_db=db, chiave="build:" + m["id"], modificabile=("build", m["id"]), file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    casi.append(("riaperto: la stessa disposizione, lo stesso zoom e la stessa fascia", [(pl["zona"], pl["x"], pl["y"], [t2.voci[c]["q"] for c in pl["carte"]]) for pl in t2.pile] == pos
                 and t2.zoom == 1.25 and t2.hs == 140))
    t2.salva_tutto(); t2.chiudi()
    # la disposizione resta anche se il mazzo e' cambiato da fuori: le carte che ci sono tornano al loro posto con le copie di adesso, la nuova va sulla sua pila
    db["Opt"] = dict(cmc=1, tipo="Instant")
    t3 = TavoloCarte(tk, F, root, "Prova", dict(sal["lista"], **{"Lightning Bolt": 3, "Opt": 2}), sal["side"], carte_db=db, chiave="build:" + m["id"],
                     modificabile=("build", m["id"]), file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    dove = lambda t_, n: next(((pl["x"], pl["y"]) for pl in t_.pile for c in pl["carte"] if t_.voci[c]["nome"] == n), None)
    casi.append(("mazzo cambiato da fuori: le carte restano dove le avevi messe, con le copie di adesso",
                 t3.zoom == 1.25 and t3.hs == 140 and t3.voci[next(i for i, v in t3.voci.items() if v["nome"] == "Lightning Bolt")]["q"] == 3
                 and dove(t3, "Mountain") == posti["Mountain"] and dove(t3, "Shock") == posti["Shock"]))
    casi.append(("e la carta nuova entra", any(v["nome"] == "Opt" and v["q"] == 2 for v in t3.voci.values())))
    t3.salva_tutto(); t3.chiudi()
    # il builder legge la disposizione di prima, salvata sotto «builder:<id>», se sotto la chiave del mazzo non c'e'
    d_ = carica_tavoli(ft)
    salva_tavolo("builder:vecchio", d_["build:" + m["id"]], ft)
    tb = TavoloCarte(tk, F, root, "Prova", dict(sal["lista"], **{"Lightning Bolt": 3, "Opt": 2}), sal["side"], carte_db=db, chiave="build:nuovo",
                     chiave_vecchia="builder:vecchio", editore=lambda a_, b_: None, file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    casi.append(("il builder riprende la disposizione che teneva a parte", dove(tb, "Mountain") == posti["Mountain"] and tb.zoom == 1.25))
    tb.chiave = None; tb.salva_tutto(); tb.chiudi()
    tn = TavoloCarte(tk, F, root, "Prova", {"Shock": 2}, {}, carte_db=db, chiave=None, editore=lambda a_, b_: None, file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    tn.nuova_chiave("build:appena"); tn.scrivi_tutto()
    casi.append(("un mazzo nuovo del builder, al primo Save, salva la disposizione sotto la sua chiave", "build:appena" in carica_tavoli(ft)))
    tn.salva_tutto(); tn.chiudi()
    # un mazzo di Arena: niente contatore, si sposta sul tavolo, il file dei mazzi non si tocca
    prima_file = open(fm, encoding="utf-8").read()
    t4 = TavoloCarte(tk, F, root, "Arena", {"Lightning Bolt": 4, "Mountain": 16}, {"Abrade": 1}, carte_db=db, chiave="mio:arena", file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    t = t4
    b4 = next(i for i, v in t4.voci.items() if v["nome"] == "Lightning Bolt")
    casi.append(("un mazzo di Arena non ha il contatore", not t4.cv.find_withtag("ctrl") and not t4.cambia_copie(b4, -1)))
    casi.append(("negativa: un mazzo di Arena non ha il ⇄ e non si sostituisce", not t4.cv.find_withtag("scambia") and not t4.scambia(b4, "Shock")))
    trascina(b4, xy=(700, 60))
    casi.append(("e la carta va in fascia ma i mazzi salvati non cambiano", t4.voci[b4]["zona"] == "side" and open(fm, encoding="utf-8").read() == prima_file))
    t4.salva_tutto(); t4.chiudi()
    t5 = TavoloCarte(tk, F, root, "Arena", {"Lightning Bolt": 4, "Mountain": 16}, {"Abrade": 1}, carte_db=db, chiave="mio:arena", file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    casi.append(("alla riapertura resta la sua disposizione", any(v["nome"] == "Lightning Bolt" and v["zona"] == "side" and v["q"] == 4 for v in t5.voci.values())))
    t5.salva_tutto(); t5.chiudi()
    _w, h1, off1, _p = misure(1.0)
    vecchio = 2 * ETICHETTA + h1 + 2 * off1 + 28
    salva_tavolo("mio:vecchio", dict(taglia="L", pile=[dict(zona="side", x=22, y=ETICHETTA, carte=[["Abrade", 1]]), dict(zona="main", x=22, y=vecchio, carte=[["Mountain", 16]]),
                                                       dict(zona="main", x=190, y=vecchio + 100, carte=[["Lightning Bolt", 4]])]), ft)
    tv = TavoloCarte(tk, F, root, "Arena", {"Lightning Bolt": 4, "Mountain": 16}, {"Abrade": 1}, carte_db=db, chiave="mio:vecchio", file_tavoli=ft, file_mazzi=fm, fuori=True, limite=lim)
    root.update()
    casi.append(("una disposizione del primo giro: zoom da L, il mazzo dall'inizio del foglio", tv.zoom == 1.25 and sorted(pl["y"] for pl in tv.pile if pl["zona"] == "main") == [0, 100]
                 and all(pl["y"] == 0 for pl in tv.pile if pl["zona"] == "side")))
    tv.salva_tutto(); tv.chiudi()
    t6 = TavoloCarte(tk, F, root, "Brawl", {"Mountain": 10}, {}, comandante={"Lightning Bolt": 1}, carte_db=db, chiave=None, file_tavoli=ft, file_mazzi=fm, fuori=True,
                     modificabile=None, limite=lim)
    root.update()
    cmd = next(i for i, v in t6.voci.items() if v["zona"] == "cmd")
    t6.sotto_al_mouse = lambda: cmd
    t6.premi(type("E", (), dict(x=10, y=10, state=0))())
    casi.append(("il comandante resta fermo", t6.drag is None))
    t6.salva_tutto(); t6.chiudi()
    # le connessioni padre -> figlio: il pallino sotto le carte intere, tirato su un'altra carta; rifatta la toglie; l'imparato fra i mazzi
    fr = os.path.join(d, "rete.json")
    dbr = {"Token Maker": dict(cmc=2, tipo="Creature — Human", testo="When this creature enters, create two 1/1 white Soldier creature tokens."),
           "Anthem": dict(cmc=3, tipo="Enchantment", testo="Creatures you control get +1/+1."),
           "Vanilla": dict(cmc=2, tipo="Creature — Bear", testo=""), "Plains": dict(cmc=0, tipo="Basic Land — Plains", testo=""),
           "Side Anthem": dict(cmc=3, tipo="Enchantment", testo="Creatures you control get +1/+1.")}

    def nuovo_t(chiave="build:rete", griglia=False):
        t_ = TavoloCarte(tk, F, root, "Rete", {"Token Maker": 4, "Anthem": 2, "Vanilla": 4, "Plains": 10}, {"Side Anthem": 1}, carte_db=dbr, chiave=chiave,
                         file_tavoli=ft, file_mazzi=fm, file_rete=fr, fuori=True, limite=lim, editore=lambda a_, b_: None)     # col contatore, come nel builder
        root.update()
        t_.griglia = griglia
        return t_

    def vid_di(t_, nome):
        return next(i for i, v in t_.voci.items() if v["nome"] == nome)

    def tira(t_, a, b=None, xy=None):
        """Dal pallino di a fino a b (al centro della sua barra del nome) o al punto xy della tela."""
        va = vid_di(t_, a)
        bb = t_.cv.bbox(f"n{va}")
        if b is not None:
            bc = t_.cv.bbox(f"c{vid_di(t_, b)}")
            xy = ((bc[0] + bc[2]) / 2, bc[1] + 14)
        E = lambda x, y: type("E", (), dict(x=x - t_.cv.canvasx(0), y=y - t_.cv.canvasy(0), state=0))()
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        t_.nodo_inizio(E(cx, cy), va); t_.trascina(E(cx + 60, cy + 40)); t_.trascina(E(*xy)); t_.rilascia(E(*xy)); root.update()

    t7 = nuovo_t()
    intere = sum(1 for pl in t7.pile if not (pl["zona"] != "main" and t7.nascosta()))
    casi.append(("un pallino sotto ogni carta intera, nessuno sotto le coperte", len(t7.cv.find_withtag("nodo")) == intere and not t7.cv.find_withtag(f"n{vid_di(t7, 'Token Maker')}")))
    tira(t7, "Vanilla", "Anthem")
    casi.append(("il pallino tirato su un'altra carta: padre -> figlio, e la freccia", ("Vanilla", "Anthem") in t7.rete.figli and t7.cv.find_withtag("rete")))
    t7.apri_pila(vid_di(t7, "Token Maker")); root.update()
    casi.append(("la carta coperta, aperta, ha il suo pallino", bool(t7.cv.find_withtag(f"n{vid_di(t7, 'Token Maker')}"))))
    tira(t7, "Token Maker", "Anthem")
    casi.append(("le famiglie dal testo nella riga d'aiuto", ("Token Maker", "Anthem") in t7.rete.figli and "go wide" in t7.aiuto.cget("text")))
    tira(t7, "Token Maker", "Side Anthem")
    casi.append(("anche una carta della sideboard puo' essere figlia", ("Token Maker", "Side Anthem") in t7.rete.figli))
    tira(t7, "Token Maker", "Side Anthem")
    casi.append(("rifatta, la connessione si toglie", ("Token Maker", "Side Anthem") not in t7.rete.figli and "unlinked" in t7.aiuto.cget("text")))
    n_prima = len(t7.rete.figli)
    tira(t7, "Anthem", "Anthem")
    casi.append(("negativa: lasciato sulla stessa carta niente", len(t7.rete.figli) == n_prima))
    tira(t7, "Anthem", xy=(1300, t7.oy("main") + 700))
    casi.append(("negativa: lasciato sul vuoto niente", len(t7.rete.figli) == n_prima))
    an = t7.pila_di(vid_di(t7, "Anthem"))
    x_prima = an["x"]
    trascina_t = t
    t = t7
    trascina(vid_di(t7, "Anthem"), xy=(1000, t7.oy("main") + 60))
    t = trascina_t
    casi.append(("trascinare la carta (non il pallino) la sposta, non collega", t7.pila_di(vid_di(t7, "Anthem"))["x"] != x_prima and len(t7.rete.figli) == n_prima))
    t7.salva_tutto(); t7.chiudi()
    t8 = nuovo_t()
    casi.append(("riaperto: le connessioni restano, con le frecce", set(t8.rete.figli) == {("Vanilla", "Anthem"), ("Token Maker", "Anthem")} and t8.cv.find_withtag("rete")))
    # il foglio come Obsidian: le frecce dritte sotto le carte, la carta si prende in ogni punto, le frecce la seguono
    tutti = t8.cv.find_all()
    prima_carta = min(tutti.index(i) for i in t8.cv.find_withtag("carta"))
    ultima_carta = max(tutti.index(i) for i in t8.cv.find_withtag("carta"))
    primo_nodo = min(tutti.index(i) for i in t8.cv.find_withtag("nodo"))
    casi.append(("le frecce SOTTO le carte (mai sopra), i pallini sopra", all(tutti.index(i) < prima_carta for i in t8.cv.find_withtag("rete"))
                 and primo_nodo > ultima_carta and t8.cv.find_withtag("rete")))
    va, vb = t8.vid_nome("Vanilla"), t8.vid_nome("Anthem")
    ra, rb = t8.rett(va), t8.rett(vb)
    na, nb = t8.nodo_xy(va), t8.nodo_xy(vb)
    sg = t8.segmento(na, nb)
    dal = lambda pt, n_: abs(((pt[0] - n_[0]) ** 2 + (pt[1] - n_[1]) ** 2) ** 0.5 - (n_[2] + 2)) < 0.01
    casi.append(("la freccia e' dritta, da pallino a pallino", sg is not None and dal(sg[0], na) and dal(sg[1], nb)))
    tm = t8.vid_nome("Token Maker")
    coperta = t8.pila_di(tm)["carte"][-1] != tm
    casi.append(("la carta coperta con una freccia ha il pallino piccolo sulla barra del nome", coperta and t8.nodo_xy(tm)[2] == 5 and bool(t8.cv.find_withtag(f"n{tm}"))))
    E8 = lambda x, y: type("E", (), dict(x=x - t8.cv.canvasx(0), y=y - t8.cv.canvasy(0), state=0))()
    t8.premi_tela(E8((rb[0] + rb[2]) / 2, rb[1] + 3))
    casi.append(("la carta si prende anche dove arriva la freccia", t8.drag is not None and t8.drag["vid"] == vb))
    t8.rilascia(E8((rb[0] + rb[2]) / 2, rb[1] + 3)); t8.clic and t8.cv.after_cancel(t8.clic); t8.clic = None
    t8.premi_tela(E8(rb[0] - 8, rb[1] + 8))
    casi.append(("e dal numero delle copie che sporge a sinistra", t8.drag is not None and t8.drag["vid"] == vb))
    t8.rilascia(E8(rb[0] - 8, rb[1] + 8)); t8.clic and t8.cv.after_cancel(t8.clic); t8.clic = None
    t8.premi_tela(E8(rb[2] + 300, rb[3] + 300))
    casi.append(("negativa: nel vuoto non si prende niente", t8.drag is None))
    t8.cv.tag_raise("rete")     # lo strato delle frecce sopra tutto: il contatore deve rispondere lo stesso
    # un + che si puo' premere (una carta sotto il suo limite): l'ordine dei pezzi sulla tela non conta (12 nov 2026, la fascia sopra il foglio)
    piu = next(i for i in t8.cv.find_withtag("ctrl") if any(g.startswith("piu") for g in t8.cv.gettags(i))
               and (lambda v_: t8.totale(v_["nome"]) < t8.limite(v_["nome"]))(t8.voci[int(next(g for g in t8.cv.gettags(i) if g.startswith("piu"))[3:])]))
    vpiu = int(next(g for g in t8.cv.gettags(piu) if g.startswith("piu"))[3:])
    q0 = t8.voci[vpiu]["q"]
    bp = t8.cv.bbox(piu)
    t8.premi_tela(E8((bp[0] + bp[2]) / 2, (bp[1] + bp[3]) / 2)); t8.rilascia(E8((bp[0] + bp[2]) / 2, (bp[1] + bp[3]) / 2))
    casi.append(("il + del contatore risponde anche sotto lo strato delle frecce", t8.voci[vpiu]["q"] == q0 + 1 and t8.drag is None))
    meno = next(i for i in t8.cv.find_withtag(f"meno{vpiu}"))
    bm = t8.cv.bbox(meno)
    t8.premi_tela(E8((bm[0] + bm[2]) / 2, (bm[1] + bm[3]) / 2)); t8.rilascia(E8((bm[0] + bm[2]) / 2, (bm[1] + bm[3]) / 2))
    casi.append(("e il − toglie la copia", t8.voci[vpiu]["q"] == q0))
    # il bordo: col mouse vicino al bordo il foglio scorre da solo e la carta resta sotto il mouse
    t8.cv.winfo_width = lambda: 900; t8.cv.winfo_height = lambda: 600
    t8.cv.xview_moveto(0); t8.cv.yview_moveto(0); root.update()
    cx_, cy_ = (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2
    t8.premi_tela(E8(cx_, cy_)); t8.trascina(type("E", (), dict(x=450, y=590))())
    y0_view = t8.cv.canvasy(0)
    fine_ = _t.time() + 0.3
    while _t.time() < fine_:
        root.update(); _t.sleep(0.01)
    y1_view = t8.cv.canvasy(0)
    bbc = t8.cv.bbox(f"c{vb}")
    casi.append(("vicino al bordo il foglio scorre dolce e la carta resta sotto il mouse", y1_view - y0_view > 40 and bbc[1] <= t8.drag["y"] <= bbc[3]))
    t8.rilascia(type("E", (), dict(x=450, y=300))()); root.update()
    del t8.cv.winfo_width, t8.cv.winfo_height
    rb = t8.rett(vb)        # la carta e' stata spostata dalla prova dei bordi
    cx_, cy_ = (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2
    t8.premi_tela(E8(cx_, cy_)); t8.trascina(E8(cx_ + 40, cy_ + 30))
    viva = t8.cv.find_withtag("rete_viva")
    c1 = t8.cv.coords(viva[0]) if viva else None
    t8.trascina(E8(cx_ + 160, cy_ + 120))
    c2 = t8.cv.coords(viva[0]) if viva else None
    casi.append(("trascinando, le frecce della carta la seguono", len(viva) == 2 and c1 != c2))
    t8.rilascia(E8(cx_ + 160, cy_ + 120)); root.update()
    casi.append(("lasciata, le frecce tornano nell'immagine, gia' al posto nuovo", not t8.cv.find_withtag("rete_viva") and t8.cv.find_withtag("rete")
                 and t8.segmento(t8.nodo_xy(va), t8.nodo_xy(vb)) != sg))
    # la carta segue dal primo pixel; sotto i 3 pixel e' un clic e torna al suo posto
    # la fascia ferma in cima alla finestra (12 nov 2026): la vista scende, la fascia la segue; sulla fascia non si prende una carta del mazzo che le passa sotto
    t8.cv.xview_moveto(0); t8.cv.yview_moveto(0); t8.segui_fascia(); root.update()
    rv0 = t8.rett(va)
    t8.cv.scan_mark(0, 0); t8.cv.scan_dragto(0, -int(rv0[1] + 20), gain=1); t8.segui_fascia(); root.update()
    bf = t8.cv.bbox("fascia_fondo")
    casi.append(("la vista scende: la fascia resta in cima alla finestra", bf is not None and abs(bf[3] - (t8.cv.canvasy(0) + t8.hs)) <= 1 and t8._fy == t8.cv.canvasy(0)))
    rv1 = t8.rett(va)
    sotto = ((rv1[0] + rv1[2]) / 2, t8.cv.canvasy(0) + 10)
    casi.append(("negativa: sulla fascia la carta del mazzo che le passa sotto non si prende", rv1[1] < sotto[1] < rv1[3] and t8.carta_a(*sotto) != va))
    t8.cv.xview_moveto(0); t8.cv.yview_moveto(0); t8.segui_fascia(); root.update()     # la vista in cima: la carta non e' sotto la fascia
    rv = t8.rett(va)
    px_, py_ = (rv[0] + rv[2]) / 2, (rv[1] + rv[3]) / 2
    b0 = t8.cv.bbox(f"c{va}")
    t8.premi_tela(E8(px_, py_)); t8.trascina(E8(px_ + 1, py_ + 1)); root.update()
    b1 = t8.cv.bbox(f"c{va}")
    casi.append(("la carta segue il mouse dal primo pixel", b1[0] - b0[0] == 1 and b1[1] - b0[1] == 1))
    t8.rilascia(E8(px_ + 1, py_ + 1)); root.update()
    casi.append(("sotto i 3 pixel e' un clic: la carta torna al suo posto", t8.cv.bbox(f"c{va}") == b0 and t8.clic is not None and t8.pila_di(va)["x"] == t8.pila_di(va)["x"]))
    t8.cv.after_cancel(t8.clic); t8.clic = None
    # una freccia un'immagine; all'inizio del trascinamento si nascondono solo quelle della carta presa
    t8.disegna(); root.update()
    casi.append(("le frecce: sulla scheda una linea per freccia, in Tk un'immagine sola", len(t8.cv.find_withtag("rete")) == (len(t8._segmenti) if t8.gpu else 1)
                 and len(t8._segmenti) == len(t8.legami_visti()) == 2))
    casi.append(("la tela e' quella della scheda video, se pyglet c'e' e TAVOLO_TK non la spegne", t8.gpu == (TG.disponibile() and os.environ.get("TAVOLO_TK") != "1")))
    rv = t8.rett(va); px_, py_ = (rv[0] + rv[2]) / 2, (rv[1] + rv[3]) / 2
    t8.premi_tela(E8(px_, py_)); t8.trascina(E8(px_ + 50, py_ + 40))
    casi.append(("trascinando le frecce ferme si nascondono TUTTE e diventano linee (nessuna traccia vecchia)",
                 all(t8.cv.itemcget(i_, "state") == "hidden" for i_ in t8.cv.find_withtag("rete")) and len(t8.cv.find_withtag("rete_viva")) == 2))
    t8.rilascia(E8(px_ + 50, py_ + 40)); root.update()
    # rompere una connessione: la freccia si accende, la ✕ a meta' la toglie
    sg = t8._segmenti[0]
    mx_, my_ = (sg[2][0] + sg[3][0]) / 2, (sg[2][1] + sg[3][1]) / 2
    t8.passa(E8(mx_ + 30, my_ + 200)); 
    casi.append(("negativa: lontano dalla freccia niente ✕", not t8.cv.find_withtag("rete_x")))
    t8.passa(E8(mx_, my_ + 2))
    casi.append(("sopra la freccia compare la ✕", bool(t8.cv.find_withtag("rete_x"))))
    n_prima = len(t8.rete.figli)
    bx8 = t8.cv.bbox("rete_x"); xx_, xy8 = (bx8[0] + bx8[2]) / 2, (bx8[1] + bx8[3]) / 2
    t8.premi_tela(E8(xx_, xy8)); t8.rilascia(E8(xx_, xy8)); root.update()
    casi.append(("il clic sulla ✕ toglie la connessione", len(t8.rete.figli) == n_prima - 1 and "unlinked" in t8.aiuto.cget("text") and t8.drag is None))
    sg = t8._segmenti[0]
    mx_, my_ = (sg[2][0] + sg[3][0]) / 2, (sg[2][1] + sg[3][1]) / 2
    t8.destro(E8(mx_ + 1, my_)); root.update()
    casi.append(("e anche il tasto destro sulla freccia", len(t8.rete.figli) == n_prima - 2))
    # il ⇄: sostituisce la carta con una della collezione, alle stesse copie fino al limite, nello stesso posto
    tv_ = t8.vid_nome("Vanilla")
    casi.append(("sotto le carte intere il pulsante ⇄", bool(t8.cv.find_withtag(f"s{tv_}"))))
    t8.nomi_ricerca = lambda: ["Grizzly Bears", "Grizzled Outrider", "Vanilla", "Anthem"]
    trov = t8.scambia_trova("griz", "Vanilla")
    casi.append(("la ricerca del ⇄: le carte che contengono il testo, non quella da sostituire", [n for n, _q in trov] == ["Grizzly Bears", "Grizzled Outrider"]
                 or set(n for n, _q in trov) == {"Grizzly Bears", "Grizzled Outrider"}))
    posto = (t8.pila_di(tv_)["x"], t8.pila_di(tv_)["y"])
    bs = t8.cv.bbox(f"s{tv_}")
    t8.premi_tela(E8((bs[0] + bs[2]) / 2, (bs[1] + bs[3]) / 2))
    aperto = t8._scambio is not None
    t8.scambia_chiudi()
    for k_ in (("Token Maker", "Vanilla"), ("Vanilla", "Anthem")):     # Vanilla figlia di una e padre dell'altra: le connessioni passano alla carta nuova
        if k_ not in t8.rete.figli:
            t8.rete.lega(k_[0], k_[1], dbr)
    t8.scambia(tv_, "Grizzly Bears"); root.update()
    gb = t8.vid_nome("Grizzly Bears")
    casi.append(("il ⇄ apre la ricerca, e la carta nuova prende il posto e le copie della vecchia", aperto and gb is not None and t8.voci[gb]["q"] == 4
                 and (t8.pila_di(gb)["x"], t8.pila_di(gb)["y"]) == posto and t8.vid_nome("Vanilla") is None))
    aiuto_8 = t8.aiuto.cget("text")
    t8.salva_tutto()
    salvate = RS.carica(t8.rete.f or RS.FILE).get(t8.rete.chiave, {}).get("figli", [])
    casi.append(("sostituita, la carta tiene le connessioni: padre resta padre, figlio resta figlio, anche nel file e a video",
                 ("Token Maker", "Grizzly Bears") in t8.rete.figli and ("Grizzly Bears", "Anthem") in t8.rete.figli
                 and not any("Vanilla" in k_ for k_ in t8.rete.figli) and ["Token Maker", "Grizzly Bears"] in [x[:2] for x in salvate]
                 and any({t8.voci[a_]["nome"], t8.voci[b_]["nome"]} == {"Grizzly Bears", "Anthem"} for a_, b_, _p, _c in t8._segmenti) and "links kept" in aiuto_8))
    fig_anthem = {k_ for k_ in t8.rete.figli if "Anthem" in k_}
    t8.scambia(t8.vid_nome("Anthem"), "Grizzly Bears"); root.update()
    casi.append(("negativa: oltre il limite del formato non sostituisce, e le connessioni restano dove sono", t8.vid_nome("Anthem") is not None
                 and t8.voci[t8.vid_nome("Grizzly Bears")]["q"] == 4 and {k_ for k_ in t8.rete.figli if "Anthem" in k_} == fig_anthem))
    # le note personali (12 nov 2026): sulla carta e sulla label; si aprono e si chiudono, si scrivono, si cancellano, si salvano
    t8.cv.xview_moveto(0); t8.cv.yview_moveto(0); t8.segui_fascia(); t8.disegna(); root.update()
    vn = t8.vid_nome("Token Maker")
    t8.pila_di(vn)["aperta"] = vn; t8.disegna(); root.update()
    bn_, bp_ = t8.cv.bbox(f"nn{vn}"), t8.cv.bbox(f"n{vn}")
    casi.append(("nota: il + nota alla base della carta, a sinistra del pallino giallo, alla sua altezza (12 nov 2026)",
                 bool(bn_ and bp_) and bn_[2] <= bp_[0] and abs((bn_[1] + bn_[3]) / 2 - (bp_[1] + bp_[3]) / 2) < 3))
    t8.metti_nota("c", "Token Maker", "Keep for the late game"); root.update()
    casi.append(("nota scritta: l'icona sulla carta e il riquadro aperto col testo", bool(t8.cv.find_withtag(f"ni{vn}")) and bool(t8.cv.find_withtag(f"nb{vn}"))
                 and "Keep for the late game" in [t8.cv.itemcget(i, "text") for i in t8.cv.find_withtag(f"nb{vn}") if t8.cv.type(i) == "text"]))
    bi = t8.cv.bbox(f"ni{vn}")
    t8.premi_tela(E8((bi[0] + bi[2]) / 2, (bi[1] + bi[3]) / 2)); t8.rilascia(E8((bi[0] + bi[2]) / 2, (bi[1] + bi[3]) / 2)); root.update()
    casi.append(("il clic sull'icona la chiude, la carta non si sposta", not t8.note["Token Maker"]["aperta"] and not t8.cv.find_withtag(f"nb{vn}") and t8.drag is None))
    t8.premi_tela(E8((bi[0] + bi[2]) / 2, (bi[1] + bi[3]) / 2)); t8.rilascia(E8((bi[0] + bi[2]) / 2, (bi[1] + bi[3]) / 2)); root.update()
    bb_ = t8.cv.bbox(f"nb{vn}")
    t8.premi_tela(E8(bb_[0] + 20, bb_[1] + 8)); t8.rilascia(E8(bb_[0] + 20, bb_[1] + 8)); root.update()
    casi.append(("riaperta; il clic sul riquadro apre l'editor col testo", t8.note["Token Maker"]["aperta"] and getattr(t8, "_nota_pop", None) is not None
                 and t8.testo_nota.get("1.0", "end").strip() == "Keep for the late game"))
    t8.testo_nota.delete("1.0", "end"); t8.testo_nota.insert("1.0", "Side out vs control"); t8.pronta_nota(); root.update()
    casi.append(("l'editor la cambia e si chiude", t8.note["Token Maker"]["testo"] == "Side out vs control" and t8._nota_pop is None))
    t8.sel = [t8.pila_di(t8.vid_nome("Anthem"))]; lbn = t8.crea_etichetta("Plan B"); root.update()
    kn = t8.etichette.index(lbn)
    t8.metti_nota("l", kn, "Swap in after game 1"); root.update()
    casi.append(("la nota della label: l'icona sul titolo e il riquadro sotto", bool(t8.cv.find_withtag(f"ln{kn}")) and bool(t8.cv.find_withtag(f"lb{kn}"))))
    t8.salva_tutto()
    salvata_ = carica_tavoli(t8.file_tavoli).get(t8.chiave) or {}
    casi.append(("le note si salvano con la disposizione", (salvata_.get("note") or {}).get("Token Maker", {}).get("testo") == "Side out vs control"
                 and any(x.get("nota") == "Swap in after game 1" for x in salvata_.get("etichette") or [])))
    t8.metti_nota("c", "Token Maker", ""); t8.metti_nota("l", kn, ""); t8.salva_tutto(); root.update()
    casi.append(("negativa: cancellate, niente icone piene ne' riquadri e niente nel file; restano i + nota (alla base della carta, sul titolo della label)",
                 not t8.cv.find_withtag(f"ni{vn}") and not t8.cv.find_withtag(f"lb{kn}") and bool(t8.cv.find_withtag(f"nn{vn}"))
                 and bool(t8.cv.find_withtag(f"ln{kn}")) and not (carica_tavoli(t8.file_tavoli).get(t8.chiave) or {}).get("note") and "nota" not in t8.etichette[kn]))
    t8.togli_etichetta(kn)
    if ("Token Maker", "Anthem") not in t8.rete.figli:       # la connessione che la prova dell'imparato cerca in un altro mazzo
        t8.rete.lega("Token Maker", "Anthem", dbr)
    t8.salva_tutto(); t8.chiudi()
    # i filtri per tipo (12 nov 2026): All acceso di partenza e assoluto; un tipo spegne All, piu' tipi si sommano; le carte fuori non si vedono e non si
    # prendono, ma restano nel mazzo e nella disposizione salvata
    tF = nuovo_t("build:filtri")
    pos0 = {tF.voci[c]["nome"]: (pl["x"], pl["y"]) for pl in tF.pile for c in pl["carte"]}
    etich_ = [tF.c_filtri.itemcget(i, "text") for i in tF.c_filtri.find_all() if tF.c_filtri.type(i) == "text"]
    casi.append(("filtri: la riga coi tipi del mazzo e i loro conti, All acceso", not tF.filtro and "All 21" in etich_ and "Creatures 8" in etich_
                 and "Enchantments 3" in etich_ and "Lands 10" in etich_ and not any(x.startswith("Instants") for x in etich_)))
    an_ = vid_di(tF, "Anthem"); ra0_ = tF.rett(an_)
    tF.scegli_filtro("creature"); root.update()
    casi.append(("Creatures: si vedono solo le creature, All si spegne", tF.filtro == {"creature"} and not tF.cv.find_withtag(f"c{an_}")
                 and tF.cv.find_withtag(f"c{vid_di(tF, 'Token Maker')}") and tF.rett(an_) is None))
    casi.append(("negativa: dove stava una carta nascosta non si prende niente", tF.carta_a((ra0_[0] + ra0_[2]) / 2, (ra0_[1] + ra0_[3]) / 2) != an_))
    tF.scegli_filtro("enchantment"); root.update()
    casi.append(("piu' tipi si sommano: creature e incantesimi, le terre restano nascoste", tF.filtro == {"creature", "enchantment"} and tF.cv.find_withtag(f"c{an_}")
                 and not tF.cv.find_withtag(f"c{vid_di(tF, 'Plains')}")))
    tF.salva_tutto()
    sal_ = carica_tavoli(ft).get("build:filtri") or {}
    casi.append(("filtrato, la disposizione salvata ha tutte le carte", {c[0] for pl in sal_.get("pile") or [] for c in pl["carte"]} >= {"Plains", "Anthem", "Vanilla", "Token Maker"}))
    tF.scegli_filtro("all"); root.update()
    pos1 = {tF.voci[c]["nome"]: (pl["x"], pl["y"]) for pl in tF.pile for c in pl["carte"]}
    casi.append(("All assoluto: spegne gli altri e tutto torna al suo posto", not tF.filtro and pos1 == pos0 and not tF._riposte))
    tF.scegli_filtro("land"); tF.scegli_filtro("land"); root.update()
    casi.append(("spento l'ultimo tipo torna All", not tF.filtro and tF.cv.find_withtag(f"c{vid_di(tF, 'Plains')}")))
    # lo stress del 12 nov 2026: col filtro acceso, trascinate via tutte le carte a vista di una pila, quelle nascoste non devono perdersi
    pa_ = tF.pila_di(vid_di(tF, "Anthem")); ptm_ = tF.pila_di(vid_di(tF, "Token Maker"))
    pa_["carte"].remove(vid_di(tF, "Anthem")); ptm_["carte"].insert(0, vid_di(tF, "Anthem"))
    if not pa_["carte"]:
        tF.pile.remove(pa_)
    tF.disegna(); tF.scegli_filtro("creature"); root.update()
    top_ = ptm_["carte"][-1]; rt_ = tF.rett(top_)
    EF = lambda x, y, st=0: type("E", (), dict(x=x - tF.cv.canvasx(0), y=y - tF.cv.canvasy(0), state=st))()
    tF.premi_tela(EF((rt_[0] + rt_[2]) / 2, (rt_[1] + rt_[3]) / 2, 1)); tF.trascina(EF(rt_[0] + 900, rt_[1] + 400)); tF.rilascia(EF(rt_[0] + 900, rt_[1] + 400))
    root.update()
    tF.scegli_filtro("all"); root.update()
    in_pila = {c for pl in tF.pile for c in pl["carte"]}
    casi.append(("negativa dello stress: trascinate via le carte a vista di una pila, quella nascosta torna al suo posto", set(tF.voci) <= in_pila
                 and vid_di(tF, "Anthem") in in_pila))
    # i gruppi (12 nov 2026): nell'outliner, duplicati che non portano carte, il ⇄ nella copia, lo Swap, via col contenuto, via vuoti; i gruppi automatici
    tF.scegli_filtro("all")
    tF.sel = [tF.pila_di(vid_di(tF, "Anthem"))]; g1 = tF.crea_etichetta("Buffs"); root.update()
    k1 = tF.etichette.index(g1)
    righe_g = [v for _y0, _y1, v in tF._out_righe if isinstance(v, tuple)]
    casi.append(("gruppi: l'outliner mostra il gruppo", ("l", k1) in righe_g))
    mazzo0 = tF.liste()
    cp = tF.duplica_gruppo(k1); root.update()
    kc = tF.etichette.index(cp)
    casi.append(("Duplicate: la copia ha le carte del gruppo scritte, e il mazzo non cambia", cp["copia"] and cp["carte"] == {"Anthem": 2} and tF.liste() == mazzo0
                 and cp["origine"] == g1["id"] and tF.cv.find_withtag("copia_w")))
    tF.cambia_copia(kc, "Anthem", "Side Anthem"); root.update()
    casi.append(("il ⇄ nella copia cambia la carta, il mazzo no", cp["carte"] == {"Side Anthem": 2} and tF.liste() == mazzo0))
    casi.append(("Swap: nel mazzo le carte della copia al posto di quelle del gruppo, la copia prende quelle di prima",
                 tF.scambia_gruppo(kc) and tF.liste()[0].get("Side Anthem") == 2 and "Anthem" not in tF.liste()[0] and cp["carte"] == {"Anthem": 2}
                 and tF.carte_gruppo(k1) == {"Side Anthem": 2}))
    tF.scambia_gruppo(kc); root.update()
    casi.append(("un altro Swap torna indietro", tF.liste()[0].get("Anthem") == 2 and "Side Anthem" not in tF.liste()[0] and cp["carte"] == {"Side Anthem": 2}))
    cp["carte"] = {"Anthem": 4, "Vanilla": 1}
    casi.append(("negativa: lo Swap che passa il limite delle copie non si fa", not tF.scambia_gruppo(kc) and tF.liste()[0].get("Anthem") == 2))
    tF.salva_tutto()
    salv_ = carica_tavoli(ft).get("build:filtri") or {}
    casi.append(("la copia si salva con le sue carte e l'origine", any(x.get("copia") and x.get("origine") == g1["id"] for x in salv_.get("etichette") or [])))
    tF.togli_gruppo(tF.etichette.index(cp)); root.update()
    casi.append(("via la copia: il mazzo non cambia", tF.liste()[0].get("Anthem") == 2 and cp not in tF.etichette))
    tF.togli_gruppo(tF.etichette.index(g1)); root.update()
    casi.append(("via il gruppo con le sue carte: l'Anthem esce dal mazzo", "Anthem" not in tF.liste()[0] and g1 not in tF.etichette))
    tF.sel = [tF.pila_di(vid_di(tF, "Vanilla"))]; g2 = tF.crea_etichetta("Bears"); root.update()
    p2_ = tF.pila_di(vid_di(tF, "Vanilla")); p2_["x"] += 3000; tF.disegna()
    tF.togli_etichetta(tF.etichette.index(g2)); root.update()
    casi.append(("il gruppo vuoto (le carte portate fuori) si toglie, e lo dice", g2 not in tF.etichette and "Empty group" in tF.aiuto.cget("text")
                 and tF.liste()[0].get("Vanilla") == 4))
    # i gruppi automatici: dal filtro e dall'analisi (passata dalla prova: il mazzo di prova non ha partite)
    tF.scegli_filtro("creature")
    nate_ = tF.auto_visibili(); root.update()
    nomi_ = {lb["nome"] for lb in nate_}
    nascoste_ = {tF.voci[v_]["nome"]: (tF.pila_di(v_) or {}).get("x") for v_ in tF.voci if tF.voci[v_]["zona"] == "main" and not tF.visibile(v_)}
    casi.append(("Auto group dal filtro: un gruppo solo, con le carte a vista (le creature); il filtro resta acceso (12 nov 2026)", nomi_ == {"Creatures"}
                 and set(tF.carte_gruppo(tF.etichette.index(nate_[0]))) == {"Token Maker", "Vanilla"} and tF.filtro == {"creature"}))
    casi.append(("negativa: le carte nascoste dal filtro non entrano nel gruppo e restano al loro posto", bool(nascoste_)
                 and not set(nascoste_) & set(tF.carte_gruppo(tF.etichette.index(nate_[0])))
                 and all((tF.pila_di(tF.vid_nome(n_)) or {}).get("x") == x_ for n_, x_ in nascoste_.items())))
    tF.scegli_filtro("all")
    tF.fonte_analisi = lambda: dict(con_dati=30, migliori=[dict(nome="Token Maker")], fatica=[dict(nome="Plains")], perse=[dict(nome="Non nel mazzo")])
    nate2 = tF.auto_analisi(); root.update()
    casi.append(("Auto groups dall'analisi: Best performers e Hard to cast; negativa: la carta che non e' nel mazzo non fa gruppo",
                 [lb["nome"] for lb in nate2] == ["Best performers", "Hard to cast"]))
    tF.fonte_analisi = lambda: None
    casi.append(("negativa: senza partite niente gruppi dall'analisi, e lo dice", tF.auto_analisi() == [] and "No games" in tF.aiuto.cget("text")))
    # il menu Groups accanto ad Arrange (13 nov 2026 sera): Auto groups non c'e' piu' nella riga dei filtri, le sue funzioni sono qui
    import tkinter as tk_
    pG = tF.menu_gruppi(); root.update()
    testi_G = [w_.cget("text") for w_ in tutti_widget(pG) if isinstance(w_, tk_.Label)]
    casi.append(("il pulsante Groups sta in testata subito dopo Arrange", tF.b_gruppi is not None and tF.b_gruppi.pack_info().get("side") == "left"
                 and tF.b_gruppi.master is tF.b_arrange.master))
    fill_s = [tF.b_salva.itemcget(i_, "fill") for i_ in tF.b_salva.find_all() if tF.b_salva.type(i_) == "rectangle"]
    casi.append(("Save in fondo a destra della testata (dopo lo zoom), verde (13 nov 2026)", tF.b_salva.master.pack_slaves()[0] is tF.b_salva
                 and bool(fill_s) and fill_s[0] in VERDE_P))
    casi.append(("il menu Groups: NEW, FROM YOUR GAMES, YOUR GROUPS coi gruppi, TIDY; e l'ex Auto groups (selezione, carte a vista, analisi)",
                 all(s_ in " ".join(testi_G) for s_ in ("NEW", "FROM YOUR GAMES", f"YOUR GROUPS · {len(tF.etichette)}", "TIDY", "Group the selection",
                                                        "Group the visible cards", "Best performers", "Remove empty groups", "Remove all groups"))
                 and all(lb["nome"].upper() in " ".join(testi_G) for lb in tF.etichette)))
    casi.append(("negativa: niente piu' AUTO GROUPS nella riga dei filtri", not any(ch_ == "auto" for _a, _b, ch_ in tF._box_filtri)
                 and not any(tF.c_filtri.type(i_) == "text" and "AUTO" in tF.c_filtri.itemcget(i_, "text") for i_ in tF.c_filtri.find_all())))
    tF.nome_chiudi()
    kB_ = len(tF.etichette) - 1
    tF.menu_gruppi().voci[f"group:{kB_}"](); root.update()
    casi.append(("dal menu, il clic su un gruppo lo sceglie", tF.sel_label == {kB_}))
    tF.nome_chiudi()
    tF.lucchetti_tutti(False); root.update()
    aperti_ = all(not lb.get("lucchetto", True) for lb in tF.etichette)
    tF.lucchetti_tutti(True); root.update()
    casi.append(("Unlock all e Lock all: tutti i lucchetti insieme", aperti_ and all(lb.get("lucchetto", True) for lb in tF.etichette)))
    gV_ = dict(nome="Vuoto", x=40000, y=40000, w=400, h=300, colore=GRIGIO_L, lucchetto=True, id=tF.nuovo_id())
    tF.etichette.append(gV_); tF.disegna()
    vuoti_ = [lb_ for k_, lb_ in enumerate(tF.etichette) if not lb_.get("copia") and not tF.carte_gruppo(k_)]
    pieni_ = [lb_ for lb_ in tF.etichette if lb_ not in vuoti_]
    n_prima = len(tF.etichette)
    n_v = tF.togli_vuoti(); root.update()
    casi.append(("Remove empty groups: via solo quelli senza carte, quelli con le carte restano", gV_ in vuoti_ and bool(pieni_) and n_v == len(vuoti_)
                 and gV_ not in tF.etichette and all(lb_ in tF.etichette for lb_ in pieni_)))
    n_dopo = len(tF.etichette)
    casi.append(("negativa: rifatto, nessun gruppo vuoto da togliere", tF.togli_vuoti() == 0))
    lista_prima = dict(tF.liste()[0])
    dG = tF.togli_tutti_gruppi(); root.update()
    resta_ = len(tF.etichette) > 0
    dG.no(); root.update()
    casi.append(("Remove all groups chiede prima; Cancel non toglie niente", resta_ and len(tF.etichette) == n_dopo))
    tF.togli_tutti_gruppi().si(); root.update()
    casi.append(("Remove all groups: via le cornici, le carte restano nel mazzo", not tF.etichette and tF.liste()[0] == lista_prima))
    tF.annulla(); root.update()
    casi.append(("Undo riporta i gruppi tolti", len(tF.etichette) == n_dopo))
    # l'occhio dell'outliner, come i livelli di Photoshop (13 nov 2026)
    tF.apri_outliner(True); tF.disegna(); tF.disegna_outliner(); root.update()

    class Ev_:
        def __init__(s_, x, y, state=0):
            s_.x, s_.y, s_.state = x, y, state

    def riga_y(voce):
        return next((y0 + 5 for y0, _y1, v_ in tF._out_righe if v_ == voce), None)
    k_g = next(k_ for k_, lb in enumerate(tF.etichette) if not lb.get("copia") and tF.carte_gruppo(k_))
    dentro_g = [c_ for pl in tF.membri(k_g)[0] for c_ in pl["carte"]]
    libera = next(v_ for v_, x in tF.voci.items() if x["zona"] == "main" and v_ not in dentro_g and tF.pila_di(v_) is not None)
    if len(tF.pila_di(libera)["carte"]) > 1:      # una carta libera, fuori da ogni gruppo: la sua pila sola, lontano
        tF.pila_di(libera)["carte"].remove(libera)
        tF.pile.append(dict(zona="main", x=60000, y=60000, carte=[libera], aperta=None))
    else:
        tF.pila_di(libera).update(x=60000, y=60000)
    tF.disegna(); tF.disegna_outliner(); root.update()
    casi.append(("ogni riga dell'outliner ha l'occhio a sinistra", all(riga_y(v_) is not None for v_ in (libera, ("l", k_g)))))
    lista_0 = dict(tF.liste()[0])
    tF.scegli_outliner(Ev_(OCCHIO_OUT + 40, riga_y(libera))); root.update()
    casi.append(("negativa: il clic sul nome sceglie la carta e non la spegne", tF.acceso(libera) and tF.pila_di(libera) is not None))
    pos_l = (tF.pila_di(libera)["x"], tF.pila_di(libera)["y"])
    tF.scegli_outliner(Ev_(6, riga_y(libera))); setattr(tF, "_occhi_drag", None); root.update()
    casi.append(("l'occhio spegne la carta: fuori dal foglio, nel mazzo come prima, la riga resta", tF.pila_di(libera) is None and tF.liste()[0] == lista_0
                 and riga_y(libera) is not None and not tF.acceso(libera)))
    tF.scegli_outliner(Ev_(6, riga_y(libera))); setattr(tF, "_occhi_drag", None); root.update()
    casi.append(("riacceso, torna al suo posto", tF.pila_di(libera) is not None and (tF.pila_di(libera)["x"], tF.pila_di(libera)["y"]) == pos_l))
    uno = dentro_g[0]
    tF.occhio(uno, on=False); root.update()
    tF.occhio(("l", k_g), on=False); root.update()
    casi.append(("il gruppo spento: sparisce la cornice con tutte le sue carte", not tF.cv.find_withtag(f"lt{k_g}") and all(tF.pila_di(c_) is None for c_ in dentro_g)))
    altro_ = next((c_ for c_ in dentro_g if c_ != uno), None)
    casi.append(("come nei livelli: la carta del gruppo spento tiene il suo occhio aperto, ma non si vede", altro_ is None
                 or (tF.acceso(altro_) and altro_ in tF._spente)))
    tF.occhio(("l", k_g), on=True); root.update()
    casi.append(("riacceso il gruppo, tornano le sue carte; quella spenta da sola resta spenta", tF.cv.find_withtag(f"lt{k_g}") and tF.pila_di(uno) is None
                 and (altro_ is None or tF.pila_di(altro_) is not None)))
    tF.occhio(uno, on=True); root.update()
    tF.scegli_outliner(Ev_(6, riga_y(("l", k_g)), state=0x20000 if piattaforma.WINDOWS else 0x10)); root.update()
    solo_ok = (all(tF.pila_di(c_) is not None for c_ in dentro_g) and tF.pila_di(libera) is None
               and all(tF.etichette[j].get("nascosta") for j in range(len(tF.etichette)) if j != k_g and not tF.contiene(tF.etichette[j], tF.etichette[k_g])))
    tF.scegli_outliner(Ev_(6, riga_y(("l", k_g)), state=0x20000 if piattaforma.WINDOWS else 0x10)); root.update()
    casi.append(("Alt+clic: solo il gruppo a vista; di nuovo Alt+clic, tutto come prima", solo_ok and not tF.occhi
                 and not any(lb.get("nascosta") for lb in tF.etichette) and tF.pila_di(libera) is not None))
    righe_c = [v_ for _a, _b, v_ in tF._out_righe if not isinstance(v_, tuple)][:3]
    tF.scegli_outliner(Ev_(6, riga_y(righe_c[0])))
    for v_ in righe_c[1:]:
        tF.occhi_trascina(Ev_(6, riga_y(v_)))
    tF._occhi_drag = None; root.update()
    casi.append(("trascinando sugli occhi si spengono in fila", all(not tF.acceso(v_) for v_ in righe_c)))
    tF.annulla(); root.update()
    casi.append(("Undo riaccende l'ultimo occhio spento", tF.acceso(righe_c[-1]) and not tF.acceso(righe_c[0])))
    root.update()
    casi.append(("con qualcosa di spento, SHOW ALL in testa all'outliner", tF.b_tutti.winfo_manager() == "pack"))
    n_sa = tF.mostra_tutto(); root.update()
    casi.append(("SHOW ALL riaccende tutto e poi si toglie", n_sa >= 1 and not tF.occhi and not any(lb.get("nascosta") for lb in tF.etichette)
                 and tF.b_tutti.winfo_manager() == ""))
    casi.append(("negativa: con tutto acceso SHOW ALL non fa niente", tF.mostra_tutto() == 0))
    vista_ = (tF.cv.canvasx(0), tF.cv.canvasy(0), tF.zoom)
    tF.scegli_outliner(Ev_(6, riga_y(libera))); tF.doppio_outliner(Ev_(6, riga_y(libera))); tF._occhi_drag = None; root.update()
    casi.append(("il doppio clic su un occhio: due clic, la carta torna come prima e la vista non si sposta", tF.acceso(libera)
                 and (tF.cv.canvasx(0), tF.cv.canvasy(0), tF.zoom) == vista_))
    tF.passa_outliner(Ev_(OCCHIO_OUT + 40, riga_y(libera))); root.update()
    casi.append(("la riga sotto il mouse si accende", bool(tF.out_cv.find_withtag("su"))))
    tF.scegli_filtro("land"); root.update()
    non_terra = next(v_ for _a, _b, v_ in tF._out_righe if not isinstance(v_, tuple) and "land" not in tF.tipi_di(v_))
    y_nt = riga_y(non_terra)
    testi_nt = [i_ for i_ in tF.out_cv.find_overlapping(OCCHIO_OUT + 12, y_nt, OCCHIO_OUT + 120, y_nt + 8) if tF.out_cv.type(i_) == "text"]
    casi.append(("col filtro per tipo le carte fuori dal filtro sono grigie anche nell'outliner (il loro occhio resta aperto)", bool(testi_nt)
                 and tF.out_cv.itemcget(testi_nt[0], "fill") == C["muto"] and tF.acceso(non_terra)))
    tF.scegli_filtro("all"); root.update()
    tF.occhio(("l", k_g), on=False); tF.occhio(libera, on=False); root.update()
    tF.salva_tutto()
    salv_o = carica_tavoli(ft).get("build:filtri") or {}
    casi.append(("la visibilita' si salva con la disposizione: le carte spente e il gruppo spento", bool(salv_o.get("nascoste"))
                 and any(x.get("nascosta") for x in salv_o.get("etichette") or [])))
    tF.salva_tutto(); tF.chiudi()
    tO_ = nuovo_t("build:filtri")
    casi.append(("riaperto, le carte spente e il gruppo spento restano spenti", bool(tO_.occhi) and any(lb.get("nascosta") for lb in tO_.etichette)
                 and any(tO_.pila_di(c_) is None for c_ in tO_.voci if tO_.voci[c_]["zona"] == "main")))
    tO_.occhi = set()
    for lb in tO_.etichette:
        lb.pop("nascosta", None)
    tO_.disegna(); tO_.salva_tutto(); tO_.chiudi()
    t9 = nuovo_t("build:altro")
    t9.apri_pila(vid_di(t9, "Token Maker")); root.update()
    va = vid_di(t9, "Token Maker")
    bb = t9.cv.bbox(f"n{va}")
    t9.nodo_inizio(type("E", (), dict(x=bb[0], y=bb[1], state=0))(), va)
    casi.append(("l'imparato: in un altro mazzo, i figli che Token Maker ha avuto", t9.tira["imparati"] == ["Anthem"]))
    t9.tira = None
    t9.salva_tutto(); t9.chiudi()
    # le linee (9 nov 2026): di partenza grigio perlato e sottili; la tavolozza sulla freccia sceglie colore e importanza, e restano
    tA = nuovo_t("build:stile")
    for k_ in (("Token Maker", "Anthem"), ("Vanilla", "Anthem")):
        if k_ not in tA.rete.figli:
            tA.rete.lega(k_[0], k_[1], dbr)
    tA.disegna(); root.update()
    EA = lambda x, y, st=0: type("E", (), dict(x=x - tA.cv.canvasx(0), y=y - tA.cv.canvasy(0), state=st))()
    casi.append(("di partenza le linee sono grigio perlato e sottili", len(tA._segmenti) == 2
                 and all(tA.stile_px(a_, b_)[:2] == (RS.PERLA, RS.SPESSORI[1]) for a_, b_, _p, _c in tA._segmenti)
                 and (not tA.gpu or all(tA.cv.itemcget(i_, "fill") == RS.PERLA for i_ in tA.cv.find_withtag("rete")))))
    tA.pila_di(vid_di(tA, "Anthem"))["x"] += 900; tA.disegna(); root.update()       # la freccia attraversa il foglio vuoto
    sgA = next(x for x in tA._segmenti if tA.voci[x[0]]["nome"] == "Token Maker")
    vuoto = None        # un punto della freccia fuori dalle carte: li' il clic apre la tavolozza
    for k_ in range(5, 96):
        px_ = sgA[2][0] + (sgA[3][0] - sgA[2][0]) * k_ / 100; py_ = sgA[2][1] + (sgA[3][1] - sgA[2][1]) * k_ / 100
        if tA.pezzo_a(px_, py_)[0] is None:
            vuoto = (px_, py_); break
    if vuoto:
        tA.premi_tela(EA(*vuoto)); tA.rilascia(EA(*vuoto))
        subito_ = tA._stile_pop is None         # aspetta un attimo: se arriva il doppio clic, la linea prende un dot
        fine_ = _t.time() + 0.4
        while _t.time() < fine_:
            root.update(); _t.sleep(0.01)
    casi.append(("il clic sulla freccia (fuori dalle carte) apre la tavolozza, dopo un attimo", vuoto is not None and subito_ and tA._stile_pop is not None and tA.drag is None
                 and tA._stile_pop.stile["coppia"] == ("Token Maker", "Anthem")))
    tA.stile_chiudi()
    mxA, myA = (sgA[2][0] + sgA[3][0]) / 2, (sgA[2][1] + sgA[3][1]) / 2
    tA.passa(EA(mxA, myA))
    bsA = tA.cv.bbox("rete_s")
    if bsA:
        tA.premi_tela(EA((bsA[0] + bsA[2]) / 2, (bsA[1] + bsA[3]) / 2))
    casi.append(("sulla freccia accesa, accanto alla ✕, il tondo dei colori apre la tavolozza anche sopra una carta", bsA is not None and tA._stile_pop is not None))
    popA = tA._stile_pop
    popA.stile["imposta"](colore="#d9534f"); popA.stile["imposta"](peso=3); root.update()
    rossa = [i_ for i_ in tA.cv.find_withtag("rete") if tA.cv.itemcget(i_, "fill") == "#d9534f"] if tA.gpu else ["tk"]
    casi.append(("la tavolozza cambia subito colore e importanza della linea", tA.rete.stile("Token Maker", "Anthem") == ("#d9534f", 3) and len(rossa) == 1
                 and (not tA.gpu or float(tA.cv.itemcget(rossa[0], "width")) == RS.SPESSORI[3]) and tA.rete.stile("Vanilla", "Anthem") == (RS.PERLA, 1)))
    sliders_ = [popA.stile["slider"]] if "slider" in popA.stile else []
    if sliders_:
        sliders_[0](5.0)
        fine_ = _t.time() + 0.3
        while _t.time() < fine_:
            root.update(); _t.sleep(0.01)
    linee_ = [i_ for i_ in tA.cv.find_withtag("rete") if tA.cv.itemcget(i_, "fill") == "#d9534f"] if tA.gpu else ["tk"]
    casi.append(("nella tavolozza lo slider dello spessore: la linea cambia mentre lo tiri", len(sliders_) == 1
                 and tA.rete.colore_spessore("Token Maker", "Anthem") == ("#d9534f", 5.0)
                 and (not tA.gpu or (len(linee_) == 1 and float(tA.cv.itemcget(linee_[0], "width")) == 5.0))
                 and not any(isinstance(w_, tk.Label) and w_.cget("text") == "IMPORTANCE" for w_ in tutti_widget(popA))))
    tA.stile_chiudi()
    tA.salva_tutto(); tA.chiudi()
    tA2 = nuovo_t("build:stile")
    casi.append(("riaperto, la linea ha il suo colore e il suo spessore", tA2.rete.colore_spessore("Token Maker", "Anthem") == ("#d9534f", 5.0)))
    tA2.salva_tutto(); tA2.chiudi()
    # i dot delle linee, come in Nuke (9 nov 2026): il doppio clic spezza la linea, il dot si trascina, da un dot partono altre linee dello stesso padre
    tD = nuovo_t("build:dot")
    for k_ in (("Token Maker", "Anthem"), ("Vanilla", "Anthem")):
        if k_ not in tD.rete.figli:
            tD.rete.lega(k_[0], k_[1], dbr)
    tD.pila_di(vid_di(tD, "Anthem"))["x"] += 900; tD.disegna(); root.update()
    ED = lambda x, y, st=0: type("E", (), dict(x=x - tD.cv.canvasx(0), y=y - tD.cv.canvasy(0), state=st))()
    sgD = next(x for x in tD._segmenti if tD.voci[x[0]]["nome"] == "Token Maker")
    vuotoD = next(((sgD[2][0] + (sgD[3][0] - sgD[2][0]) * k_ / 100, sgD[2][1] + (sgD[3][1] - sgD[2][1]) * k_ / 100) for k_ in range(30, 71)
                   if tD.pezzo_a(sgD[2][0] + (sgD[3][0] - sgD[2][0]) * k_ / 100, sgD[2][1] + (sgD[3][1] - sgD[2][1]) * k_ / 100)[0] is None), None)
    lontano = (vuotoD[0], vuotoD[1] + 300) if vuotoD else (0, 0)
    tD.doppio(ED(*lontano))
    casi.append(("negativa: il doppio clic nel vuoto lontano dalle linee non mette un dot", not tD.punti))
    tD.doppio(ED(*vuotoD)) if vuotoD else None
    q1 = next(iter(tD.punti), None)
    casi.append(("il doppio clic su una linea la spezza con un dot: tronco dal padre al dot, punta dal dot al figlio", q1 is not None
                 and tD.vie.get(("Token Maker", "Anthem")) == q1 and len(tD._tronchi) == 1 and len(tD._segmenti) == 2 and bool(tD.cv.find_withtag(f"p{q1}"))
                 and (not tD.gpu or len(tD.cv.find_withtag("rete")) == 3)))
    if q1 is not None:
        x1_, y1_, _r = tD.punto_xy(q1)
        tD.premi_tela(ED(x1_, y1_))
        for k_ in range(1, 5):
            tD.trascina(ED(x1_ + 20 * k_, y1_ + 15 * k_))
        vive_d = len([1 for _it, pz in tD.drag["vive"]]) if tD.drag else 0
        tD.rilascia(ED(x1_ + 80, y1_ + 60)); root.update()
        x2_, y2_, _r = tD.punto_xy(q1)
        casi.append(("il dot si trascina, e i due pezzi di linea che ci passano lo seguono", vive_d == 2 and abs(x2_ - x1_ - 80) < 1 and abs(y2_ - y1_ - 60) < 1
                     and abs(tD._tronchi[0][2][0] - x2_) < R_PUNTO + 4))
        rp = tD.rett(vid_di(tD, "Plains"))
        tD.premi_tela(ED(x2_, y2_, st=0x1)); tD.trascina(ED((rp[0] + rp[2]) / 2, (rp[1] + rp[3]) / 2)); tD.rilascia(ED((rp[0] + rp[2]) / 2, (rp[1] + rp[3]) / 2))
        root.update()
        casi.append(("Maiuscolo+trascina dal dot su una carta: una connessione nuova dello stesso padre, che passa dal dot", ("Token Maker", "Plains") in tD.rete.figli
                     and tD.vie.get(("Token Maker", "Plains")) == q1 and len(tD._tronchi) == 1 and len(tD._segmenti) == 3))
        tD.premi_tela(ED(x2_, y2_, st=0x1)); tD.trascina(ED(x2_ + 150, y2_ + 120)); tD.rilascia(ED(x2_ + 150, y2_ + 120)); root.update()
        q2 = max(tD.punti)
        casi.append(("Maiuscolo+trascina dal dot nel vuoto: un dot nuovo in catena", q2 != q1 and tD.punti[q2]["ingressi"] == [["p", q1]] and tD.fonti(q2) == {"Token Maker"}))
        tD.salva_tutto(); tD.chiudi()
        tD = nuovo_t("build:dot")
        casi.append(("riaperto, i dot e le strade delle linee ci sono", set(tD.punti) == {q1, q2} and tD.vie.get(("Token Maker", "Anthem")) == q1
                     and tD.vie.get(("Token Maker", "Plains")) == q1))
        ED = lambda x, y, st=0: type("E", (), dict(x=x - tD.cv.canvasx(0), y=y - tD.cv.canvasy(0), state=st))()
        x2_, y2_, _r = tD.punto_xy(q1)
        tD.destro(ED(x2_, y2_)); root.update()
        casi.append(("il tasto destro sul dot lo toglie: le linee vanno dritte, il dot dopo prende i suoi ingressi", q1 not in tD.punti and not tD.vie
                     and tD.punti.get(q2, {}).get("ingressi") == [["c", "Token Maker"]] and ("Token Maker", "Anthem") in tD.rete.figli))
        tD.togli_punto(q2)
        tD.doppio(ED(*(lambda s_: ((s_[2][0] + s_[3][0]) / 2, (s_[2][1] + s_[3][1]) / 2))(next(x for x in tD._segmenti
                     if (tD.voci[x[0]]["nome"], tD.voci[x[1]]["nome"]) == ("Token Maker", "Plains")))))
        q3 = tD.vie.get(("Token Maker", "Plains"))
        sgP = next(x for x in tD._segmenti if (tD.voci[x[0]]["nome"], tD.voci[x[1]]["nome"]) == ("Token Maker", "Plains"))
        tD.togli_arco(sgP)
        casi.append(("tolta la connessione col ✕, il suo dot che non serve piu' sparisce", q3 is not None and q3 not in tD.punti and ("Token Maker", "Plains") not in tD.rete.figli))
    tD.salva_tutto(); tD.chiudi()
    # il chiodo sulla freccia accesa mette il dot; il dot fa partire linee dal suo pallino d'oro e ne riceve (Autore, 10 nov 2026)
    tE = nuovo_t("build:dot2")
    if ("Token Maker", "Anthem") not in tE.rete.figli:
        tE.rete.lega("Token Maker", "Anthem", dbr)
    tE.rete.imposta_stile("Token Maker", "Anthem", colore="#d9534f", peso=2)
    tE.pila_di(vid_di(tE, "Anthem"))["x"] += 900; tE.disegna(); root.update()
    EE = lambda x, y, st=0: type("E", (), dict(x=x - tE.cv.canvasx(0), y=y - tE.cv.canvasy(0), state=st))()
    sgE = next(x for x in tE._segmenti if tE.voci[x[0]]["nome"] == "Token Maker")
    vuotoE = next(((sgE[2][0] + (sgE[3][0] - sgE[2][0]) * k_ / 100, sgE[2][1] + (sgE[3][1] - sgE[2][1]) * k_ / 100) for k_ in range(30, 71)
                   if tE.pezzo_a(sgE[2][0] + (sgE[3][0] - sgE[2][0]) * k_ / 100, sgE[2][1] + (sgE[3][1] - sgE[2][1]) * k_ / 100)[0] is None), None)
    if vuotoE:
        tE.passa(EE(*vuotoE))
    bc = tE.cv.bbox("rete_c")
    if bc:
        kc = ((bc[0] + bc[2]) / 2, (bc[1] + bc[3]) / 2)
        tE.premi_tela(EE(*kc)); tE.rilascia(EE(*kc)); root.update()
    qE = tE.vie.get(("Token Maker", "Anthem"))
    mE = ((sgE[2][0] + sgE[3][0]) / 2, (sgE[2][1] + sgE[3][1]) / 2)
    casi.append(("sulla freccia accesa il chiodo mette un dot a meta' della linea", bc is not None and qE in tE.punti
                 and abs(tE.punto_xy(qE)[0] - mE[0]) < 1 and abs(tE.punto_xy(qE)[1] - mE[1]) < 1))
    if qE in tE.punti:
        ox_, oy_ = tE.uscita_xy(qE)
        rp = tE.rett(vid_di(tE, "Plains"))
        tE.premi_tela(EE(ox_, oy_)); tE.trascina(EE((rp[0] + rp[2]) / 2, (rp[1] + rp[3]) / 2)); tE.rilascia(EE((rp[0] + rp[2]) / 2, (rp[1] + rp[3]) / 2)); root.update()
        casi.append(("dal pallino d'oro del dot parte una linea nuova (senza Maiuscolo), dello stesso padre", tE.vie.get(("Token Maker", "Plains")) == qE
                     and ("Token Maker", "Plains") in tE.rete.figli and tE.punti[qE]["x"] == tE.punti[qE]["x"]))
        vV = vid_di(tE, "Vanilla")
        bn = tE.cv.bbox(f"n{vV}")
        dx_, dy_, _r = tE.punto_xy(qE)
        tE.premi_tela(EE((bn[0] + bn[2]) / 2, (bn[1] + bn[3]) / 2)); tE.trascina(EE(dx_, dy_)); tE.rilascia(EE(dx_, dy_)); root.update()
        casi.append(("il dot riceve piu' frecce: Vanilla entra accanto a Token Maker, quello che esce vale per tutti e due, col suo colore",
                     tE.punti[qE]["ingressi"] == [["c", "Token Maker"], ["c", "Vanilla"]] and tE.vie.get(("Vanilla", "Anthem")) == qE
                     and tE.vie.get(("Vanilla", "Plains")) == qE and tE.vie.get(("Token Maker", "Anthem")) == qE and ("Token Maker", "Plains") in tE.rete.figli
                     and tE.rete.stile("Vanilla", "Anthem") == ("#d9534f", 2) and len(tE._tronchi) == 2
                     and len([x for x in tE._segmenti if tE.voci[x[1]]["nome"] == "Anthem"]) == 1))
        tE.premi_tela(EE((bn[0] + bn[2]) / 2, (bn[1] + bn[3]) / 2)); tE.trascina(EE(dx_ + 9, dy_ + 9)); tE.trascina(EE(dx_, dy_)); tE.rilascia(EE(dx_, dy_)); root.update()
        casi.append(("negativa: la stessa carta non entra due volte nello stesso dot", len(tE.punti[qE]["ingressi"]) == 2))
        prima_v = dict(tE.vie)
        ox_, oy_ = tE.uscita_xy(qE)
        tE.premi_tela(EE(ox_, oy_)); tE.trascina(EE(dx_ + 20, dy_ + 20)); tE.trascina(EE(dx_, dy_)); tE.rilascia(EE(dx_, dy_)); root.update()
        nego1 = tE.vie == prima_v and len(tE.punti[qE]["ingressi"]) == 2
        tE.premi_tela(EE(ox_, oy_, st=0x1)); tE.trascina(EE(dx_ + 160, dy_ + 140)); tE.rilascia(EE(dx_ + 160, dy_ + 140)); root.update()
        q2E = max(tE.punti)
        o2x, o2y = tE.uscita_xy(q2E)
        dx_, dy_, _r = tE.punto_xy(qE)
        tE.premi_tela(EE(o2x, o2y)); tE.trascina(EE(o2x + 30, o2y - 30)); tE.trascina(EE(dx_, dy_)); tE.rilascia(EE(dx_, dy_)); root.update()
        casi.append(("negativa: un dot non riceve da se stesso ne' da un dot dopo di lui (giro chiuso)", nego1 and q2E != qE and len(tE.punti[qE]["ingressi"]) == 2
                     and tE.punti[q2E]["ingressi"] == [["p", qE]]))
        # la tavolozza e la ✕ su un'uscita del dot valgono per tutte le connessioni che ci passano; la ✕ su un ingresso toglie solo quello
        sgO = next(x for x in tE._segmenti if tE.voci[x[1]]["nome"] == "Anthem")
        popO = tE.stile_apri(sgO); popO.stile["imposta"](colore="#24baff"); tE.stile_chiudi()
        casi.append(("la tavolozza su un'uscita del dot colora le connessioni di tutti i suoi ingressi", tE.rete.stile("Token Maker", "Anthem")[0] == "#24baff"
                     and tE.rete.stile("Vanilla", "Anthem")[0] == "#24baff"))
        trV = next((x for x in tE._tronchi if x[3] == ("c", "Vanilla")), None)
        vuotoV = next(((trV[1][0] + (trV[2][0] - trV[1][0]) * k_ / 100, trV[1][1] + (trV[2][1] - trV[1][1]) * k_ / 100) for k_ in range(25, 76)
                       if tE.pezzo_a(trV[1][0] + (trV[2][0] - trV[1][0]) * k_ / 100, trV[1][1] + (trV[2][1] - trV[1][1]) * k_ / 100)[0] is None), None) if trV else None
        if vuotoV:
            tE.passa(EE(*vuotoV))
        bx_t = tE.cv.bbox("rete_xt")
        if bx_t:
            tE.premi_tela(EE((bx_t[0] + bx_t[2]) / 2, (bx_t[1] + bx_t[3]) / 2)); tE.rilascia(EE((bx_t[0] + bx_t[2]) / 2, (bx_t[1] + bx_t[3]) / 2)); root.update()
        casi.append(("la ✕ su un ingresso del dot toglie quell'ingresso e le sue connessioni, le altre restano", bx_t is not None
                     and tE.punti[qE]["ingressi"] == [["c", "Token Maker"]] and ("Vanilla", "Anthem") not in tE.rete.figli and ("Vanilla", "Plains") not in tE.rete.figli
                     and tE.vie.get(("Token Maker", "Anthem")) == qE and ("Token Maker", "Plains") in tE.rete.figli))
        sgO = next(x for x in tE._segmenti if tE.voci[x[1]]["nome"] == "Anthem")
        tE.togli_arco(sgO)
        casi.append(("la ✕ su un'uscita del dot toglie quella connessione, il dot resta per le altre", ("Token Maker", "Anthem") not in tE.rete.figli
                     and qE in tE.punti and tE.vie.get(("Token Maker", "Plains")) == qE))
    tE.salva_tutto(); tE.chiudi()
    # una linea corta: i pulsantini ci sono tutti, uno accanto all'altro, fuori dai pallini; la linea resta accesa mentre il mouse va verso di loro
    tC = nuovo_t("build:corta")
    if ("Vanilla", "Anthem") not in tC.rete.figli:
        tC.rete.lega("Vanilla", "Anthem", dbr)
    p_v_, p_an_ = tC.pila_di(vid_di(tC, "Vanilla")), tC.pila_di(vid_di(tC, "Anthem"))
    p_an_["x"], p_an_["y"] = p_v_["x"] + 70, p_an_["y"] + tC.posizioni(p_v_)[-1] - tC.posizioni(p_an_)[-1]      # accanto, con la base alla stessa altezza
    tC.disegna(); root.update()
    EC = lambda x, y, st=0: type("E", (), dict(x=x - tC.cv.canvasx(0), y=y - tC.cv.canvasy(0), state=st))()
    sgC = next(x for x in tC._segmenti if tC.voci[x[0]]["nome"] == "Vanilla")
    lungC = ((sgC[3][0] - sgC[2][0]) ** 2 + (sgC[3][1] - sgC[2][1]) ** 2) ** 0.5
    mC = ((sgC[2][0] + sgC[3][0]) / 2, (sgC[2][1] + sgC[3][1]) / 2)
    tC.passa(EC(*mC))
    bxs = {g_: tC.cv.bbox(g_) for g_ in ("rete_c", "rete_x", "rete_s")}
    tocca = lambda a_, b_: a_[0] < b_[2] and b_[0] < a_[2] and a_[1] < b_[3] and b_[1] < a_[3]
    nodi_ = [tC.cv.bbox(f"n{v_}") for v_ in (sgC[0], sgC[1]) if tC.cv.bbox(f"n{v_}")]
    casi.append(("su una linea corta i pulsantini ci sono tutti, separati, fuori dai pallini", lungC < 90 and all(bxs.values())
                 and not any(tocca(bxs[a_], bxs[b_]) for a_, b_ in (("rete_c", "rete_x"), ("rete_x", "rete_s"), ("rete_c", "rete_s")))
                 and not any(tocca(b_, n_) for b_ in bxs.values() for n_ in nodi_)))
    cs_ = ((bxs["rete_s"][0] + bxs["rete_s"][2]) / 2, (bxs["rete_s"][1] + bxs["rete_s"][3]) / 2) if bxs["rete_s"] else mC
    accesa_ = True
    for k_ in range(1, 7):
        tC.passa(EC(mC[0] + (cs_[0] - mC[0]) * k_ / 6, mC[1] + (cs_[1] - mC[1]) * k_ / 6))
        accesa_ = accesa_ and bool(tC.cv.find_withtag("rete_s"))
    casi.append(("andando verso la barretta la linea resta accesa, fino al pulsante dei colori", accesa_))
    tC.passa(EC(mC[0] + 400, mC[1] + 400))
    casi.append(("negativa: lontano dalla linea e dalla barretta si spegne", not tC.cv.find_withtag("rete_s")))
    # un dot che cade sopra una carta (il centro di una linea fra le basi di padre e figlio) sta sopra la carta e si prende col clic
    qC = tC.inserisci_punto(*mC)
    rvC = tC.rett(vid_di(tC, "Vanilla"))
    tC.punti[qC]["x"], tC.punti[qC]["y"] = ((rvC[0] + rvC[2]) / 2) / tC.zoom, ((rvC[1] + rvC[3]) / 2 - tC.oy("main")) / tC.zoom
    tC.disegna(); root.update()
    tutti_C = tC.cv.find_all()
    ptC = tC.punto_xy(qC)
    casi.append(("un dot sopra una carta sta sopra la carta e si prende col clic; le linee restano sotto", tutti_C.index(tC.cv.find_withtag(f"p{qC}")[0]) >
                 max(tutti_C.index(i_) for i_ in tC.cv.find_withtag("carta")) and tC.pezzo_a(ptC[0], ptC[1]) == ("punto", qC)
                 and all(tutti_C.index(i_) < min(tutti_C.index(j_) for j_ in tC.cv.find_withtag("carta")) for i_ in tC.cv.find_withtag("rete"))))
    tC.salva_tutto(); tC.chiudi()
    # Grid snap: libero mentre trascini, sulla griglia quando lasci; la spunta lo spegne, e si ricorda
    tG = nuovo_t("build:griglia", griglia=True)
    EG = lambda x, y, st=0: type("E", (), dict(x=x - tG.cv.canvasx(0), y=y - tG.cv.canvasy(0), state=st))()
    va_ = vid_di(tG, "Vanilla")
    rv_ = tG.rett(va_)
    cxv, cyv = (rv_[0] + rv_[2]) / 2, (rv_[1] + rv_[3]) / 2
    b0_ = tG.cv.bbox(f"c{va_}")
    tG.premi_tela(EG(cxv, cyv)); tG.trascina(EG(cxv + 37, cyv + 11)); tG.trascina(EG(cxv + 337, cyv + 211))
    b1_ = tG.cv.bbox(f"c{va_}")
    tG.rilascia(EG(cxv + 337, cyv + 211)); root.update()
    plv = tG.pila_di(va_)
    # sulla griglia a quadratini (12 nov 2026): 12 per colonna, 2 per passo verticale
    sulla = lambda x_, y_: abs(((x_ - MARGINE) / CELLA_X) - round((x_ - MARGINE) / CELLA_X)) < 1e-6 and abs(y_ / CELLA_Y - round(y_ / CELLA_Y)) < 1e-6
    casi.append(("la griglia a quadratini: 12 per colonna e 2 per passo, quasi quadrati; la colonna di prima e' fatta degli stessi quadratini",
                 abs(CELLE_X * CELLA_X - PASSO_X) < 1e-9 and abs(CELLE_Y * CELLA_Y - PASSO_Y) < 1e-9 and 12 <= CELLA_X <= 15 and 12 <= CELLA_Y <= 15
                 and a_griglia(MARGINE + 3 * CELLA_X + 5, 4 * CELLA_Y - 5) == (MARGINE + 3 * CELLA_X, 4 * CELLA_Y)))
    casi.append(("Grid snap: mentre trascini la carta segue il mouse al pixel, lasciata va sulla griglia", b1_[0] - b0_[0] == 337 and b1_[1] - b0_[1] == 211
                 and sulla(plv["x"], plv["y"])))
    p_tm, p_an = tG.pila_di(vid_di(tG, "Token Maker")), tG.pila_di(vid_di(tG, "Anthem"))
    if p_tm is plv:
        p_tm = tG.pila_di(vid_di(tG, "Plains"))
    tG.sel = [p_tm, p_an]
    rel = (p_an["x"] - p_tm["x"], p_an["y"] - p_tm["y"])
    ra_ = tG.rett(vid_di(tG, "Anthem")); cxa_, cya_ = (ra_[0] + ra_[2]) / 2, (ra_[1] + ra_[3]) / 2
    tG.premi_tela(EG(cxa_, cya_)); tG.trascina(EG(cxa_ + 100, cya_ + 50)); tG.trascina(EG(cxa_ + 213, cya_ + 97)); tG.rilascia(EG(cxa_ + 213, cya_ + 97)); root.update()
    casi.append(("Grid snap: un gruppo lasciato tiene le sue distanze, col primo sulla griglia", (p_an["x"] - p_tm["x"], p_an["y"] - p_tm["y"]) == rel
                 and sulla(*(lambda q_: (q_["x"], q_["y"]))(tG.sel[0] if tG.sel else p_tm))))
    tG.vuota_sel()
    # una carta lasciata accanto a una pila (non sopra): la cella piu' vicina e' quella della pila, quindi va nella libera accanto, non sopra
    pan_ = max((q_ for q_ in tG.pile if q_["zona"] == "main" and q_["carte"] and va_ not in q_["carte"]), key=lambda q_: q_["x"])     # la pila piu' a destra
    rp_ = tG.ingombro_px(pan_)
    plv = tG.pila_di(va_); rv_ = tG.rett(va_)
    cxv, cyv = rv_[2] - 4, (rv_[1] + rv_[3]) / 2        # la carta presa dal bordo destro
    destx = rp_[0] + 70 * tG.zoom + (cxv - rv_[0])      # lasciata col bordo sinistro 70 pixel dentro la colonna della pila: il puntatore e' fuori dalla pila,
    desty = rp_[1] + (cyv - rv_[1]) + 5                 # ma la cella piu' vicina e' quella della pila
    tG.premi_tela(EG(cxv, cyv)); tG.trascina(EG((cxv + destx) / 2, (cyv + desty) / 2)); tG.trascina(EG(destx, desty)); tG.rilascia(EG(destx, desty)); root.update()
    plv = tG.pila_di(va_)
    tocca_ = lambda a_, b_: a_[0] < b_[2] - 1 and b_[0] < a_[2] - 1 and a_[1] < b_[3] - 1 and b_[1] < a_[3] - 1
    casi.append(("Grid snap: lasciata accanto a una pila, la carta va nella cella libera piu' vicina, non sopra la pila", plv is not pan_ and len(plv["carte"]) == 1
                 and not any(tocca_(tG.ingombro(plv), tG.ingombro(q_)) for q_ in tG.pile if q_ is not plv and q_["zona"] == "main" and q_["carte"])
                 and sulla(plv["x"], plv["y"]) and abs(plv["x"] - pan_["x"]) >= BASE_W - 1))
    occ_ = [q_ for q_ in tG.pile if q_["zona"] == "main" and q_["carte"]]
    lib_x, lib_y = tG.cella_libera("main", -2000, -2000, 1)
    casi.append(("negativa: dove non c'e' niente la cella e' quella piu' vicina, senza spostamenti", (lib_x, lib_y) == a_griglia(-2000, -2000) and occ_))
    legata_ = bool(tG.b_griglia.bind("<Button-1>"))        # la finestra di prova non e' mappata: si chiama quello che il clic chiama
    tG.cambia_griglia(); root.update()
    plv = tG.pila_di(va_); rv_ = tG.rett(va_); cxv, cyv = (rv_[0] + rv_[2]) / 2, (rv_[1] + rv_[3]) / 2
    x_prima, y_prima = plv["x"], plv["y"]
    tG.premi_tela(EG(cxv, cyv)); tG.trascina(EG(cxv + 50, cyv + 20)); tG.trascina(EG(cxv + 101, cyv + 43)); tG.rilascia(EG(cxv + 101, cyv + 43)); root.update()
    plv = tG.pila_di(va_)
    casi.append(("negativa: Grid snap spento, la carta resta dove la lasci", legata_ and tG.griglia is False and abs(plv["x"] - x_prima - 101) <= 1
                 and abs(plv["y"] - y_prima - 43) <= 1 and not sulla(plv["x"], plv["y"])))
    # la carta in cima tirata di poco fuori dalla sua pila (il mouse resta sopra la pila): se ne stacca, esattamente dove la lasci (Autore, 10 nov 2026:
    # «quando sposto delle carte in un punto senza il grid snap scattano spostandosi in un punto leggermente differente»: tornava sulla pila)
    multi_ = [q_ for q_ in tG.pile if q_["zona"] == "main" and len(q_["carte"]) >= 2]
    if not multi_:
        q0_, q1_ = [q_ for q_ in tG.pile if q_["zona"] == "main" and q_["carte"]][:2]
        q0_["carte"].extend(q1_["carte"]); tG.pile.remove(q1_); tG.disegna(); root.update()
        multi_ = [q0_]
    pm_ = multi_[0]; vc_ = pm_["carte"][-1]; rc_ = tG.rett(vc_)
    px_, py_ = rc_[0] + 30, rc_[1] + 40
    tG.premi_tela(EG(px_, py_)); tG.trascina(EG(px_ + 30, py_ + 10)); tG.trascina(EG(px_ + 61, py_ + 23))
    vecchio_ = tG.bersaglio(px_ + 61, py_ + 23, dict(da=None, prese=[]))       # come lo vedeva il rilascio fino al 10 nov: il trascinamento gia' chiuso
    tG.rilascia(EG(px_ + 61, py_ + 23)); root.update()
    rd_ = tG.rett(vc_)
    casi.append(("Grid snap spento: la carta in cima tirata di poco fuori dalla sua pila se ne stacca, al pixel dove la lasci", tG.pila_di(vc_) is not pm_
                 and abs(rd_[0] - rc_[0] - 61) < 0.05 and abs(rd_[1] - rc_[1] - 23) < 0.05))
    casi.append(("negativa: senza il trascinamento la pila di partenza sotto il mouse contava come bersaglio (la carta tornava indietro)", vecchio_ is pm_))
    tG.salva_tutto(); tG.chiudi()
    tG2 = TavoloCarte(tk, F, root, "Rete", {"Vanilla": 4}, {}, carte_db=dbr, chiave="build:griglia2", file_tavoli=ft, file_mazzi=fm, file_rete=fr, fuori=True, limite=lim)
    root.update()
    casi.append(("la spunta si ricorda per tutti i mazzi", tG2.griglia is False))
    tG2.cambia_griglia(True)
    tG2.salva_tutto(); tG2.chiudi()
    # il Board in sola lettura (aperto dalla finestra del mazzo): la disposizione di edit, niente strumenti, niente salvato
    tS0 = nuovo_t("build:sola")
    for k_ in (("Token Maker", "Anthem"),):
        if k_ not in tS0.rete.figli:
            tS0.rete.lega(k_[0], k_[1], dbr)
    tS0.sel = [tS0.pila_di(vid_di(tS0, "Anthem"))]; tS0.crea_etichetta("Finisher")
    tS0.disegna(); root.update()
    strumenti = lambda t_: [g_ for g_ in ("nodo", "ctrl", "scambia", "label_x", "label_l", "label_m", "label_r") if t_.cv.find_withtag(g_)]
    con_strumenti = strumenti(tS0)
    tS0.salva_tutto(); tS0.chiudi()
    prima_file = json.dumps(carica_tavoli(ft).get("build:sola"), sort_keys=True)
    tS = TavoloCarte(tk, F, root, "Rete", {"Token Maker": 4, "Anthem": 2, "Vanilla": 4, "Plains": 10}, {"Side Anthem": 1}, carte_db=dbr, chiave="build:sola",
                     file_tavoli=ft, file_mazzi=fm, file_rete=fr, fuori=True, limite=lim, modificabile=("build", "x"), sola_lettura=True)
    root.update()
    ES = lambda x, y, st=0: type("E", (), dict(x=x - tS.cv.canvasx(0), y=y - tS.cv.canvasy(0), state=st))()
    casi.append(("sola lettura: la disposizione e le connessioni di edit ci sono, gli strumenti no", len(con_strumenti) >= 5 and not strumenti(tS)
                 and len(tS.etichette) == 1 and len(tS._segmenti) == 1 and not tS.modifica and tS.b_griglia is None and "view only" in tS.aiuto.cget("text")))
    pa_ = tS.pila_di(vid_di(tS, "Anthem")); xy_ = (pa_["x"], pa_["y"])
    ra_ = tS.rett(vid_di(tS, "Anthem")); cxs, cys = (ra_[0] + ra_[2]) / 2, (ra_[1] + ra_[3]) / 2
    prima_mazzi = open(fm, encoding="utf-8").read() if os.path.exists(fm) else ""
    # in sola lettura le carte si spostano (Autore, 10 nov 2026: «le carte possono cmq essere spostate e trascinate in giro»), il resto no
    tS.premi_tela(ES(cxs, cys)); tS.trascina(ES(cxs + 200, cys + 100)); tS.rilascia(ES(cxs + 200, cys + 100))
    pa2 = tS.pila_di(vid_di(tS, "Anthem"))
    casi.append(("sola lettura: la carta si trascina e resta nel mazzo", (pa2["x"], pa2["y"]) != xy_ and tS.voci[vid_di(tS, "Anthem")]["zona"] == "main"))
    ra2 = tS.rett(vid_di(tS, "Anthem")); cx2, cy2 = (ra2[0] + ra2[2]) / 2, (ra2[1] + ra2[3]) / 2
    xy2 = (pa2["x"], pa2["y"])
    tS.premi_tela(ES(cx2, cy2)); tS.trascina(ES(cx2, tS.hs / 2)); tS.rilascia(ES(cx2, tS.hs / 2))
    pa3 = tS.pila_di(vid_di(tS, "Anthem"))
    casi.append(("sola lettura: lasciata nella sideboard torna al suo posto", tS.voci[vid_di(tS, "Anthem")]["zona"] == "main" and (pa3["x"], pa3["y"]) == xy2))
    tS.premi_tela(ES(cxs - 900, cys)); tS.trascina(ES(cxs - 600, cys + 300)); tS.rilascia(ES(cxs - 600, cys + 300))
    tS.doppio(ES(cx2, cy2)); tS.destro(ES(cx2, cy2)); root.update()
    if tS.clic is not None:
        tS.cv.after_cancel(tS.clic); tS.clic = None
    casi.append(("negativa: in sola lettura il riquadro, il doppio clic e il tasto destro non cambiano niente", not tS.sel
                 and tS.voci[vid_di(tS, "Anthem")]["zona"] == "main" and len(tS.rete.figli) == 1 and not tS.cambia_copie(vid_di(tS, "Anthem"), +1)))
    casi.append(("negativa: in sola lettura niente foglietto vuoto e l'editor delle note non si apre", not tS.cv.find_withtag("nota_n") and tS.editor_nota("c", "Anthem") is None))
    tS.zoom_a(1.3); tS.chiudi()
    dopo_ = carica_tavoli(ft).get("build:sola") or {}
    casi.append(("sola lettura: si salva la posizione nuova, label e mazzo restano quelli di edit",
                 any(["Anthem", 2] in pl_["carte"] and (pl_["x"], pl_["y"]) == xy2 for pl_ in dopo_.get("pile", []))
                 and dopo_.get("etichette") == (json.loads(prima_file) or {}).get("etichette")
                 and (open(fm, encoding="utf-8").read() if os.path.exists(fm) else "") == prima_mazzi))
    tN = TavoloCarte(tk, F, root, "Rete", {"Token Maker": 4, "Anthem": 2, "Vanilla": 4, "Plains": 10}, {"Side Anthem": 1}, carte_db=dbr, chiave="build:sola",
                     file_tavoli=ft, file_mazzi=fm, file_rete=fr, fuori=True, limite=lim, modificabile=("build", "x"), sola_lettura=True)
    tN.sposta = False       # come con All accounts: niente si sposta
    root.update()
    EN = lambda x, y, st=0: type("E", (), dict(x=x - tN.cv.canvasx(0), y=y - tN.cv.canvasy(0), state=st))()
    pn = tN.pila_di(vid_di(tN, "Anthem")); xyn = (pn["x"], pn["y"])
    rn = tN.rett(vid_di(tN, "Anthem")); cxn, cyn = (rn[0] + rn[2]) / 2, (rn[1] + rn[3]) / 2
    tN.premi_tela(EN(cxn, cyn)); tN.trascina(EN(cxn + 200, cyn + 100)); tN.rilascia(EN(cxn + 200, cyn + 100)); root.update()
    if tN.clic is not None:
        tN.cv.after_cancel(tN.clic); tN.clic = None
    pn2 = tN.pila_di(vid_di(tN, "Anthem"))
    casi.append(("negativa: senza il permesso di spostare (All accounts) la carta resta ferma", (pn2["x"], pn2["y"]) == xyn))
    tN.salva_tutto(); tN.chiudi()
    # l'outliner, A e F, le carte nuove isolate, comandi e outliner che si chiudono (10 nov 2026)
    tO = nuovo_t("build:outliner")
    tO.cv.winfo_width = lambda: 1000; tO.cv.winfo_height = lambda: 700
    tO.disegna(); root.update()
    righe_o = list(tO._out_righe)
    nomi_o = [tO.voci[v_]["nome"] for _a, _b, v_ in righe_o]
    y_o = {tO.voci[v_]["nome"]: (a_, b_) for a_, b_, v_ in righe_o}
    testi_o = [tO.out_cv.itemcget(i_, "text") for i_ in tO.out_cv.find_all() if tO.out_cv.type(i_) == "text"]
    casi.append(("l'outliner: le carte sopra, le terre sotto, poi la sideboard, staccate da un piccolo spazio, con le copie", nomi_o[:3] == ["Token Maker", "Vanilla", "Anthem"]
                 and nomi_o[3] == "Plains" and nomi_o[4] == "Side Anthem" and y_o["Plains"][0] - y_o["Anthem"][1] == 9 and y_o["Vanilla"][0] == y_o["Token Maker"][1]
                 and "10" in testi_o and "SIDEBOARD" in testi_o))
    EO = lambda y_: type("E", (), dict(x=20, y=y_, state=0))()
    tO.scegli_outliner(EO((y_o["Anthem"][0] + y_o["Anthem"][1]) / 2))
    van = vid_di(tO, "Anthem")
    casi.append(("clic su una riga dell'outliner: la carta e' scelta, anche sul Board", tO.sel_carta == van and bool(tO.cv.find_withtag("sel_c"))))
    tasto_ = lambda k_: tO.tasto(type("E", (), dict(keysym=k_))())
    tasto_("f"); root.update()
    ra_ = tO.ingombro_px(tO.pila_di(van))
    centro_ = ((ra_[0] + ra_[2]) / 2, (ra_[1] + ra_[3]) / 2)
    # al centro dell'area libera (sotto la fascia, fuori da HUD e comandi: 13 nov 2026), non piu' al centro di tutta la tela
    casi.append(("F: il Board porta sulla carta scelta, al centro dell'area libera", tO.zoom > 1.0 and tO.in_vista(tO.rett_selezione())
                 and any(abs(centro_[0] - 4 - tO.cv.canvasx((a_[0] + a_[2]) / 2)) < 12 and abs(centro_[1] + 9 - tO.cv.canvasy((a_[1] + a_[3]) / 2)) < 12
                         for a_ in tO.aree_libere())))
    tasto_("a"); root.update()
    dentro_v = all(tO.cv.canvasx(0) <= r_[0] and r_[2] <= tO.cv.canvasx(1000) and tO.cv.canvasy(0) <= r_[1] and r_[3] <= tO.cv.canvasy(700)
                   for r_ in (tO.ingombro_px(pl_) for pl_ in tO.pile if pl_["zona"] == "main"))
    casi.append(("A: tutta la rete nella finestra", dentro_v))
    tO.vuota_sel(); z_ = tO.zoom
    casi.append(("negativa: F senza niente scelto non muove niente, e lo dice", tasto_("f") is False and tO.zoom == z_ and "F frames" in tO.aiuto.cget("text")))
    w_, h_, _o, _p = misure(1.0)
    destra_ = max(pl_["x"] + w_ for pl_ in tO.pile if pl_["zona"] == "main")
    tO.allinea({"Token Maker": 4, "Anthem": 2, "Vanilla": 4, "Plains": 10, "Nuova": 1}, {"Side Anthem": 1})
    tO.allinea({"Token Maker": 4, "Anthem": 2, "Vanilla": 4, "Plains": 10, "Nuova": 1, "Altra": 2}, {"Side Anthem": 1})
    pn_, pa2_ = tO.pila_di(vid_di(tO, "Nuova")), tO.pila_di(vid_di(tO, "Altra"))
    casi.append(("le carte aggiunte (doppio clic, ricerca) in uno spazio isolato a destra, una sotto l'altra", pn_["carte"] == [vid_di(tO, "Nuova")]
                 and pn_["x"] >= destra_ + PASSO_X - 1 and pa2_["x"] == pn_["x"] and pa2_["y"] > pn_["y"] and len(pa2_["carte"]) == 1))
    v_x = tO.nuova_voce("Posata", "main", 1, xy=(100, 300))
    casi.append(("negativa: una carta lasciata in un punto (trascinata dalla Collection) va li', non nello spazio isolato", tO.pila_di(v_x)["x"] == 100))
    casi.append(("la lista dei comandi parte chiusa, con la testa azzurra", not tO.comandi_aperti and tO.f_comandi.winfo_manager() == ""
                 and tO.aiuto.master.cget("bg") == C["accento"] and tO.b_comandi.cget("text") == "▸"))
    tO.disegna()
    curva_ = tO.curva()
    testi_i = [tO.cv.itemcget(i_, "text") for i_ in tO.cv.find_withtag("hud") if tO.cv.type(i_) == "text"]
    r_h = tO._hud_rect
    casi.append(("l'HUD in alto a destra: il totale nella testa azzurra, la curva di mana", r_h is not None and r_h[2] == 1000 - 14 and r_h[1] == 12
                 and curva_[2] == 8 and curva_[3] == 2 and curva_[0] == 4 and sum(curva_) == 14 and "DECK · 24 CARDS" in testi_i
                 and any(t_.startswith("14 spells") for t_ in testi_i) and len(tO.cv.find_withtag("curva")) == 3 and not hasattr(tO, "l_conti")
                 and any(tO.cv.itemcget(i_, "fill") == C["accento"] for i_ in tO.cv.find_withtag("hud_testa") if tO.cv.type(i_) == "rectangle")))
    pil_f = DG._icona(("hud_fondo", INFO_L, INFO_H), lambda: None)
    import tela_gpu as TG_
    sorg_ = TG_.SORGENTI.get(str(pil_f))
    casi.append(("lo sfondo dell'HUD e' semitrasparente", sorg_ is not None and 100 <= sorg_.getpixel((INFO_L // 2, INFO_H // 2))[3] < 230))
    v0_ = (tO.cv.canvasx(0), tO.cv.canvasy(0))
    tO.cv.scan_mark(0, 0); tO.cv.scan_dragto(-150, -90, gain=1)
    fine_ = _t.time() + 0.3
    while _t.time() < fine_:
        root.update(); _t.sleep(0.01)
    bb_t = tO.cv.bbox(tO.cv.find_withtag("hud_testa")[0])
    vis_ = (bb_t[0] - (0 if tO.gpu else tO.cv.canvasx(0)), bb_t[1] - (0 if tO.gpu else tO.cv.canvasy(0)))
    casi.append(("spostato il foglio, l'HUD resta nell'angolo della finestra", (tO.cv.canvasx(0), tO.cv.canvasy(0)) != v0_ and abs(vis_[0] - r_h[0]) < 1.5 and abs(vis_[1] - r_h[1]) < 1.5))
    ET = lambda x_, y_: type("E", (), dict(x=x_, y=y_, state=0))()
    n_sel = len(tO.sel)
    tO.premi_tela(ET(r_h[0] + 40, r_h[1] + 8)); tO.rilascia(ET(r_h[0] + 40, r_h[1] + 8))
    chiuso_ = not tO.info_aperto and not tO.cv.find_withtag("curva") and tO._hud_rect[3] - tO._hud_rect[1] == TESTA_HUD
    tO.premi_tela(ET(r_h[0] + 40, r_h[1] + 8)); tO.rilascia(ET(r_h[0] + 40, r_h[1] + 8))
    casi.append(("la testa dell'HUD lo chiude e lo riapre, come i comandi", chiuso_ and tO.info_aperto and len(tO.cv.find_withtag("curva")) == 3))
    tO.premi_tela(ET(r_h[0] + 40, r_h[1] + 60)); tO.trascina(ET(r_h[0] - 200, r_h[1] + 260)); tO.rilascia(ET(r_h[0] - 200, r_h[1] + 260))
    casi.append(("negativa: un clic sul corpo dell'HUD non arriva al foglio (niente riquadro, niente carta)", tO.banda is None and len(tO.sel) == n_sel and tO.drag is None))
    tO.apri_comandi(True)
    tO.apri_comandi(False); tO.apri_outliner(False); root.update()
    chiusi_ = tO.f_comandi.winfo_manager() == "" and tO.out_corpo.winfo_manager() == "" and tO.b_out.cget("text") == "▶" and tO.b_comandi.cget("text") == "▸"
    tO.salva_tutto(); tO.chiudi()
    tO2 = nuovo_t("build:outliner")
    casi.append(("l'outliner chiuso resta chiuso alla riapertura; i comandi ripartono comunque chiusi", chiusi_ and not tO2.comandi_aperti and not tO2.outliner_aperto
                 and tO2.out_corpo.winfo_manager() == ""))
    tO2.fin.transient(""); tO2.fin.deiconify(); root.update()
    on_ = tO2.tutta_pagina(); root.update()
    pieno_ = tO2.fin.state() == "zoomed" and "Restore" in tO2.b_pagina.testo()
    tO2.tutta_pagina(False); root.update()
    casi.append(("Full page: il Board a tutto schermo e indietro", on_ and pieno_ and tO2.fin.state() == "normal" and "Full page" in tO2.b_pagina.testo()))
    tO2.apri_comandi(True); tO2.apri_outliner(True); root.update()
    casi.append(("e si riaprono", tO2.f_comandi.winfo_manager() == "grid" and tO2.out_corpo.winfo_manager() == "pack" and tO2.b_out.cget("text") == "◀"))
    tO2.salva_tutto(); tO2.chiudi()
    def frecce_sotto(t_):
        """Quante frecce padre -> figlio passano sopra una carta che si vede (un punto della freccia dentro una carta, a 2 pixel dai bordi)."""
        rr = [r_ for r_ in (t_.rett(v) for pl in t_.pile if pl["zona"] == "main" for v in pl["carte"]) if r_]
        n_ = 0
        for _a, _b, p0, p1 in t_._segmenti:
            pts = [(p0[0] + (p1[0] - p0[0]) * i / 60, p0[1] + (p1[1] - p0[1]) * i / 60) for i in range(61)]
            n_ += any(r_[0] + 2 < x < r_[2] - 2 and r_[1] + 2 < y < r_[3] - 2 for x, y in pts for r_ in rr)
        return n_

    # Arrange network (13 nov 2026 sera: Network, da sinistra a destra): i padri a sinistra dei figli, i giri chiusi rotti, le carte senza connessioni sotto per costo
    tR = nuovo_t("build:rete_ord")
    pile_prima = [(q["x"], q["y"], list(q["carte"])) for q in tR.pile]
    casi.append(("negativa: senza connessioni Arrange network non tocca niente, e lo dice", tR.disponi_rete() == 0
                 and [(q["x"], q["y"], list(q["carte"])) for q in tR.pile] == pile_prima and "No connections" in tR.aiuto.cget("text")))
    for k_ in (("Token Maker", "Anthem"), ("Anthem", "Plains"), ("Plains", "Token Maker")):
        if k_ not in tR.rete.figli:
            tR.rete.lega(k_[0], k_[1], dbr)
    side_prima = [(q["x"], q["y"], list(q["carte"])) for q in tR.pile if q["zona"] != "main"]
    n_r = tR.disponi_rete(); root.update()
    yR = {n_: tR.pila_di(vid_di(tR, n_))["y"] for n_ in ("Token Maker", "Anthem", "Plains", "Vanilla")}
    xR = {n_: tR.pila_di(vid_di(tR, n_))["x"] for n_ in ("Token Maker", "Anthem", "Plains")}
    casi.append(("Network: i padri a sinistra dei figli con una colonna vuota in mezzo, ogni livello una riga piu' giu' (frecce distinte), il giro chiuso rotto",
                 n_r == 3 and xR["Anthem"] - xR["Token Maker"] == 2 * PASSO_X and xR["Plains"] - xR["Anthem"] == 2 * PASSO_X
                 and yR["Anthem"] - yR["Token Maker"] == PASSO_Y and yR["Plains"] - yR["Anthem"] == PASSO_Y
                 and all(len(tR.pila_di(vid_di(tR, n_))["carte"]) == 1 for n_ in ("Token Maker", "Anthem", "Plains"))))
    casi.append(("Network: nessuna freccia passa sopra una carta (la catena corre sotto le carte)", bool(tR._segmenti) and frecce_sotto(tR) == 0))
    # la negativa: la rete di prima, coi padri sopra i figli, fa passare ogni freccia dietro la carta del figlio, e il controllo lo vede
    for i_, n_ in enumerate(("Token Maker", "Anthem", "Plains")):
        tR.pila_di(vid_di(tR, n_)).update(x=MARGINE, y=i_ * 9 * PASSO_Y)
    tR.disegna(); root.update()
    casi.append(("negativa: coi padri sopra i figli le frecce passano dietro le carte, e il controllo le conta", frecce_sotto(tR) >= 2))
    tR.disponi_rete(); root.update()
    casi.append(("le carte senza connessioni sotto la rete, sideboard ferma, connessioni intatte", yR["Vanilla"] > yR["Plains"]
                 and [(q["x"], q["y"], list(q["carte"])) for q in tR.pile if q["zona"] != "main"] == side_prima
                 and set(tR.rete.figli) == {("Token Maker", "Anthem"), ("Anthem", "Plains"), ("Plains", "Token Maker")}))
    disp_ = sorted((q["x"], q["y"], tuple(tR.voci[c_]["nome"] for c_ in q["carte"])) for q in tR.pile)
    tR.disponi_rete()
    casi.append(("rifatto, da' la stessa disposizione", sorted((q["x"], q["y"], tuple(tR.voci[c_]["nome"] for c_ in q["carte"])) for q in tR.pile) == disp_))
    tR.salva_tutto(); tR.chiudi()
    tR2 = nuovo_t("build:rete_ord")
    casi.append(("riaperto, la rete riordinata resta", sorted((q["x"], q["y"], tuple(tR2.voci[c_]["nome"] for c_ in q["carte"])) for q in tR2.pile) == disp_))
    tR2.salva_tutto(); tR2.chiudi()
    # Arrange: i quattro modi (13 nov 2026). Un mazzo con due gruppi, una copia di gruppo e connessioni dentro, fuori e fra i gruppi: dopo ogni modo ogni carta in
    # una pila sola, i gruppi con le stesse carte di prima, niente sovrapposizioni, tutto sulla griglia, e cosa sta in cima lo decide il modo
    dbA = dict(dbr, **{"One Drop": dict(cmc=1, tipo="Creature — Elf", testo="", colori="G", rarita="C"), "Two Drop": dict(cmc=2, tipo="Creature — Elf", testo=""),
                       "Three Drop": dict(cmc=3, tipo="Creature — Elf", testo="", colori="BG", rarita="M"),
                       "Bolt": dict(cmc=1, tipo="Instant", testo="Bolt deals 3 damage to any target."),
                       "Engine": dict(cmc=2, tipo="Enchantment", testo="", colori="W", rarita="U"), "Payoff": dict(cmc=4, tipo="Creature — Elf", testo=""),
                       "Finisher": dict(cmc=5, tipo="Creature — Dragon", testo=""), "Forest": dict(cmc=0, tipo="Basic Land — Forest", testo="")})
    mainA = {"One Drop": 4, "Two Drop": 4, "Three Drop": 3, "Bolt": 4, "Engine": 2, "Payoff": 2, "Finisher": 1, "Forest": 9, "Plains": 8}

    def nuovo_a(chiave):
        t_ = TavoloCarte(tk, F, root, "Arrange", dict(mainA), {"Side Anthem": 1}, carte_db=dbA, chiave=chiave, file_tavoli=ft, file_mazzi=fm, file_rete=fr,
                         fuori=True, limite=lim, editore=lambda a_, b_: None)
        root.update()
        return t_

    tA = nuovo_a("build:arrange")
    posti_ = {"Bolt": (0, 0), "Two Drop": (1, 0), "Payoff": (0, 702), "Finisher": (1, 702), "One Drop": (0, 1404), "Engine": (1, 1404), "Three Drop": (2, 1404),
              "Forest": (3, 1404), "Plains": (4, 1404)}
    tA.pile = [pl for pl in tA.pile if pl["zona"] != "main"] + [dict(zona="main", x=MARGINE + c_ * PASSO_X, y=y_, carte=[vid_di(tA, n_)], aperta=None)
                                                                  for n_, (c_, y_) in posti_.items()]
    tA.sel = [tA.pila_di(vid_di(tA, "Bolt")), tA.pila_di(vid_di(tA, "Two Drop"))]
    gBurn = tA.crea_etichetta("Burn", "#d9534f")
    tA.sel = [tA.pila_di(vid_di(tA, "Payoff")), tA.pila_di(vid_di(tA, "Finisher"))]
    gTop = tA.crea_etichetta("Top", "#5cb85c")
    cpA = tA.duplica_gruppo(tA.etichette.index(gBurn))
    for k_ in (("One Drop", "Engine"), ("Engine", "Payoff"), ("Bolt", "Three Drop")):
        tA.rete.lega(k_[0], k_[1], dbA)
    tA.disegna(); root.update()
    side_A = [(q["x"], q["y"], list(q["carte"])) for q in tA.pile if q["zona"] != "main"]

    def gruppi_di(t_):
        cl_, _pa, lib_ = t_.struttura()
        return {t_.etichette[k]["nome"]: sorted(t_.voci[v]["nome"] for v in vv) for k, vv in cl_.items()}, sorted(t_.voci[v]["nome"] for v in lib_)
    gr_prima = gruppi_di(tA)
    tocca_ = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
    sulla_ = lambda x_, y_: (abs(a_griglia(x_, y_)[0] - x_) < 1e-6 and abs(a_griglia(x_, y_)[1] - y_) < 1e-6)

    def ordinato(t_):
        """Le regole che ogni modo deve rispettare. -> la lista di quello che non torna (vuota: tutto in ordine)."""
        male = []
        tutte = sorted(c for pl in t_.pile if pl["zona"] == "main" for c in pl["carte"])
        if tutte != sorted(v for v, x in t_.voci.items() if x["zona"] == "main"):
            male.append("carte perse o doppie")
        if gruppi_di(t_) != gr_prima:
            male.append("gruppi cambiati")
        if [(q["x"], q["y"], list(q["carte"])) for q in t_.pile if q["zona"] != "main"] != side_A:
            male.append("sideboard mossa")
        rp = [t_.ingombro(pl) for pl in t_.pile if pl["zona"] == "main"]
        if any(tocca_(rp[i], rp[j]) for i in range(len(rp)) for j in range(i + 1, len(rp))):
            male.append("pile sovrapposte")
        rl = [(lb["x"], lb["y"], lb["x"] + lb["w"], lb["y"] + lb["h"]) for lb in t_.etichette]
        if any(tocca_(rl[i], rl[j]) for i in range(len(rl)) for j in range(i + 1, len(rl))):
            male.append("gruppi sovrapposti")
        cl_, _pa, lib_ = t_.struttura()
        for pl in t_.pile:
            if pl["zona"] == "main" and set(pl["carte"]) <= set(lib_) and any(tocca_(t_.ingombro(pl), r_) for r_ in rl):
                male.append("carta libera sopra un gruppo")
                break
        if not all(sulla_(pl["x"], pl["y"]) for pl in t_.pile if pl["zona"] == "main"):
            male.append("fuori griglia")
        return male
    ya_ = lambda t_, n_: t_.pila_di(vid_di(t_, n_))["y"]
    gl_ = lambda t_, nome: next(lb for lb in t_.etichette if lb["nome"] == nome and not lb.get("copia"))
    casi.append(("negativa: il riordino di prima (per costo, label ferme) e' preso dal controllo: gruppi cambiati o carte sopra i gruppi",
                 (tA.disponi("cost", salva=False), bool(ordinato(tA)))[1]))
    tA.pile =[pl for pl in tA.pile if pl["zona"] != "main"] + [dict(zona="main", x=MARGINE + c_ * PASSO_X, y=y_, carte=[vid_di(tA, n_)], aperta=None)
                                                                  for n_, (c_, y_) in posti_.items()]
    casi.append(("prima del riordino il mazzo di prova e' in ordine (il controllo non da' falsi rossi)", not ordinato(tA)))
    lbB = lambda t_: [gl_(t_, "Burn")] + [lb for lb in t_.etichette if lb.get("copia")]
    # By mana cost
    nC = tA.disponi_modo("costo"); root.update()
    libere_y = [pl["y"] for pl in tA.pile if pl["zona"] == "main" and set(pl["carte"]) <= set(tA.struttura()[2])]
    casi.append(("By mana cost: tutto in ordine, le carte libere in colonne per costo sopra i gruppi interi", not ordinato(tA) and nC == 5
                 and max(libere_y) < min(lb["y"] for lb in tA.etichette)
                 and all(len({tA.gruppo(c, "cost") for c in pl["carte"]}) == 1 for pl in tA.pile if pl["zona"] == "main")))
    casi.append(("By mana cost: la copia del gruppo accanto al suo gruppo, sulla stessa riga", len(lbB(tA)) == 2 and lbB(tA)[0]["y"] == lbB(tA)[1]["y"]
                 and next(lb for lb in lbB(tA) if lb.get("copia"))["x"] > gl_(tA, "Burn")["x"]))
    disp_c = sorted((q["x"], q["y"], tuple(q["carte"])) for q in tA.pile)
    tA.disponi_modo("costo"); root.update()
    casi.append(("By mana cost rifatto da' la stessa disposizione", sorted((q["x"], q["y"], tuple(q["carte"])) for q in tA.pile) == disp_c))
    # By groups
    tA.disponi_modo("gruppi"); root.update()
    cl_A = tA.struttura()[0]
    casi.append(("By groups: tutto in ordine, i gruppi in cima con una carta per pila, le carte libere sotto per costo", not ordinato(tA)
                 and min(lb["y"] for lb in tA.etichette) == 0
                 and all(len(tA.pila_di(v)["carte"]) == 1 for vv in cl_A.values() for v in vv)
                 and min(pl["y"] for pl in tA.pile if pl["zona"] == "main" and set(pl["carte"]) <= set(tA.struttura()[2]))
                 > max(lb["y"] + lb["h"] for lb in tA.etichette)))
    pila_lb = lambda t_: sorted(t_.etichette, key=lambda lb: lb["y"])
    casi.append(("One under the other: ogni gruppo (anche la copia) su una riga sua, tutti allineati a sinistra, nessuno accanto a un altro",
                 len({lb["x"] for lb in tA.etichette}) == 1
                 and all(a_["y"] + a_["h"] <= b_["y"] for a_, b_ in zip(pila_lb(tA), pila_lb(tA)[1:]))))
    tA.disponi_modo("gruppi_costo"); root.update()
    casi.append(("One under the other · by cost: tutto in ordine, gruppi uno sotto l'altro, dentro le carte in colonne per costo", not ordinato(tA)
                 and len({lb["x"] for lb in tA.etichette}) == 1
                 and all(a_["y"] + a_["h"] <= b_["y"] for a_, b_ in zip(pila_lb(tA), pila_lb(tA)[1:]))
                 and all(len({tA.gruppo(c, "cost") for c in pl["carte"]}) == 1 for pl in tA.pile if pl["zona"] == "main")))
    # CARDS: per tipo, colore, rarita'. Colore e rarita' delle carte finte stanno in carte_db (colori, rarita)
    xa_ = lambda t_, n_: t_.pila_di(vid_di(t_, n_))["x"]
    tA.disponi_modo("tipo"); root.update()
    lib_ = set(tA.struttura()[2])
    col_lib = lambda t_: [pl for pl in t_.pile if pl["zona"] == "main" and set(pl["carte"]) <= lib_]
    casi.append(("By type: tutto in ordine, una colonna per tipo (le creature prima dell'incantesimo), le terre in fondo", not ordinato(tA)
                 and all(len({tA.colonna(c, "type") for c in pl["carte"]}) == 1 for pl in col_lib(tA))
                 and xa_(tA, "One Drop") == xa_(tA, "Three Drop") < xa_(tA, "Engine") < xa_(tA, "Forest")))
    tA.disponi_modo("colore"); root.update()
    casi.append(("By color: tutto in ordine, il bianco prima del verde, l'incolore dopo, le terre in fondo", not ordinato(tA)
                 and all(len({tA.colonna(c, "color") for c in pl["carte"]}) == 1 for pl in col_lib(tA))
                 and xa_(tA, "Engine") < xa_(tA, "One Drop") < xa_(tA, "Three Drop") < xa_(tA, "Forest")))
    tA.disponi_modo("rarita"); root.update()
    casi.append(("By rarity: tutto in ordine, la mitica prima della comune, le terre in fondo", not ordinato(tA)
                 and all(len({tA.colonna(c, "rarity") for c in pl["carte"]}) == 1 for pl in col_lib(tA))
                 and xa_(tA, "Three Drop") < xa_(tA, "One Drop") < xa_(tA, "Forest")))
    # CONNECTIONS: Network
    nR = tA.disponi_modo("rete"); root.update()
    casi.append(("Network: tutto in ordine, One Drop a sinistra di Engine (una riga sopra), la rete sopra i gruppi e le altre carte", not ordinato(tA) and nR == 2
                 and xa_(tA, "One Drop") < xa_(tA, "Engine") and ya_(tA, "One Drop") < ya_(tA, "Engine") < min(lb["y"] for lb in tA.etichette)))
    # Network with groups
    nM = tA.disponi_modo("misto"); root.update()
    casi.append(("Network with groups: tutto in ordine, i gruppi nodi della rete (One Drop, Engine, poi Top a destra; Burn a sinistra di Three Drop)",
                 not ordinato(tA) and nM == 5
                 and xa_(tA, "One Drop") < xa_(tA, "Engine") < gl_(tA, "Top")["x"] and gl_(tA, "Burn")["x"] + gl_(tA, "Burn")["w"] < xa_(tA, "Three Drop")))
    casi.append(("Mixed: le terre (senza connessioni) sotto la rete, e la copia del gruppo fuori dalla rete sotto", ya_(tA, "Forest") > gl_(tA, "Top")["y"] + gl_(tA, "Top")["h"]
                 and next(lb for lb in lbB(tA) if lb.get("copia"))["y"] > gl_(tA, "Top")["y"]))
    disp_m = sorted((q["x"], q["y"], tuple(q["carte"])) for q in tA.pile)
    lab_m = [(lb["x"], lb["y"], lb["w"], lb["h"]) for lb in tA.etichette]
    tA.disponi_modo("misto"); root.update()
    casi.append(("Mixed rifatto da' la stessa disposizione, gruppi compresi", sorted((q["x"], q["y"], tuple(q["carte"])) for q in tA.pile) == disp_m
                 and [(lb["x"], lb["y"], lb["w"], lb["h"]) for lb in tA.etichette] == lab_m))
    tA.disponi_modo("costo"); root.update()
    tA.annulla(); root.update()
    casi.append(("Undo dopo un Arrange torna alla disposizione di prima", sorted((q["x"], q["y"], tuple(q["carte"])) for q in tA.pile) == disp_m))
    # col filtro acceso: niente carte in due pile, e il filtro resta
    tA.scegli_filtro("instant"); root.update()
    tA.disponi_modo("misto"); root.update()
    casi.append(("Mixed col filtro acceso: ogni carta in una pila sola, e il filtro resta acceso", sorted(c for _pl, cc in tA.pile_tutte() for c in cc) == sorted(tA.voci)
                 and bool(tA._riposte)))
    tA.scegli_filtro("all"); root.update()
    # il filtro per tipo spegne e accende anche il riquadro del gruppo (13 nov 2026): si vede se almeno una sua carta passa il filtro
    kB_, kT_ = tA.etichette.index(gl_(tA, "Burn")), tA.etichette.index(gl_(tA, "Top"))
    kC_ = next(k_ for k_, lb in enumerate(tA.etichette) if lb.get("copia"))
    disegnata_ = lambda k_: bool(tA.cv.find_withtag(f"lt{k_}"))
    vis_ = lambda: (disegnata_(kB_), disegnata_(kT_), disegnata_(kC_))
    tA.scegli_filtro("instant"); root.update()
    v_ist = vis_()
    tA.scegli_filtro("all"); tA.scegli_filtro("creature"); root.update()
    v_cre = vis_()
    tA.scegli_filtro("all"); tA.scegli_filtro("land"); root.update()
    v_ter = vis_()
    tA.scegli_filtro("all"); root.update()
    v_all = vis_()
    casi.append(("filtro Instants: Burn (Bolt) e la sua copia accesi, Top (solo creature) spento; Creatures: tutti accesi", v_ist == (True, False, True)
                 and v_cre == (True, True, True)))
    casi.append(("negativa: filtro Lands, nessun gruppo ha terre: tutti spenti; tornato All si riaccendono", v_ter == (False, False, False) and v_all == (True, True, True)))
    # il pulsante e il menu
    pA = tA.menu_disponi(); root.update()
    testi_A = [w_.cget("text") for w_ in tutti_widget(pA) if isinstance(w_, tk.Label)]
    casi.append(("il pulsante Arrange ▾ sta in testata accanto ad Add card e apre le tre sezioni coi loro modi", tA.b_arrange is not None
                 and tA.b_arrange.pack_info().get("side") == "left" and all(s_ in testi_A for s_, _vv in tA.SEZIONI_ARRANGE)
                 and all(n_ in testi_A for _m, n_, _r in tA.ARRANGE)))
    tA.nome_chiudi()
    tA.salva_tutto(); tA.chiudi()
    # le negative: By groups senza gruppi e By connections senza connessioni non toccano niente
    tN = nuovo_t("build:arrange_vuoto")
    pile_N = [(q["x"], q["y"], list(q["carte"])) for q in tN.pile]
    casi.append(("negativa: By groups senza gruppi non tocca niente, e lo dice", tN.disponi_modo("gruppi") == 0
                 and [(q["x"], q["y"], list(q["carte"])) for q in tN.pile] == pile_N and "No groups" in tN.aiuto.cget("text")))
    tN.salva_tutto(); tN.chiudi()
    # una disposizione col dot del primo giro (padre e da): si riprende con l'ingresso giusto
    vecchia_d = carica_tavoli(ft).get("build:dot2")
    if vecchia_d and vecchia_d.get("punti"):
        q0 = vecchia_d["punti"][0]
        vecchia_d = dict(vecchia_d, punti=[dict(id=q0["id"], x=q0["x"], y=q0["y"], padre="Token Maker", da=None)])
        salva_tavolo("build:dot_vecchio", vecchia_d, ft)
    tV = nuovo_t("build:dot_vecchio")
    casi.append(("un dot salvato col formato di prima (padre, da) si riprende come dot con quell'ingresso", bool(vecchia_d)
                 and tV.punti.get(q0["id"], {}).get("ingressi") == [["c", "Token Maker"]]))
    tV.salva_tutto(); tV.chiudi()
    # la selezione a riquadro e lo spostamento di gruppo, con le connessioni che seguono; le label
    tB = nuovo_t("build:sel")
    for k_ in (("Token Maker", "Anthem"), ("Vanilla", "Anthem")):
        if k_ not in tB.rete.figli:
            tB.rete.lega(k_[0], k_[1], dbr)
    tB.disegna(); root.update()
    EB = lambda x, y, st=0: type("E", (), dict(x=x - tB.cv.canvasx(0), y=y - tB.cv.canvasy(0), state=st))()
    p2, p3, pt = tB.pila_di(vid_di(tB, "Token Maker")), tB.pila_di(vid_di(tB, "Anthem")), tB.pila_di(vid_di(tB, "Plains"))
    r2, r3 = tB.ingombro_px(p2), tB.ingombro_px(p3)
    ax_, ay_ = min(r2[0], r3[0]) - 30, min(r2[1], r3[1]) - 12
    bx_, by_ = max(r2[2], r3[2]) + 4, max(r2[3], r3[3]) + 4
    tB.premi_tela(EB(ax_, ay_)); tB.trascina(EB((ax_ + bx_) / 2, (ay_ + by_) / 2)); tB.trascina(EB(bx_, by_)); tB.rilascia(EB(bx_, by_)); root.update()
    contorni = [i_ for i_ in tB.cv.find_withtag("sel") if not ({"sel_cornice", "sel_menu"} & set(tB.cv.gettags(i_)))]
    casi.append(("il riquadro sul vuoto seleziona le pile che tocca, e non le altre", len(tB.sel) == 2 and tB.in_sel(p2) and tB.in_sel(p3) and not tB.in_sel(pt)
                 and len(contorni) == 2 and not tB.cv.find_withtag("banda")))
    corB = tB.cornice_sel()
    bm_ = tB.cv.bbox("sel_menu")
    casi.append(("intorno alla selezione la cornice, e fuori, in alto a destra, le tre linee del menu", corB is not None and bool(tB.cv.find_withtag("sel_cornice"))
                 and bm_ is not None and bm_[0] > corB[2] and abs(bm_[1] - corB[1]) < 2 and bm_[3] < (corB[1] + corB[3]) / 2))
    # la finestrella dei comandi: solo in basso a destra (sopra il foglio sulla scheda video: controllato a mano sulla finestra vera, qui la radice e' nascosta)
    pan_ = tB.pannello
    righe_ = [w_.cget("text") for w_ in tutti_widget(tB.fin) if isinstance(w_, tk.Label)]
    fuori_pan = [w_.cget("text") for w_ in tutti_widget(tB.fin) if isinstance(w_, tk.Label) and not str(w_).startswith(str(pan_))]
    casi.append(("i comandi solo nella finestrella in basso a destra; fuori di li' nessuna riga di comandi", pan_.place_info().get("anchor") == "se"
                 and any(r_ == "Middle-drag" for r_ in righe_) and not any(r_ in ("Middle-drag", "Wheel") or str(r_).startswith("Wheel zoom") for r_ in fuori_pan)
                 and str(tB.aiuto).startswith(str(pan_))))
    testi_tele = [x_.itemcget(i_, "text") for x_ in tutti_widget(tB.fin) if isinstance(x_, tk.Canvas) for i_ in x_.find_all() if x_.type(i_) == "text"]
    casi.append(("nella testata niente By type, By cost, Label (lo zoom resta)", not {"By type", "By cost", "Label"} & set(testi_tele)
                 and any(isinstance(x_, tk.Label) and x_.cget("text") == "ZOOM" for x_ in tutti_widget(tB.fin))))
    tB.premi_tela(EB(*(lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2))(tB.rett(pt["carte"][-1])), st=0x4)); tB.rilascia(EB(0, 0))
    con_ctrl = tB.in_sel(pt)
    tB.premi_tela(EB(*(lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2))(tB.rett(pt["carte"][-1])), st=0x4)); tB.rilascia(EB(0, 0))
    casi.append(("Ctrl+clic aggiunge e toglie una pila dalla selezione", con_ctrl and not tB.in_sel(pt) and len(tB.sel) == 2))
    prima = {id(q): (q["x"], q["y"]) for q in (p2, p3, pt)}
    seg_prima = list(tB._segmenti)
    ra = tB.rett(vid_di(tB, "Anthem")); cxa, cya = (ra[0] + ra[2]) / 2, (ra[1] + ra[3]) / 2
    tB.premi_tela(EB(cxa, cya))
    for k_ in range(1, 6):
        tB.trascina(EB(cxa + 40 * k_, cya + 30 * k_))
    vive = len(tB.cv.find_withtag("rete_viva"))
    spente = all(tB.cv.itemcget(i_, "state") == "hidden" for i_ in tB.cv.find_withtag("rete"))
    tB.rilascia(EB(cxa + 200, cya + 150)); root.update()
    d2 = (p2["x"] - prima[id(p2)][0], p2["y"] - prima[id(p2)][1]); d3 = (p3["x"] - prima[id(p3)][0], p3["y"] - prima[id(p3)][1])
    casi.append(("trascinata una pila selezionata, si spostano tutte insieme dello stesso passo, le altre no", d2 == d3 and d2[0] > 100 and d2[1] > 80
                 and (pt["x"], pt["y"]) == prima[id(pt)] and p2 in tB.pile and p3 in tB.pile))
    casi.append(("e le connessioni seguono: le frecce vive durante, al posto nuovo dopo, nessuna vecchia accesa", vive == 2 and spente
                 and set(tB.rete.figli) == {("Token Maker", "Anthem"), ("Vanilla", "Anthem")} and tB._segmenti != seg_prima and len(tB._segmenti) == 2))
    corB = tB.cornice_sel()
    angolo = next(((corB[0] + 3 + a_, corB[1] + 3 + a_) for a_ in range(0, 10) if tB.pezzo_a(corB[0] + 3 + a_, corB[1] + 3 + a_)[0] is None), None)
    prima = {id(q): (q["x"], q["y"]) for q in (p2, p3, pt)}
    if angolo:
        tB.premi_tela(EB(*angolo))
        for k_ in range(1, 4):
            tB.trascina(EB(angolo[0] + 20 * k_, angolo[1] + 30 * k_))
        tB.rilascia(EB(angolo[0] + 60, angolo[1] + 90)); root.update()
    d2 = (p2["x"] - prima[id(p2)][0], p2["y"] - prima[id(p2)][1]); d3 = (p3["x"] - prima[id(p3)][0], p3["y"] - prima[id(p3)][1])
    casi.append(("preso nel vuoto dentro la cornice, il gruppo si sposta tutto insieme", angolo is not None and d2 == d3 and d2[0] > 40 and d2[1] > 60
                 and (pt["x"], pt["y"]) == prima[id(pt)] and len(tB.sel) == 2))
    tB.premi_tela(EB(ax_ - 400, ay_ + 5)); tB.rilascia(EB(ax_ - 400, ay_ + 5))
    casi.append(("un clic nel vuoto fuori dalla cornice scioglie la selezione", not tB.sel and not tB.cv.find_withtag("sel")))
    tB.premi_tela(EB(*(lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2))(tB.rett(pt["carte"][-1])), st=0x4)); tB.rilascia(EB(0, 0))
    corT = tB.cornice_sel()
    angT = next(((corT[0] + 3 + a_, corT[1] + 3 + a_) for a_ in range(0, 10) if tB.pezzo_a(corT[0] + 3 + a_, corT[1] + 3 + a_)[0] is None), None) if corT else None
    xt0 = (pt["x"], pt["y"])
    if angT:
        tB.premi_tela(EB(*angT)); tB.trascina(EB(angT[0] + 40, angT[1] + 30)); tB.trascina(EB(angT[0] + 80, angT[1] + 60)); tB.rilascia(EB(angT[0] + 80, angT[1] + 60))
        root.update()
    casi.append(("anche una pila sola selezionata si sposta dalla sua cornice", angT is not None and pt["x"] - xt0[0] > 40 and pt["y"] - xt0[1] > 30))
    tB.esc()
    casi.append(("Esc scioglie la selezione (e non chiude il tavolo)", not tB.sel and tB.fin.winfo_exists()))
    tB.vuota_sel()
    p2b = tB.pila_di(vid_di(tB, "Token Maker"))
    tB.sel = [p2b]; tB.disegna_sel()
    carte_p = list(p2b["carte"]); xy_p = (p2b["x"], p2b["y"])
    rr_ = tB.rett(carte_p[0]); px_s, py_s = (rr_[0] + rr_[2]) / 2, (rr_[1] + rr_[3]) / 2
    tB.premi_tela(EB(px_s, py_s)); tB.trascina(EB(px_s + 120, py_s + 80)); tB.trascina(EB(px_s + 240, py_s + 160)); tB.rilascia(EB(px_s + 240, py_s + 160)); root.update()
    casi.append(("selezione: presa da una carta in mezzo alla pila, si sposta tutta la selezione, non la carta sola", len(carte_p) > 1 and p2b["carte"] == carte_p
                 and p2b in tB.pile and (p2b["x"], p2b["y"]) != xy_p and all(tB.pila_di(c_) is p2b for c_ in carte_p)))
    rr_ = tB.rett(carte_p[-1]); px_s, py_s = (rr_[0] + rr_[2]) / 2, (rr_[1] + rr_[3]) / 2
    tB.premi_tela(EB(px_s, py_s, st=0x4)); tB.rilascia(EB(px_s, py_s, st=0x4))
    casi.append(("negativa: Ctrl+clic dentro la selezione la toglie, non sposta niente", not tB.sel and tB.drag is None))
    p2b["x"], p2b["y"] = xy_p; tB.disegna(); root.update()      # la pila torna dov'era: le prove dopo contano le posizioni di prima
    casi.append(("negativa: senza selezione la label non nasce, e lo dice", tB.crea_etichetta("X") is None and not tB.etichette and "Select the cards" in tB.aiuto.cget("text")))
    tB.sel = [p2, p3]; tB.disegna_sel()
    bm_ = tB.cv.bbox("sel_menu")
    tB.premi_tela(EB((bm_[0] + bm_[2]) / 2, (bm_[1] + bm_[3]) / 2)); tB.rilascia(EB((bm_[0] + bm_[2]) / 2, (bm_[1] + bm_[3]) / 2))
    menu_ = tB._nome_pop
    casi.append(("le tre linee aprono il menu della label: nome e colore", menu_ is not None and hasattr(menu_, "menu")))
    if menu_ is not None:
        menu_.menu["nome"].set("Finisher"); menu_.menu["colore"]("#d9534f"); menu_.menu["applica"](); root.update()
    lb = tB.etichette[0] if tB.etichette else None
    i2, i3 = tB.ingombro(p2), tB.ingombro(p3)
    dentro_ = lambda r: lb["x"] <= r[0] and r[2] <= lb["x"] + lb["w"] and lb["y"] + TIT_L <= r[1] and r[3] <= lb["y"] + lb["h"]
    tutti_B = tB.cv.find_all()
    casi.append(("la label nasce intorno alle pile selezionate, col nome e il colore del menu, chiusa, sotto le carte", lb is not None and lb["nome"] == "Finisher"
                 and lb.get("colore") == "#d9534f" and lb.get("lucchetto") is True and dentro_(i2) and dentro_(i3) and tB._nome_pop is None
                 and not tB.sel and max(tutti_B.index(i_) for i_ in tB.cv.find_withtag("label") if "nota" not in tB.cv.gettags(i_))
                 < min(tutti_B.index(i_) for i_ in tB.cv.find_withtag("carta"))))
    bt = tB.cv.bbox("lt0")
    tx_, ty_ = bt[0] + 40, (bt[1] + bt[3]) / 2
    pos_l = (lb["x"], lb["y"]); prima = {id(q): (q["x"], q["y"]) for q in (p2, p3, pt)}
    tB.premi_tela(EB(tx_, ty_))
    for k_ in range(1, 5):
        tB.trascina(EB(tx_ + 30 * k_, ty_ + 25 * k_))
    tB.rilascia(EB(tx_ + 120, ty_ + 100)); root.update()
    dl = (lb["x"] - pos_l[0], lb["y"] - pos_l[1])
    casi.append(("trascinata dal titolo, la label si porta dietro le sue pile, le altre restano", dl[0] > 50 and dl[1] > 40
                 and (p2["x"] - prima[id(p2)][0], p2["y"] - prima[id(p2)][1]) == dl == (p3["x"] - prima[id(p3)][0], p3["y"] - prima[id(p3)][1])
                 and (pt["x"], pt["y"]) == prima[id(pt)]))
    tB.rinomina_etichetta(0, "Win cons")
    tB.salva_tutto(); tB.chiudi()
    tB2 = nuovo_t("build:sel")
    casi.append(("riaperto, la label c'e' col suo nome e al suo posto, con le pile dentro", len(tB2.etichette) == 1 and tB2.etichette[0]["nome"] == "Win cons"
                 and (tB2.etichette[0]["x"], tB2.etichette[0]["y"]) == (lb["x"], lb["y"]) and len(tB2.membri(0)[0]) == 2))
    EB2 = lambda x, y: type("E", (), dict(x=x - tB2.cv.canvasx(0), y=y - tB2.cv.canvasy(0), state=0))()
    lb2 = tB2.etichette[0]
    casi.append(("riaperto, la label ha il suo colore e il lucchetto chiuso", lb2.get("colore") == "#d9534f" and lb2.get("lucchetto") is True))
    # il lucchetto: aperta, la label si sposta da sola (e prende dentro le carte su cui la lasci); chiusa, si porta dietro quello che ha dentro
    bl_ = tB2.cv.bbox("ll0")
    tB2.premi_tela(EB2((bl_[0] + bl_[2]) / 2, (bl_[1] + bl_[3]) / 2)); tB2.rilascia(EB2((bl_[0] + bl_[2]) / 2, (bl_[1] + bl_[3]) / 2)); root.update()
    aperta_ = lb2.get("lucchetto") is False
    pile_prima = {id(q): (q["x"], q["y"]) for q in tB2.pile}
    l_prima = (lb2["x"], lb2["y"])

    def tira_titolo(dx, dy):
        bt_ = tB2.cv.bbox("lt0")
        x_, y_ = bt_[0] + 40, (bt_[1] + bt_[3]) / 2
        tB2.premi_tela(EB2(x_, y_))
        for k_ in range(1, 5):
            tB2.trascina(EB2(x_ + dx * k_ / 4, y_ + dy * k_ / 4))
        tB2.rilascia(EB2(x_ + dx, y_ + dy)); root.update()
    tira_titolo(0, 700)
    casi.append(("negativa del lucchetto: aperta, la label si sposta da sola e le carte restano dove sono", aperta_ and lb2["y"] - l_prima[1] > 300
                 and {id(q): (q["x"], q["y"]) for q in tB2.pile} == pile_prima and not tB2.membri(0)[0]))
    tira_titolo(0, -700)
    casi.append(("aperta e riportata sopra le carte, le prende dentro", len(tB2.membri(0)[0]) == 2))
    bl_ = tB2.cv.bbox("ll0")
    tB2.premi_tela(EB2((bl_[0] + bl_[2]) / 2, (bl_[1] + bl_[3]) / 2)); tB2.rilascia(EB2((bl_[0] + bl_[2]) / 2, (bl_[1] + bl_[3]) / 2)); root.update()
    pile_prima = {id(q): (q["x"], q["y"]) for q in tB2.pile}
    tira_titolo(200, 0)
    mosse_ = [q for q in tB2.pile if (q["x"], q["y"]) != pile_prima[id(q)]]
    casi.append(("richiusa, la label si porta dietro le sue carte", lb2.get("lucchetto") is True and len(mosse_) == 2))
    bmL = tB2.cv.bbox("lm0")
    tB2.premi_tela(EB2((bmL[0] + bmL[2]) / 2, (bmL[1] + bmL[3]) / 2)); tB2.rilascia(EB2((bmL[0] + bmL[2]) / 2, (bmL[1] + bmL[3]) / 2))
    mL = tB2._nome_pop
    if mL is not None:
        mL.menu["colore"]("#24baff")
        mL.menu["nome"].set("Closers"); mL.menu["applica"](); root.update()
    casi.append(("le tre linee sul titolo aprono il menu della label: il colore cambia subito, il nome con Invio", mL is not None and lb2["colore"] == "#24baff"
                 and lb2["nome"] == "Closers"))
    bx0 = tB2.cv.bbox("lx0")
    n_pile = len(tB2.pile)
    tB2.premi_tela(EB2((bx0[0] + bx0[2]) / 2, (bx0[1] + bx0[3]) / 2)); tB2.rilascia(EB2((bx0[0] + bx0[2]) / 2, (bx0[1] + bx0[3]) / 2))
    casi.append(("la ✕ della label la toglie, le carte restano", not tB2.etichette and len(tB2.pile) == n_pile))
    tB2.salva_tutto(); tB2.chiudi()
    # la barra della fascia non ruba il clic: una label col titolo proprio sulla barra si trascina dal titolo
    tL = nuovo_t("build:barra")
    tL.cv.winfo_width = lambda: 1000; tL.cv.winfo_height = lambda: 700
    tL.sel = [tL.pila_di(vid_di(tL, "Anthem"))]; lbL = tL.crea_etichetta("Top")
    thL = max(16, TIT_L * tL.zoom)
    lbL["y"] = round((tL.hs - tL.oy("main") - thL / 2) / tL.zoom); tL.disegna(); root.update()
    ELb = lambda x, y: type("E", (), dict(x=x - tL.cv.canvasx(0), y=y - tL.cv.canvasy(0), state=0))()
    btL = tL.cv.bbox("lt0"); txL, tyL = btL[0] + 20, tL.hs
    hs0, y0L = tL.hs, lbL["y"]
    tL.premi_tela(ELb(txL, tyL)); tL.trascina(ELb(txL + 10, tyL + 60)); tL.trascina(ELb(txL + 20, tyL + 120)); tL.rilascia(ELb(txL + 20, tyL + 120)); root.update()
    casi.append(("la label col titolo sulla barra si trascina dal titolo; la barra della fascia resta dov'era", tL.hs == hs0 and lbL["y"] > y0L and tL.separa is None))
    tL.premi_tela(ELb(980, tL.hs))
    casi.append(("negativa: nel vuoto la barra della fascia si prende ancora", tL.separa is not None))
    tL.rilascia(ELb(980, tL.hs)); root.update()
    tL.salva_tutto(); tL.chiudi()
    # niente salvataggi automatici, Save, Undo, Redo, la domanda alla chiusura (12 nov 2026, Autore: «la board di editor dei deck non deve autosalvare i
    # cambiamenti», «nella board editor vogliamo i pulsanti save, undo (ctrl z), redo»)
    mU = MS.aggiungi("build", dict(nome="Undo", lista={"Lightning Bolt": 2, "Shock": 2, "Mountain": 14}, side={}), f=fm)
    tU = TavoloCarte(tk, F, root, "Undo", mU["lista"], {}, carte_db=db, chiave="build:" + mU["id"], modificabile=("build", mU["id"]), file_tavoli=ft, file_mazzi=fm,
                     fuori=True, limite=lim)
    root.update()
    sU = lambda: next(x for x in MS.carica(fm)["build"] if x["id"] == mU["id"])["lista"]
    casi.append(("Save, Undo e Redo nella testata in modalita' edit; appena aperto niente da salvare", bool(getattr(tU, "b_salva", None)) and bool(getattr(tU, "b_undo", None))
                 and bool(getattr(tU, "b_redo", None)) and not tU.da_salvare))
    bU = tU.vid_nome("Shock")
    tU.cambia_copie(bU, +1); root.update()
    tU.cambia_copie(tU.vid_nome("Shock"), +1); root.update()
    casi.append(("due + : il Board ha 4 Shock, il file ancora 2 (niente autosalvataggio), da salvare", tU.liste()[0]["Shock"] == 4 and sU()["Shock"] == 2 and tU.da_salvare))
    tU.annulla(); root.update()
    casi.append(("Undo: 3 Shock", tU.liste()[0]["Shock"] == 3))

    class EK:
        def __init__(self, k, st):
            self.keysym, self.state = k, st
    tU.tasto(EK("z", 0x4)); root.update()
    casi.append(("Ctrl+Z: 2 Shock, come all'apertura: niente da salvare", tU.liste()[0]["Shock"] == 2 and not tU.da_salvare))
    casi.append(("negativa: oltre l'inizio Undo non fa niente", not tU.annulla() and tU.liste()[0]["Shock"] == 2))
    tU.tasto(EK("y", 0x4)); root.update()
    tU.tasto(EK("z", 0x5)); root.update()
    casi.append(("Ctrl+Y e Ctrl+Shift+Z: Redo due volte, 4 Shock", tU.liste()[0]["Shock"] == 4))
    tU.salva_tutto(); root.update()
    casi.append(("Save: il file ha 4 Shock, niente piu' da salvare", sU()["Shock"] == 4 and not tU.da_salvare))
    tU.cambia_copie(tU.vid_nome("Lightning Bolt"), +1); root.update()
    esito_ = tU.chiudi(); root.update()
    dom_ = getattr(tU, "domanda", None)
    casi.append(("chiudendo con modifiche: la domanda, e il Board resta aperto", esito_ is False and dom_ is not None and dom_.winfo_exists() and tU.fin.winfo_exists()))
    import piattaforma as P_
    pr_ = P_.proprietaria(dom_)
    casi.append(("la domanda ha il Board come proprietaria: Windows la tiene sopra di lui (13 nov 2026: senza, un clic dietro la copriva e col grab l'app "
                 "non si chiudeva piu')", pr_ is None or (pr_[1] == pr_[2] == P_.proprietaria(tU.fin)[0])))
    # la X vera di Windows (WM_CLOSE) passa dal protocollo: la domanda, una sola
    dom_.no(); root.update()
    if P_.WINDOWS:
        import ctypes as ct_
        ct_.WinDLL("user32").PostMessageW(P_.proprietaria(tU.fin)[0], 0x0010, 0, 0)
        for _ in range(20):
            root.update()
        casi.append(("la X vera (WM_CLOSE) con modifiche chiede, e il Board resta aperto", tU.fin.winfo_exists() and tU.domanda.winfo_exists()))
        tU.domanda.no(); root.update()
    # la negativa: senza la proprietaria (come fino al 13 nov 2026) la domanda nasce senza, e il controllo lo vede
    vero_sd = P_.sopra_di
    P_.sopra_di = lambda f_, p_: False
    tU.chiudi(); root.update()
    pr_n = P_.proprietaria(tU.domanda)
    P_.sopra_di = vero_sd
    casi.append(("negativa: senza sopra_di la domanda non ha proprietaria", pr_n is None or pr_n[1] != pr_n[2]))
    tU.domanda.no(); root.update()
    casi.append(("Cancel: il Board resta aperto con la modifica", tU.fin.winfo_exists() and tU.liste()[0]["Lightning Bolt"] == 3))
    tU.chiudi(); root.update()
    tU.domanda.altro(); root.update()
    casi.append(("Don't save: il Board si chiude e il file resta all'ultimo Save (negativa: la modifica non c'e')", not tU.fin.winfo_exists()
                 and sU()["Lightning Bolt"] == 2 and sU()["Shock"] == 4))
    # ---- 13 nov 2026 (Autore: «testa le board delle schede dei deck perche' all'apertura sono disposte male», «l'outliner non deve ripetere le carte
    # gruppate», «quando seleziono una categoria di carte il focus si sposta a caso»): l'apertura inquadrata, il filtro che inquadra le carte a vista, F e A
    # sotto la fascia e fuori dall'HUD, l'outliner a elenco unico, il filtro con le carte tolte o riordinate, la fascia che sta nella finestra
    dbV = {"Lightning Bolt": dict(cmc=1, tipo="Instant"), "Shock": dict(cmc=2, tipo="Instant"), "Opt": dict(cmc=3, tipo="Sorcery"),
           "Abrade": dict(cmc=4, tipo="Creature — Elf"), "Token Maker": dict(cmc=5, tipo="Creature — Human"), "Anthem": dict(cmc=6, tipo="Enchantment"),
           "Vanilla": dict(cmc=7, tipo="Creature — Bear"), "Mountain": dict(cmc=0, tipo="Basic Land — Mountain"), "Plains": dict(cmc=0, tipo="Basic Land — Plains")}
    mainV = {"Lightning Bolt": 4, "Shock": 4, "Opt": 4, "Abrade": 4, "Token Maker": 4, "Anthem": 4, "Vanilla": 4, "Mountain": 16, "Plains": 8}

    def apri_v(chiave, sola=True, side=None, L=1000, H=700):
        kw_ = dict(sola_lettura=True) if sola else dict(editore=lambda a_, b_: None, limite=lim)
        t_ = TavoloCarte(tk, F, root, "Vista", dict(mainV), dict(side or {}), carte_db=dbV, chiave=chiave, file_tavoli=ft, file_mazzi=fm, file_rete=fr, fuori=True, **kw_)
        root.update()
        t_.cv.winfo_width = lambda: L; t_.cv.winfo_height = lambda: H
        return t_
    tV0 = apri_v("mio:vista_nuovo", side={"Abrade": 1})
    n_col = len([pl for pl in tV0.pile if pl["zona"] == "main"])
    casi.append(("apertura: un mazzo senza disposizione ha le colonne dei costi che stanno nella finestra vera (1262 pixel: 7, 6 e 7 insieme), anche se la tela non ha "
                 "ancora la sua misura (prima 4: 1, 2, 3+, terre)", n_col == 7))
    tV0.chiudi()
    # una disposizione salvata con pile lontane: a destra, a sinistra e sopra l'inizio del mazzo
    w_, h_, off_, _p = misure(1.0)
    salva_tavolo("mio:vista_lontana", dict(v=2, zoom=1.0, fascia=250, pile=[
        dict(zona="main", x=22, y=0, carte=[["Lightning Bolt", 4], ["Shock", 4]]), dict(zona="main", x=4200, y=900, carte=[["Opt", 4], ["Abrade", 4]]),
        dict(zona="main", x=-1500, y=-800, carte=[["Token Maker", 4], ["Anthem", 4]]), dict(zona="main", x=900, y=300, carte=[["Vanilla", 4]]),
        dict(zona="main", x=1300, y=0, carte=[["Mountain", 16], ["Plains", 8]])]), ft)
    tV = apri_v("mio:vista_lontana")
    fuori_prima = not tV.pile_in_vista()
    tV.al_configure(); root.update()
    casi.append(("apertura: le pile lontane (a destra, a sinistra, sopra) inquadrate tutte, sotto la fascia e fuori dall'HUD (prima la vista partiva dall'angolo del foglio)",
                 fuori_prima and tV.pile_in_vista() and tV.zoom < 1.0 and not tV._da_inquadrare))
    vx_, vy_, z_ = tV.cv.canvasx(0), tV.cv.canvasy(0), tV.zoom
    tV.al_configure(); root.update()
    casi.append(("negativa: inquadrato una volta, un altro <Configure> non sposta piu' la vista", (tV.cv.canvasx(0), tV.cv.canvasy(0), tV.zoom) == (vx_, vy_, z_)))
    casi.append(("niente piu' il rettangolo scuro sopra il mazzo (una seconda fascia vuota quando la vista va sopra l'inizio del foglio)", not tV.cv.find_withtag("fondo")))
    # il filtro: le carte a vista fuori dalla vista vengono inquadrate
    tV.zoom = 1.0; tV.disegna(); tV.cv.scan_mark(0, 0); tV.cv.scan_dragto(int(tV.cv.canvasx(0)), int(tV.cv.canvasy(0)), gain=1); tV.segui_fascia(); root.update()
    tV.scegli_filtro("creature"); root.update()
    cre_ = [pl for pl in tV.pile if pl["zona"] == "main"]
    casi.append(("il filtro Creatures: le creature (lontane) inquadrate, dentro la vista (prima la vista restava ferma e non si vedeva niente)",
                 bool(cre_) and all(tV.visibile(c) for pl in cre_ for c in pl["carte"]) and tV.pile_in_vista()))
    vx_, vy_, z_ = tV.cv.canvasx(0), tV.cv.canvasy(0), tV.zoom
    tV.scegli_filtro("creature"); tV.scegli_filtro("creature"); root.update()
    casi.append(("negativa: un filtro le cui carte si vedono gia' tutte non sposta la vista", (tV.cv.canvasx(0), tV.cv.canvasy(0), tV.zoom) == (vx_, vy_, z_)))
    tV.scegli_filtro("all"); root.update()
    casi.append(("tornato a All: tutto il mazzo in vista", tV.pile_in_vista()))
    # Fit: come A, anche con le pile a sinistra e sopra
    tV.zoom = 1.0; tV.disegna(); root.update()
    tV.adatta(); root.update()
    casi.append(("Fit: tutte le pile in vista, anche quelle a sinistra e sopra l'inizio del foglio (prima portava la vista all'angolo del foglio)", tV.pile_in_vista()))
    # F: sotto la fascia, non al centro di tutta la tela
    sola_ = tV.pila_di(tV.vid_nome("Vanilla"))
    tV.sel_carta = sola_["carte"][-1]
    tV.inquadra_selezione(); root.update()
    r_f = tV.rett_selezione()
    casi.append(("F: la carta tutta sotto la fascia della sideboard e fuori dall'HUD (prima il centro di tutta la tela: la cima finiva sotto la fascia)",
                 tV.in_vista(r_f) and r_f[1] - tV.cv.canvasy(0) >= tV.hs))
    tV.chiudi()
    tVs = apri_v("mio:vista_side", side={"Abrade": 1, "Shock": 1})
    tVs.disegna(); root.update()
    vx_, vy_, z_ = tVs.cv.canvasx(0), tVs.cv.canvasy(0), tVs.zoom
    tVs.sel_carta = tVs.pila_di(next(i for i, v in tVs.voci.items() if v["zona"] == "side"))["carte"][-1]
    ok_s = tVs.inquadra_selezione() is False and (tVs.cv.canvasx(0), tVs.cv.canvasy(0), tVs.zoom) == (vx_, vy_, z_) and "sideboard band" in tVs.aiuto.cget("text")
    casi.append(("negativa: F su una carta della fascia non porta il foglio in un punto a caso (la fascia e' sempre in vista), e lo dice", ok_s))
    # la fascia sta nella finestra: con tante carte diverse in sideboard si impilano a 2 o 3
    tVs.cv.winfo_width = lambda: 700
    voci0_ = tVs.voci
    side8 = {n_: 1 for n_ in ("Lightning Bolt", "Shock", "Opt", "Abrade", "Token Maker", "Anthem", "Vanilla", "Plains")}
    tVs.voci = {i: dict(nome=n_, zona="side", q=1) for i, n_ in enumerate(side8)}
    pf_ = tVs.pile_fascia()
    destra_f = max(pl["x"] + w_ for pl in pf_) * max(tVs.sf(), SPARISCE)
    casi.append(("la sideboard all'apertura sta nella larghezza della finestra, a sinistra dell'HUD: 8 carte su 700 pixel a pile di 2-3 (prima una per pila, oltre il bordo)",
                 destra_f <= 700 - INFO_L - 28 and max(len(pl["carte"]) for pl in pf_) in (2, 3) and sum(len(pl["carte"]) for pl in pf_) == 8))
    tVs.voci = {0: dict(nome="Shock", zona="side", q=1), 1: dict(nome="Opt", zona="side", q=1)}
    casi.append(("negativa: due carte in sideboard, una per pila come sempre", [len(pl["carte"]) for pl in tVs.pile_fascia()] == [1, 1]))
    tVs.voci = voci0_
    tVs.chiudi()
    tVv = apri_v("mio:vista_vuota")
    casi.append(("in sola lettura, senza sideboard ne' comandante, niente fascia vuota in cima (prima 250 pixel vuoti)", tVv.hs == 0 and tVv.nascosta()))
    tVv.disegna(); root.update()
    seg_ = [tVv.cv.bbox(i_) for i_ in tVv.cv.find_withtag("barra") if tVv.cv.type(i_) == "image"]
    mx_ = tVv.cv.canvasx(0) + 500
    casi.append(("con la fascia chiusa il segno della barra e' intero sotto il bordo alto, e si prende per riaprirla", bool(seg_) and seg_[0][1] >= tVv._fy - 0.5
                 and tVv.vicino_barra(tVv._fy + 9, mx_)))
    casi.append(("negativa: lontano dal segno, in cima alla vista, non e' la barra (le carte li' si prendono)", not tVv.vicino_barra(tVv._fy + 9, mx_ + 300)))
    tVv.chiudi()
    tVe = apri_v("build:vista_vuota", sola=False)
    casi.append(("negativa: in modalita' edit la fascia resta aperta anche vuota (ci si lasciano le carte)", tVe.hs == FASCIA_DEF and not tVe.nascosta()))
    # la carta arrivata dal builder nello spazio isolato: in vista
    tVe.disegna(); root.update()
    tVe.allinea(dict(mainV, Nuova=1), {})
    root.update()
    v_n = tVe.vid_nome("Nuova")
    x0n, y0n, x1n, y1n = tVe.ingombro_px(tVe.pila_di(v_n))
    casi.append(("la carta nuova dal builder (spazio isolato a destra di tutto) arriva in vista (prima fuori dallo schermo)", tVe.in_vista((x0n - 16, y0n - 8, x1n + 8, y1n + 26))))
    # col filtro acceso: il builder toglie una carta nascosta, Arrange network senza connessioni
    tVe.scegli_filtro("instant"); root.update()
    try:
        tVe.allinea({n_: q_ for n_, q_ in mainV.items() if n_ != "Vanilla"}, {}); root.update()
        crash_ = False
    except Exception:       # noqa: BLE001
        crash_ = True
    tutte_ = [c for _pl, cc in tVe.pile_tutte() for c in cc]
    casi.append(("col filtro acceso il builder toglie una carta nascosta: niente pila vuota, il disegno non cade (prima IndexError in disegna)",
                 not crash_ and tVe.vid_nome("Vanilla") is None and all(pl["carte"] for pl in tVe.pile) and sorted(tutte_) == sorted(tVe.voci)))
    tVe.disponi_rete(); root.update()
    casi.append(("negativa: Arrange network senza connessioni lascia il filtro com'era (solo gli istantanei sul foglio)",
                 all(tVe.visibile(c) for pl in tVe.pile for c in pl["carte"]) and bool(tVe._riposte)))
    tVe.rete.lega("Lightning Bolt", "Shock", dbV)
    tVe.disponi_rete(); root.update()
    tutte_ = [c for _pl, cc in tVe.pile_tutte() for c in cc]
    casi.append(("Arrange network col filtro acceso: ogni carta in una pila sola (prima le nascoste finivano in due pile)", sorted(tutte_) == sorted(tVe.voci)))
    tVe.scegli_filtro("all"); root.update()
    # l'outliner: un elenco solo, il gruppo al posto della sua prima carta con sotto le sue carte (anche le terre), nessuna carta ripetuta
    pS_, pM_ = tVe.pila_di(tVe.vid_nome("Shock")), tVe.pila_di(tVe.vid_nome("Mountain"))
    pM_["x"], pM_["y"] = pS_["x"] + PASSO_X, pS_["y"]        # le terre accanto a Shock: la label prende solo queste due pile
    tVe.sel = [pS_, pM_]
    gV = tVe.crea_etichetta("Burn", "#d9534f"); root.update()
    kV = tVe.etichette.index(gV)
    cpV = tVe.duplica_gruppo(kV); root.update()
    righe_V = tVe.voci_outliner()
    carte_V = [x[1] for x in righe_V if x[0] == "carta"]
    i_g = next(i for i, x in enumerate(righe_V) if x[0] == "gruppo" and x[1] == kV)
    sotto_ = [tVe.voci[x[1]]["nome"] for x in righe_V[i_g + 1:i_g + 3]]
    i_bolt = next(i for i, x in enumerate(righe_V) if x[0] == "carta" and tVe.voci[x[1]]["nome"] == "Lightning Bolt")
    i_opt = next(i for i, x in enumerate(righe_V) if x[0] == "carta" and tVe.voci[x[1]]["nome"] == "Opt")
    testi_V = [tVe.out_cv.itemcget(i_, "text") for i_ in tVe.out_cv.find_all() if tVe.out_cv.type(i_) == "text"]
    casi.append(("outliner: ogni carta una volta sola, il gruppo fra Lightning Bolt e Opt (al posto di Shock) con sotto Shock e le terre, la copia una riga sotto",
                 sorted(carte_V) == sorted(tVe.voci) and len(carte_V) == len(set(carte_V)) and i_bolt < i_g < i_opt and sotto_ == ["Shock", "Mountain"]
                 and righe_V[i_g + 4][0] == "gruppo" and righe_V[i_g + 4][2] is cpV and "BURN" in testi_V))
    casi.append(("negativa: niente piu' la sezione GROUPS in fondo che ripeteva le carte", "GROUPS" not in testi_V
                 and sum(1 for _a, _b, v_ in tVe._out_righe if v_ == tVe.vid_nome("Shock")) == 1))
    y_g = next((a_ + b_) / 2 for a_, b_, v_ in tVe._out_righe if v_ == ("l", kV))
    tVe.scegli_outliner(type("E", (), dict(x=20, y=y_g, state=0))()); root.update()
    casi.append(("clic sul gruppo nell'outliner: scelto e inquadrato nell'area libera", tVe.sel_label == {kV} and tVe.in_vista(tVe.lb_px(kV), tolleranza=40)))
    # la carta scelta nell'outliner fuori dalla vista: il foglio la porta in vista, senza cambiare lo zoom
    tVe.zoom = 1.0; tVe.disegna(); tVe.cv.scan_mark(0, 0); tVe.cv.scan_dragto(-4000, -3000, gain=1); root.update()
    y_c = next((a_ + b_) / 2 for a_, b_, v_ in tVe._out_righe if v_ == tVe.vid_nome("Opt"))
    tVe.scegli_outliner(type("E", (), dict(x=20, y=y_c, state=0))()); root.update()
    x0o, y0o, x1o, y1o = tVe.ingombro_px(tVe.pila_di(tVe.vid_nome("Opt")))
    casi.append(("clic su una carta dell'outliner fuori dalla vista: la sua pila in vista, lo zoom resta", tVe.zoom == 1.0 and tVe.in_vista((x0o, y0o, x1o, min(y1o, y0o + 300)))))
    # la rotella sotto il 30% (dopo un'inquadratura di un foglio grande): non salta al 30%, va a passi fini
    tVe.zoom = 0.15; tVe.disegna()
    tVe.zoom_a(0.15 * 1.12); z_su = tVe.zoom
    tVe.zoom = 0.15; tVe.zoom_a(0.15 / 1.12); z_giu = tVe.zoom
    casi.append(("la rotella sotto il 30%: in su 0,17 (prima saltava a 0,30), in giu' resta", abs(z_su - 0.17) < 1e-9 and z_giu == 0.15))
    tVe.zoom = 0.3; tVe.zoom_a(0.3 / 1.12)
    casi.append(("negativa: dal 30% la rotella non scende piu' giu'", tVe.zoom == 0.3))
    # la connessione col pallino e' un gesto: nello storico e da salvare (prima chiudendo senza Save si perdeva, senza domanda)
    tVe.zoom = 1.0; tVe.disegna(); tVe.salva_tutto(); root.update()
    tVe.rete.figli.pop(("Opt", "Abrade"), None)
    tVe.apri_pila(tVe.vid_nome("Opt")) if tVe.pila_di(tVe.vid_nome("Opt"))["carte"][-1] != tVe.vid_nome("Opt") else None
    tVe.inquadra_tutto(); tVe.salva_tutto(); root.update()       # tutto in vista e fuori dall'HUD (sotto l'HUD le carte non si prendono)
    tira(tVe, "Opt", "Abrade")
    legata_ = ("Opt", "Abrade") in tVe.rete.figli
    casi.append(("la connessione col pallino in modalita' edit: da salvare (Save acceso, chiudendo chiede) e nello storico", legata_ and tVe.da_salvare))
    tVe.annulla(); root.update()
    casi.append(("Undo toglie la connessione, e non c'e' piu' niente da salvare", ("Opt", "Abrade") not in tVe.rete.figli and not tVe.da_salvare))
    # col filtro acceso un disegno non e' un gesto: lo storico non cambia (prima l'ordine delle pile cambiava e Save si accendeva da solo)
    tVe.scegli_filtro("creature"); root.update()
    tVe.zoom_a(0.8); root.update(); tVe.disegna(); tVe.salva()
    casi.append(("col filtro acceso zoom e disegno non segnano un gesto finto: niente da salvare", not tVe.da_salvare))
    tVe.scegli_filtro("all"); root.update()
    tVe.chiudi(chiedi=False)
    root.destroy()
    RS.FILE, RS.IMPARATE, globals()["FILE"] = vero_
    casi.append(("le prove non toccano i file di Autore (reti, imparato, disposizioni)", impronta_vera() == veri_prima))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
