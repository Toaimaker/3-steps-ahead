"""Il mana: il passo 4 del motore di partita (14 ott 2026).

Secondo il regolamento ufficiale (Regole/MagicCompRules.txt, numeri letti con Motore_Opzioni/regolamento.py):
  - i tipi di mana sono sei: i cinque colori e l'incolore (106.1a, 106.1b). La riserva tiene il mana per tipo e si svuota
    alla fine di ogni passo e di ogni fase (106.4): `Riserva`;
  - i simboli di costo (107.4): {W}{U}{B}{R}{G} si pagano solo col loro colore (107.4a); i numeri e la {X} sono mana
    generico, si pagano con qualsiasi tipo (107.4b); {C} solo con mana incolore (107.4c); {0} non costa niente (107.4d);
    gli ibridi {W/U} con l'uno o l'altro colore, gli ibridi monocolore {2/B} con un nero o due mana qualsiasi, i {C/W} con
    un incolore o un bianco (107.4e); i phyrexiani {W/P} e {W/U/P} con un mana del colore o con 2 vite (107.4f). La neve
    {S} (107.4h) vuole sapere da che fonte arriva il mana: qui non c'e', e un costo con {S} esce NonCoperto (nessuna
    carta di FRA ce l'ha). Un simbolo sconosciuto e' un errore, mai «un mana di qualsiasi colore»;
  - il valore di mana (202.3): la X conta 0 fuori dalla pila e il numero annunciato in pila (202.3e, 107.3g), l'ibrido
    conta la sua parte piu' grande (202.3f), il phyrexiano 1 (202.3g). I colori di un oggetto sono quelli dei simboli del
    suo costo, ibridi e phyrexiani compresi (202.2, 202.2d);
  - pagare (601.2b, 601.2f-h, 118.3): si annuncia la X (107.3a) e per ogni ibrido o phyrexiano come lo si paga
    (601.2b); il costo totale si blocca (601.2f); si attivano le abilita' di mana (601.2g, 605.3a) e si paga tutto o
    niente (601.2h): pagare mana e' togliere quel mana dalla riserva (118.3a), pagare vite si puo' solo con almeno
    altrettante vite (119.4). Un oggetto senza costo di mana ha un costo che non si paga (202.1b, 118.6);
  - da dove viene il mana: una terra con un tipo base ha «{T}: aggiungi» il suo colore anche senza testo (305.6), una per
    ogni tipo base che ha; le altre fonti hanno le loro produzioni nelle caratteristiche (car «mana»: «{R}» o «{W}» per una
    terra doppia, «{C}{C}{C}» per tre incolori). Le abilita' di mana non usano la pila (605.3b).

`piano` trova un pagamento esatto (ricerca completa, non avida: con le terre doppie l'avido sbaglia, vedi la prova) e,
fra i pagamenti possibili, quello che tappa meno fonti e lascia stappate le piu' versatili (a parita', l'incolore prima
di un colore): questa e' una scelta del giocatore finto, il regolamento chiede solo che il pagamento sia legale (`valida`).

    py -I -X utf8 Motore_Partita/mana.py --prova
"""
import itertools
import os
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso

COLORI = ("W", "U", "B", "R", "G")                               # 106.1a
TIPI = COLORI + ("C",)                                           # 106.1b
BASE_MANA = {"plains": "W", "island": "U", "swamp": "B", "mountain": "R", "forest": "G"}   # 305.6
_SIMBOLO = re.compile(r"\{([^}]+)\}")


class NonCoperto(ValueError):
    """Una regola che questo passo non copre ancora, dichiarata invece di indovinata."""


# ====================================================================== i simboli e i costi
@dataclass(frozen=True)
class Modo:
    """Un modo di pagare un simbolo (601.2b): «tipo» un tipo di mana (o None = generico) per «quanto», piu' «vite»."""
    tipo: str = None
    quanto: int = 0
    vite: int = 0


def simbolo(s):
    """107.4: il simbolo senza graffe -> i modi di pagarlo. Generico e X li tiene `leggi`, non arrivano qui."""
    if s in TIPI: return (Modo(s, 1),)                                                             # 107.4a, 107.4c
    parti = s.split("/")
    if parti[-1] == "P" and 2 <= len(parti) <= 3 and all(p in COLORI for p in parti[:-1]) and len(set(parti[:-1])) == len(parti) - 1:
        return tuple(Modo(c, 1) for c in parti[:-1]) + (Modo(None, 0, 2),)                         # 107.4f
    if len(parti) == 2:
        a, b = parti
        if a.isdigit() and b in COLORI: return (Modo(b, 1), Modo(None, int(a)))                   # 107.4e {2/B}
        if a == "C" and b in COLORI: return (Modo("C", 1), Modo(b, 1))                            # 107.4e {C/W}
        if a in COLORI and b in COLORI and a != b: return (Modo(a, 1), Modo(b, 1))                # 107.4e {W/U}
    if s == "S": raise NonCoperto("{S} (107.4h): serve sapere se il mana viene da una fonte neve; nessuna carta di FRA")
    raise ValueError(f"simbolo di mana sconosciuto: {{{s}}} (107.4)")


@dataclass(frozen=True)
class Costo:
    """Un costo di mana letto (202.1): il generico dei numeri, quante {X}, e i simboli con i loro modi."""
    testo: str
    generico: int
    x: int
    simboli: tuple                     # ((testo, (Modo, ...)), ...)

    @property
    def pagabile(self): return self.testo != ""                                                     # 202.1b, 118.6


def leggi(costo):
    """«{2}{W/U}{X}» -> Costo. Una stringa vuota o None e' «nessun costo di mana» (202.1b): non si paga (118.6)."""
    testo = (costo or "").strip()
    if "//" in testo: raise NonCoperto("le carte con due meta' (709, 715) hanno un costo per meta': si legge la meta' lanciata")
    if testo and _SIMBOLO.sub("", testo).strip():
        raise ValueError(f"costo non fatto solo di simboli: {costo!r}")
    gen, x, sim = 0, 0, []
    for s in _SIMBOLO.findall(testo):
        if s.isdigit(): gen += int(s)                                                              # 107.4b, 107.4d
        elif s in ("X", "Y"): x += 1                                                               # 107.3, 107.3p
        else: sim.append((s, simbolo(s)))
    return Costo(testo, gen, x, tuple(sim))


def _costo(c): return c if isinstance(c, Costo) else leggi(c)


def valore(costo, x=None):
    """202.3: il valore di mana di un costo. x=None fuori dalla pila (la X vale 0: 202.3e, 107.3g), altrimenti il numero
    annunciato. Un costo vuoto vale 0 (202.3a); il retro di una carta che si trasforma e la carta fusa prendono il valore
    delle facce davanti (202.3b, 202.3c): quello lo calcola chi conosce le facce, non questa funzione."""
    c = _costo(costo)
    return c.generico + c.x * (x or 0) + sum(max(m.quanto if m.tipo is None else 1 for m in modi) if any(m.tipo for m in modi)
                                            else max(m.quanto for m in modi) for _, modi in c.simboli)


def colori(costo):
    """202.2, 202.2d: i colori dei simboli del costo (l'incolore {C} non e' un colore: 105.1, 106.1a)."""
    return {m.tipo for _, modi in _costo(costo).simboli for m in modi if m.tipo in COLORI}


# ====================================================================== cosa si paga davvero
@dataclass(frozen=True)
class Richiesta:
    """Il costo dopo gli annunci (601.2b, 601.2f): mana per tipo (tupla nell'ordine di TIPI), generico, vite."""
    tipi: tuple
    generico: int
    vite: int
    scelte: tuple = ()                 # il modo scelto per ogni ibrido o phyrexiano, nell'ordine dei simboli

    @property
    def mana(self): return sum(self.tipi) + self.generico


def annunci(costo, x=0):
    """601.2b: tutti i modi di pagare il costo con la X annunciata. -> [Richiesta], senza doppioni, nell'ordine dei modi
    (prima il mana, poi le vite)."""
    c = _costo(costo)
    if not c.pagabile: return []                                                                   # 118.6
    if x and not c.x: raise ValueError("la X si annuncia solo se il costo ha {X} (107.3a)")
    if x < 0: raise ValueError("la X non e' mai negativa (107.1b)")
    out, visti = [], set()
    for scelta in itertools.product(*(modi for _, modi in c.simboli)):
        tipi, gen, vite = Counter(), c.generico + c.x * x, 0
        for m in scelta:
            if m.tipo: tipi[m.tipo] += m.quanto
            else: gen += m.quanto
            vite += m.vite
        r = Richiesta(tuple(tipi[t] for t in TIPI), gen, vite, scelta)
        k = (r.tipi, r.generico, r.vite)
        if k not in visti: visti.add(k); out.append(r)
    return out


# ====================================================================== la riserva e le fonti
def produzione(testo):
    """«{G}» o «{C}{C}{C}» -> la tupla del mana per tipo. Solo simboli di un tipo di mana (106.1b); un ibrido prodotto
    (106.8) qui non c'e'."""
    conta = Counter()
    for s in _SIMBOLO.findall(testo or ""):
        if s not in TIPI: raise NonCoperto(f"produrre {{{s}}} (106.5, 106.8) non e' coperto")
        conta[s] += 1
    if not conta: raise ValueError(f"una produzione senza mana: {testo!r} (106.5)")
    return tuple(conta[t] for t in TIPI)


def scrivi(mana):
    """La tupla del mana per tipo -> «{W}{W}{C}» (vuota: «{0}»)."""
    return "".join("{%s}" % t * n for t, n in zip(TIPI, mana)) or "{0}"


def produzioni(carta):
    """Le produzioni delle abilita' di mana {T} di una carta: una per tipo base se e' una terra (305.6), poi quelle scritte
    in car «mana» (una lista di alternative). -> tuple di tuple per tipo, senza doppioni."""
    out = []
    tipo = getattr(carta, "tipo", "") or ""
    davanti = tipo.split("//")[0]
    if "land" in getattr(carta, "tipi", set()) and "—" in davanti:
        for st in davanti.split("—", 1)[1].lower().split():
            if st in BASE_MANA: out.append(produzione("{%s}" % BASE_MANA[st]))                     # 305.6
    voce = (getattr(carta, "car", None) or {}).get("mana", ())
    if isinstance(voce, str): voce = (voce,)
    for p in voce: out.append(produzione(p))
    return tuple(dict.fromkeys(out))


class Riserva:
    """La riserva di mana di un giocatore (106.4), per tipo."""

    def __init__(self):
        self.m = dict.fromkeys(TIPI, 0)

    def tupla(self): return tuple(self.m[t] for t in TIPI)

    def totale(self): return sum(self.m.values())

    def aggiungi(self, mana):
        for t, n in zip(TIPI, mana): self.m[t] += n

    def paga(self, spesa):
        """118.3a, 601.2h: toglie il mana indicato; se non c'e' tutto non toglie niente. -> True se pagato."""
        if any(self.m[t] < n for t, n in zip(TIPI, spesa)): return False
        for t, n in zip(TIPI, spesa): self.m[t] -= n
        return True

    def svuota(self):
        """106.4: la riserva si svuota. -> il mana perso, per tipo."""
        perso = self.tupla()
        self.m = dict.fromkeys(TIPI, 0)
        return perso

    def __repr__(self): return scrivi(self.tupla())


# ====================================================================== il pagamento
@dataclass
class Pagamento:
    """Un pagamento legale: la richiesta annunciata, quali fonti tappare con quale produzione (indici in «fonti»), il mana
    tolto dalla riserva per tipo (spesa) e le vite."""
    richiesta: Richiesta
    usa: list = field(default_factory=list)          # [(indice della fonte, produzione)]
    spesa: tuple = (0,) * len(TIPI)

    @property
    def vite(self): return self.richiesta.vite


def _tupla(riserva):
    """Una Riserva o una tupla per tipo -> tupla (senza isinstance: il modulo lanciato a mano e quello importato dal
    tavolo sono due moduli diversi, con due classi Riserva diverse)."""
    return riserva.tupla() if hasattr(riserva, "tupla") else tuple(riserva)


def _assorbi(stato, mana):
    """Il mana di un tipo va prima al simbolo di quel tipo, il resto al generico (scambio: il generico si paga con tutto,
    107.4b, quindi non perde mai niente)."""
    manca, gen = stato
    nuovo, avanzo = [], 0
    for m, n in zip(manca, mana):
        usa = min(m, n)
        nuovo.append(m - usa)
        avanzo += n - usa
    return tuple(nuovo), max(0, gen - avanzo)


def _spesa(richiesta, disponibile):
    """Il mana da togliere: i tipi richiesti esatti, il generico prima con l'incolore e poi coi colori piu' abbondanti
    (lascia i colori che restano). -> tupla, o None se non basta."""
    resto = [d - r for d, r in zip(disponibile, richiesta.tipi)]
    if any(v < 0 for v in resto): return None
    spesa, gen = list(richiesta.tipi), richiesta.generico
    ordine = [TIPI.index("C")] + sorted(range(len(COLORI)), key=lambda k: (-resto[k], k))
    for k in ordine:
        usa = min(gen, resto[k]); spesa[k] += usa; gen -= usa
    return tuple(spesa) if gen == 0 else None


def piano(costo, fonti, riserva=(0,) * len(TIPI), x=0, vite=None):
    """Il pagamento che tappa meno fonti (e, a parita', le meno versatili), fra tutti gli annunci (601.2b). fonti: lista
    di produzioni alternative per fonte stappata; riserva: il mana gia' in riserva; vite: quante ne ha chi paga (None =
    non contano). -> Pagamento o None se il costo non si paga."""
    riserva = _tupla(riserva)
    # le meno versatili per prime: meno produzioni, poi meno colori prodotti (l'incolore prima della Forest)
    ordine = sorted(range(len(fonti)), key=lambda k: (len(fonti[k]), len({t for p in fonti[k] for t, n in zip(COLORI, p) if n}), k))
    migliore = None
    for r in annunci(costo, x):
        if r.vite and vite is not None and vite < r.vite: continue                                # 119.4
        inizio = _assorbi((r.tipi, r.generico), riserva)
        memo = {}
        def cerca(k, stato):
            if not any(stato[0]) and not stato[1]: return ()
            if k == len(ordine): return None
            chiave = (k, stato)
            if chiave in memo: return memo[chiave]
            best = None
            for p in fonti[ordine[k]]:                                           # a parita' si tappa questa
                resto = cerca(k + 1, _assorbi(stato, p))
                if resto is not None and (best is None or len(resto) + 1 < len(best)): best = ((ordine[k], p),) + resto
            salta = cerca(k + 1, stato)
            if salta is not None and (best is None or len(salta) < len(best)): best = salta
            memo[chiave] = best
            return best
        usa = cerca(0, inizio)
        if usa is None: continue
        disp = tuple(riserva)
        for _, p in usa: disp = tuple(a + b for a, b in zip(disp, p))
        spesa = _spesa(r, disp)
        if spesa is None: continue                                                                 # non succede: prova
        cand = Pagamento(r, sorted(usa), spesa)
        if migliore is None or (len(cand.usa), cand.vite) < (len(migliore.usa), migliore.vite): migliore = cand
    return migliore


def pagabile(costo, fonti, riserva=(0,) * len(TIPI), x=0, vite=None):
    return piano(costo, fonti, riserva, x, vite) is not None


def x_massimo(costo, fonti, riserva=(0,) * len(TIPI), vite=None):
    """107.3a: la X piu' grande che si riesce a pagare. -> int, None se il costo non ha {X} o non si paga nemmeno a X=0."""
    c = _costo(costo)
    if not c.x or not pagabile(c, fonti, riserva, 0, vite): return None
    tetto = sum(_tupla(riserva)) + sum(max(map(sum, f)) for f in fonti if f)
    x = 0
    while x < tetto and pagabile(c, fonti, riserva, x + 1, vite): x += 1
    return x


def valida(pag, costo, fonti, riserva=(0,) * len(TIPI), x=0, vite=None):
    """Un pagamento scelto dal giocatore e' legale? -> None se si', altrimenti il perche' con la regola."""
    riserva = _tupla(riserva)
    chiavi = {(r.tipi, r.generico, r.vite) for r in annunci(costo, x)}
    r = pag.richiesta
    if (r.tipi, r.generico, r.vite) not in chiavi: return "601.2b: non e' un modo di pagare questo costo"
    if r.vite and vite is not None and vite < r.vite: return "119.4: non ci sono abbastanza vite"
    indici = [k for k, _ in pag.usa]
    if len(set(indici)) != len(indici): return "118.3: una fonte gia' tappata non si tappa di nuovo"
    disp = list(riserva)
    for k, p in pag.usa:
        if not 0 <= k < len(fonti) or p not in fonti[k]: return "605: quella fonte non produce quel mana"
        disp = [a + b for a, b in zip(disp, p)]
    if any(s < t for s, t in zip(pag.spesa, r.tipi)): return "107.4a, 107.4c: un simbolo colorato o {C} pagato col tipo sbagliato"
    if sum(pag.spesa) != r.mana: return "601.2h: si paga il costo intero, ne' meno ne' piu'"
    if any(s > d for s, d in zip(pag.spesa, disp)): return "118.3a: si spende mana che non c'e'"
    return None


# ====================================================================== le prove
def _regolamento():
    """Motore_Opzioni/regolamento.py: le regole si leggono dal file, per numero."""
    cartella = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Motore_Opzioni")
    if cartella not in sys.path: sys.path.insert(0, cartella)
    import regolamento
    return regolamento


def _avido(costo, fonti):
    """La prova negativa: l'algoritmo avido di Companion/Suggeritore/vigila_partita.pagabile (ricopiato qui, il Companion
    e' blindato e non si importa). Ogni fonte e' un insieme di colori, i simboli si servono dal piu' stretto, la prima
    fonte che va bene si prende; {C} e i simboli sconosciuti valgono «qualsiasi colore», {2/W} vuole il bianco."""
    gen, col = 0, []
    for s in re.findall(r"\{([^}]+)\}", costo or ""):
        if s.isdigit(): gen += int(s)
        elif s != "X": col.append(set(s.split("/")) & set(COLORI) or set(COLORI))
    libere = [{t for p in f for t, n in zip(TIPI, p) if n} for f in fonti]
    if gen + len(col) > len(libere): return False
    resto = list(libere)
    for req in sorted(col, key=len):
        k = next((i for i, t in enumerate(resto) if t & req), None)
        if k is None: return False
        resto.pop(k)
    return len(resto) >= gen


def _forza_bruta(costo, fonti, riserva, x, vite):
    """Il controllo indipendente: ogni annuncio per ogni scelta di ogni fonte (non usata o una produzione). -> il numero
    minimo di fonti da tappare, None se non si paga."""
    meglio = None
    for r in annunci(costo, x):
        if r.vite and vite is not None and vite < r.vite: continue
        for scelta in itertools.product(*[(None,) + tuple(f) for f in fonti]):
            tot = list(riserva)
            for p in scelta:
                if p: tot = [a + b for a, b in zip(tot, p)]
            if all(t >= n for t, n in zip(tot, r.tipi)) and sum(tot) - sum(r.tipi) >= r.generico:
                usate = sum(p is not None for p in scelta)
                meglio = usate if meglio is None else min(meglio, usate)
    return meglio


def confronto_casuale(pagatore, n=3000, seme=14):
    """Costi e fonti a caso con i simboli di FRA (e i phyrexiani): il pagatore contro la forza bruta. -> errori."""
    rng = random.Random(seme)
    simboli = ["{1}", "{2}", "{W}", "{U}", "{G}", "{R}", "{C}", "{W/U}", "{G/W}", "{R/G}", "{2/W}", "{2/G}", "{C/G}", "{W/P}", "{X}"]
    prod = [("{W}",), ("{U}",), ("{G}",), ("{R}",), ("{C}",), ("{R}", "{W}"), ("{G}", "{W}"), ("{W}", "{U}"), ("{C}{C}",),
            ("{W}", "{U}", "{B}", "{R}", "{G}"), ("{G}{G}",)]
    errori = []
    for _ in range(n):
        costo = "".join(rng.choice(simboli) for _ in range(rng.randint(0, 4))) or "{0}"
        if costo.count("{X}") > 1: costo = costo.replace("{X}", "", costo.count("{X}") - 1)
        fonti = [tuple(produzione(p) for p in rng.choice(prod)) for _ in range(rng.randint(0, 5))]
        riserva = tuple(rng.choice((0, 0, 0, 1)) for _ in TIPI)
        x = rng.randint(0, 2) if "{X}" in costo else 0
        vite = rng.choice((None, 1, 3, 20))
        giusto = _forza_bruta(costo, fonti, riserva, x, vite)
        r = pagatore(costo, fonti, riserva, x, vite)
        si = r is not None and r is not False
        if si != (giusto is not None):
            errori.append(f"{costo} X={x} fonti {[[scrivi(p) for p in f] for f in fonti]} riserva {scrivi(riserva)}: "
                          f"dice {'si' if si else 'no'}, la forza bruta {'si' if giusto is not None else 'no'}")
        elif isinstance(r, Pagamento):
            perche = valida(r, costo, fonti, riserva, x, vite)
            if perche: errori.append(f"{costo}: pagamento illegale ({perche})")
            elif len(r.usa) != giusto: errori.append(f"{costo}: tappa {len(r.usa)} fonti, ne bastano {giusto}")
    return errori


def prove_puri():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    R = _regolamento()
    P = lambda *a: tuple(produzione(x) for x in a)

    # 107.4: ogni simbolo che la regola elenca si legge (il file, non la memoria)
    elenco = re.findall(r"\{[^}]+\}", R.regola("107.4", sotto=False))
    letti, scoperti, sbagliati = 0, [], []
    for s in elenco:
        try: leggi(s); letti += 1
        except NonCoperto: scoperti.append(s)
        except ValueError as e: sbagliati.append(f"{s}: {e}")
    caso(f"107.4: si leggono tutti i {len(elenco)} simboli della regola, tranne la neve dichiarata",
         not sbagliati and scoperti == ["{S}"], "; ".join(sbagliati) or str(scoperti))
    try: leggi("{Q}"); sconosciuto = False
    except NonCoperto: sconosciuto = False
    except ValueError: sconosciuto = True
    caso("un simbolo sconosciuto e' un errore, non «qualsiasi colore»", sconosciuto)

    # 202.3: gli esempi della regola, letti dal file
    es = re.findall(r"mana cost (?:of )?((?:\{[^}]+\})+)(?: translates to a mana value of| is) (\d+)", R.regola("202.3"))
    es += re.findall(r"card with mana cost ((?:\{[^}]+\})+) is (\d+)", R.regola("202.3"))
    giusti = [(c, int(v), valore(c)) for c, v in dict.fromkeys(es)]
    caso(f"202.3: il valore di mana degli esempi della regola ({len(giusti)})",
         len(giusti) >= 4 and all(a == b for _, a, b in giusti), str(giusti))
    caso("202.3e, 107.3g: la X vale 0 fuori dalla pila, il numero annunciato in pila",
         valore("{X}{R}") == 1 and valore("{X}{R}", x=3) == 4 and valore("{X}{X}{G}", x=2) == 5)
    caso("202.2: {2}{W} bianco, {2} incolore, {2}{W}{B} bianco e nero (gli esempi della regola)",
         colori("{2}{W}") == {"W"} and colori("{2}") == set() and colori("{2}{W}{B}") == {"W", "B"})
    caso("202.2d: gli ibridi e i phyrexiani sono di tutti i loro colori; {C} non e' un colore",
         colori("{G/W}") == {"G", "W"} and colori("{2/R}") == {"R"} and colori("{W/U/P}") == {"W", "U"} and colori("{C}{C/G}") == {"G"})

    # 107.4e, 107.4f: gli esempi della regola
    modi = {(scrivi(r.tipi), r.vite) for r in annunci("{G/W}{G/W}")}
    caso("107.4e: {G/W}{G/W} si paga con GG, GW o WW", modi == {("{G}{G}", 0), ("{W}{G}", 0), ("{W}{W}", 0)}, str(modi))
    modi = {(scrivi(r.tipi), r.vite) for r in annunci("{W/P}{W/P}")}
    caso("107.4f: {W/P}{W/P} si paga con WW, con W e 2 vite, o con 4 vite", modi == {("{W}{W}", 0), ("{W}", 2), ("{0}", 4)}, str(modi))
    caso("107.4e: {2/B} con un nero o con due mana qualsiasi",
         pagabile("{2/B}", [P("{B}")]) and pagabile("{2/B}", [P("{G}"), P("{R}")]) and not pagabile("{2/B}", [P("{G}")]))

    # pagare
    caso("107.4a: il colore si paga solo col suo colore", not pagabile("{W}", [P("{G}")]) and pagabile("{W}", [P("{W}")]))
    caso("107.4b: il generico si paga con qualsiasi tipo, incolore compreso", pagabile("{2}", [P("{C}"), P("{G}")]))
    caso("107.4c: {C} solo con mana incolore", not pagabile("{C}", [P("{G}")]) and pagabile("{C}", [P("{C}")]))
    caso("107.4d, 118.5: {0} si paga senza niente; un costo vuoto non si paga (202.1b, 118.6)",
         pagabile("{0}", []) and not pagabile("", [P("{W}")] * 5))
    caso("terre doppie: {W}{U} con una W/U e una Plains, {R}{W} con una R/W e una R/G (l'avido sbaglia qui)",
         pagabile("{W}{U}", [P("{W}", "{U}"), P("{W}")]) and pagabile("{R}{W}", [P("{R}", "{W}"), P("{R}", "{G}")]))
    caso("119.4: 2 vite per un phyrexiano solo con almeno 2 vite",
         pagabile("{W/P}", [], vite=2) and not pagabile("{W/P}", [], vite=1) and pagabile("{W/P}", [P("{W}")], vite=1))
    caso("107.3a: la X massima con tre terre per {X}{G} e' 2", x_massimo("{X}{G}", [P("{G}"), P("{W}"), P("{C}")]) == 2)
    caso("il mana gia' in riserva conta (106.4)", pagabile("{1}{G}", [P("{W}")], riserva=produzione("{G}")))
    pag = piano("{G}", [P("{G}", "{W}"), P("{G}")])
    caso("fra due fonti si tappa la meno versatile: resta stappata la doppia", pag and pag.usa == [(1, produzione("{G}"))], str(pag and pag.usa))
    pag = piano("{1}", [P("{G}"), P("{C}")])
    caso("scelta del giocatore finto, non regola: a parita' tappa la fonte incolore e tiene il colore",
         pag and pag.usa == [(1, produzione("{C}"))], str(pag and pag.usa))

    # la riserva: tutto o niente
    r = Riserva(); r.aggiungi(produzione("{W}{G}"))
    caso("118.3a, 601.2h: la riserva paga tutto o niente", not r.paga(produzione("{W}{W}")) and r.tupla() == produzione("{W}{G}")
         and r.paga(produzione("{G}")) and r.tupla() == produzione("{W}"))
    caso("106.4: svuotata, la riserva dice quanto si e' perso", r.svuota() == produzione("{W}") and r.totale() == 0)

    # valida: i pagamenti illegali del giocatore
    f = [P("{G}"), P("{W}")]
    buono = piano("{G}{W}", f)
    caso("valida: il piano e' legale", valida(buono, "{G}{W}", f) is None)
    finto = Pagamento(buono.richiesta, [(0, produzione("{G}")), (0, produzione("{G}"))], produzione("{G}{W}"))
    caso("valida: la stessa terra due volte e' illegale (118.3)", (valida(finto, "{G}{W}", f) or "").startswith("118.3"))
    finto = Pagamento(buono.richiesta, [(0, produzione("{W}")), (1, produzione("{W}"))], produzione("{W}{W}"))
    caso("valida: una Forest non da' bianco (605)", (valida(finto, "{G}{W}", f) or "").startswith("605"))

    # la forza bruta: 3000 casi a caso
    err = confronto_casuale(piano)
    caso("3000 costi e fonti a caso: piano come la forza bruta, sempre legale, sempre col minimo di fonti", not err, "; ".join(err[:2]))
    err = confronto_casuale(lambda c, f, r, x, v: _avido(c, f) if not any(r) and not x and "/P" not in c else
                            (piano(c, f, r, x, v) is not None))
    caso("prova negativa: l'algoritmo avido di oggi (vigila_partita.pagabile) risulta rosso", err, f"{len(err)} discordanze")

    # tutte le carte dello Standard: il valore di mana contro Scryfall. Senza costo e con valore > 0 puo' esserci solo
    # una carta fusa o un retro (202.3a-c): quelle note, verificate su Scryfall il 14 ott 2026 (layout «meld»), si
    # controllano con la somma delle facce davanti; una nuova e' rossa finche' non si guarda.
    FUSE = {"Ragnarok, Divine Deliverance": ("Fang, Fearless l'Cie", "Vanille, Cheerful l'Cie")}
    import json
    std = json.load(open(os.path.join(R.P.ROOT, "Regole", "standard_carte.json"), encoding="utf-8"))
    per_nome = {c["name"]: c for c in std}
    contate, diverse, doppie, fuse = 0, [], 0, 0
    for c in std:
        mc = c.get("mana_cost") or ""
        if "//" in mc: doppie += 1; continue
        contate += 1
        if not mc and c["cmc"]:
            if c["name"] in FUSE and all(n in per_nome for n in FUSE[c["name"]]):
                fuse += 1
                v = sum(valore(per_nome[n]["mana_cost"]) for n in FUSE[c["name"]])            # 202.3c
            else:
                diverse.append(f"{c['name']}: senza costo ma con valore {c['cmc']}, fusa o retro da verificare (202.3a-c)"); continue
        else: v = valore(mc)
        if v != int(c["cmc"]): diverse.append(f"{c['name']} {mc}: {v} contro {c['cmc']}")
    caso(f"Standard: il valore di mana di {contate} carte come Scryfall ({fuse} fusa per 202.3c; fuori {doppie} a due meta')",
         not diverse and contate > 4000, "; ".join(diverse[:3]))
    # i colori (202.2): in standard_carte.json «identita» e' l'identita' di colore (903.4: anche i simboli del testo) e,
    # dal 14 ott 2026, «colors» il colore della carta (fino a quel giorno «colors» era l'identita'). Lo Standard si
    # controlla per inclusione nell'identita', FRA per uguaglianza coi colori di Scryfall
    fuori = [f"{c['name']} {c['mana_cost']}" for c in std if "//" not in (c.get("mana_cost") or "")
             and not colori(c.get("mana_cost") or "") <= set(c.get("identita") or "")]
    caso("Standard: i colori del costo stanno sempre nell'identita' di colore (903.4)", not fuori, "; ".join(fuori[:3]))
    # «colors» e' il colore della carta (202.2): quello del costo, salvo devoid (702.114a) e le carte senza costo, che
    # prendono il colore dall'indicatore (202.2e, 204). Haunted Screen e' incolore: da identita' era a cinque colori
    diversi = [f"{c['name']} {c['mana_cost']}: {c['colors']}" for c in std if "//" not in (c.get("mana_cost") or "")
               and c.get("mana_cost") and "devoid" not in c["oracle"].lower()
               and "".join(sorted(colori(c["mana_cost"]))) != "".join(sorted(c.get("colors") or ""))]
    schermo = next((c for c in std if c["name"] == "Haunted Screen"), {})
    caso("Standard: «colors» e' il colore della carta, uguale ai colori del costo (202.2); Haunted Screen incolore",
         not diversi and schermo.get("colors") == "" and len(schermo.get("identita") or "") == 5, "; ".join(diversi[:3]))
    fra_sf = json.load(open(R.P.PR.file("oracle", "FRA"), encoding="utf-8"))
    normali = [c for c in fra_sf if c["layout"] == "normal"]
    col_diversi = [c["name"] for c in normali
                   if "".join(sorted(colori(c["faces"][0].get("mana_cost") or ""))) != "".join(sorted(c.get("colors") or ""))]
    caso(f"FRA: i colori dal costo come i colori di Scryfall (202.2), {len(normali)} carte a una faccia", not col_diversi and len(normali) > 250,
         "; ".join(col_diversi[:3]))

    # FRA: ogni costo si legge, ogni terra produce quello che dice il testo
    fra = json.load(open(os.path.join(R.P.ROOT, "Espansioni", "FRA", "Dati", "schede.json"), encoding="utf-8"))["carte"]
    illeggibili = []
    for nome, s in fra.items():
        try: leggi(s.get("costo") or "")
        except ValueError as e: illeggibili.append(f"{nome}: {e}")
    caso(f"FRA: si leggono i costi di tutte le {len(fra)} carte", not illeggibili, "; ".join(illeggibili[:3]))
    return casi


def prove_turno():
    """Il mana dentro il turno (turno.py): colori, terre doppie, X, phyrexiani, e la conservazione del mana."""
    import turno as T
    from inizio import inizia
    from tavolo import Tavolo, controlla, mazzo_draft_colori
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))

    def partita(Pa=T.Partita, seme=1, **kw):
        t = Tavolo([mazzo_draft_colori(**kw), mazzo_draft_colori(**kw)], seme=seme)
        inizia(t, primo=0)
        p = Pa(t); p.fase = "principale_1"
        return p
    def dai(p, i, nome, campo=False):
        o = next(o for o in p.t.giocatori[i].grimorio.carte if o.nome == nome)
        p.t._togli(o)
        o = p.t._arriva(o, "grimorio", "mano", None, None, "prova")
        return p.t.metti_in_campo(o, chi=i) if campo else o

    def regole(Pa):
        out = []
        def c(nome, ok, det=""): out.append((nome, bool(ok), det))
        p = partita(Pa); dai(p, 0, "Forest", True); cw = dai(p, 0, "Creatura W")
        c("una Forest non paga {W} (305.6, 107.4a)", p.lancia(0, cw) is None and cw in p.t.giocatori[0].mano)
        p = partita(Pa); dai(p, 0, "Forest", True); dai(p, 0, "Plains", True); gw = dai(p, 0, "Creatura GW")
        perm = p.lancia(0, gw)
        c("Forest e Plains pagano {G}{W} (305.6)", perm is not None and all(o.tappato for o in p.t.campo if "land" in o.carta.tipi))
        p = partita(Pa); dai(p, 0, "Terra doppia", True); cw = dai(p, 0, "Creatura W"); cg = dai(p, 0, "Creatura G")
        c("la terra doppia paga il bianco, poi e' tappata e il verde no", p.lancia(0, cw) is not None and p.lancia(0, cg) is None)
        p = partita(Pa)
        for n in ("Forest", "Forest", "Plains"): dai(p, 0, n, True)
        cx = dai(p, 0, "Creatura XG")
        c("{X}{G} con tre terre: X=3 no, X=2 si', e la magia in pila ha X=2 (107.3a)",
          p.lancia(0, cx, x=3) is None and p.lancia(0, cx, x=2) is not None and p.pagati[-1][2] == 2, str(p.pagati[-1:]))
        p = partita(Pa); cp = dai(p, 0, "Creatura W/P")
        c("{W/P} senza terre: si pagano 2 vite (107.4f, 119.4)", p.lancia(0, cp) is not None and p.t.giocatori[0].vite == 18)
        p = partita(Pa); p.t.giocatori[0].vite = 1; cp = dai(p, 0, "Creatura W/P")
        c("{W/P} a 1 vita senza terre non si lancia (119.4)", p.lancia(0, cp) is None and p.t.giocatori[0].vite == 1)
        p = partita(Pa); f = dai(p, 0, "Forest", True); p.tappa_per_mana(0, f)
        c("tappata, la Forest mette {G} nella riserva (305.6, 605.3b)", p.t.giocatori[0].riserva.tupla() == produzione("{G}"),
          repr(p.t.giocatori[0].riserva))
        return out
    for n, ok, det in regole(T.Partita): caso(n, ok, det)

    # 20 partite colorate: ogni pagamento legale, mana prodotto = mana speso + mana perso (106.4), invarianti del tavolo
    class Conta(T.Partita):
        def __init__(self, t):
            super().__init__(t); self.prodotto = self.speso = self.perso = 0
        def tappa_per_mana(self, i, terra, prod=None):
            prima = self.t.giocatori[i].riserva.totale()
            ok = super().tappa_per_mana(i, terra, prod)
            self.prodotto += self.t.giocatori[i].riserva.totale() - prima
            return ok
        def _svuota_mana(self):
            self.perso += sum(g.riserva.totale() for g in self.t.giocatori)
            super()._svuota_mana()
    errori, lanciate = [], 0
    for s in range(20):
        t = Tavolo([mazzo_draft_colori(), mazzo_draft_colori()], seme=s); inizia(t)
        p = Conta(t)
        def dopo(p):
            e = controlla(p.t)
            if e and not errori: errori.append(f"seme {s} turno {p.t.turno_numero}: {e[0]}")
        p.gioca({0: T.GiocaTutto(), 1: T.GiocaTutto()}, dopo_ogni_turno=dopo)
        for carta, pag, x, fonti, riserva in p.pagati:
            perche = valida(pag, carta.car["costo"], fonti, riserva, x)
            if perche and len(errori) < 3: errori.append(f"seme {s}, {carta.nome}: {perche}")
        p.speso = sum(sum(pag.spesa) for _, pag, _, _, _ in p.pagati)
        lanciate += len(p.pagati)
        if p.prodotto != p.speso + p.perso and len(errori) < 3:
            errori.append(f"seme {s}: prodotto {p.prodotto}, speso {p.speso}, perso {p.perso} (106.4)")
    caso(f"20 partite col mazzo a due colori ({lanciate} magie): pagamenti legali, il mana non si crea ne' si perde a caso",
         not errori and lanciate > 200, "; ".join(errori))

    # prove negative: una Partita che sbaglia il mana deve risultare rossa sulla regola giusta
    class SoloIncolore(T.Partita):                        # la terra da' sempre {C}: il vecchio «un mana» generico
        def produzioni(self, ogg): return (produzione("{C}"),)
    class ContaSoltanto(T.Partita):                       # guarda solo quanti mana, non quali (il passo 3)
        def piano(self, i, costo, x=0):
            return piano("{%d}" % valore(costo, x), self.fonti(i), self.t.giocatori[i].riserva, 0)
    for nome, Pa, cerca in (("la terra da' sempre incolore", SoloIncolore, "305.6"),
                            ("si contano i mana e non i colori", ContaSoltanto, "107.4a")):
        rosse = [n for n, ok, _ in regole(Pa) if not ok]
        caso(f"prova negativa: {nome} risulta rosso", any(cerca in n for n in rosse), "; ".join(rosse[:2]) or "nessuna regola rossa")
    return casi


def prova():
    casi = prove_puri() + prove_turno()
    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(prova() if "--prova" in sys.argv else print(__doc__))
