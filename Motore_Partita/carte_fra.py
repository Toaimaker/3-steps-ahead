"""Le carte vere di Reality Fracture nel motore di partita: il passo 7.2 (14 ott 2026).

Autore, 14 ott 2026: «aggiungi gli effetti conosciuti delle carte di FRA (per ogni effetto istruisci il motore sulla
meccanica reale da documentazione ufficiale) [...] non approssimiamo, non inventiamo, non tappiamo buchi».

Come si traduce una carta. La fonte e' il testo Oracle di Scryfall (Espansioni/FRA/Comune/carte_complete.json), non il catalogo del
motore delle opzioni, che e' una lettura per il valore e perde pezzi (Prophesied End: «If it wasn't attacking, its
controller draws a card» nel catalogo e' solo «pesca 1»). Il testo si divide nelle sue abilita', una per paragrafo
(113.2c); il testo di richiamo fra parentesi non e' regola e si toglie (207.2: «reminder text»). Ogni paragrafo si
traduce solo se combacia per intero con un modello di frase scritto qui, e il modello dice quale istruzione del motore
(Motore_Partita/effetti.py, ognuna con la sua regola) fa quella cosa. Un paragrafo che non combacia non si indovina:
resta fra le abilita' mancanti della carta, col perche'. Una carta con abilita' mancanti non entra in una partita del
motore (`mazzo` la rifiuta con NonCoperto): una parte che manca non e' una parte che non fa niente.

    py -I -X utf8 Motore_Partita/carte_fra.py              la copertura: carte intere, carte con mancanti, perche'
    py -I -X utf8 Motore_Partita/carte_fra.py "Nome"       come il motore legge una carta
    py -I -X utf8 Motore_Partita/carte_fra.py --prova      le prove sulle carte vere
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effetti as E
from mana import NonCoperto

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _progetto():
    """Companion/progetto.py caricato dal suo file, senza toccare il sys.path: Motore_Partita ha moduli con lo stesso nome
    di quelli del Companion (tavolo.py). Il set si passa sempre (16 ott 2026)."""
    import importlib.util
    if "progetto" not in sys.modules:
        sp = importlib.util.spec_from_file_location("progetto", os.path.join(ROOT, "Companion", "progetto.py"))
        sys.modules["progetto"] = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(sys.modules["progetto"])
    return sys.modules["progetto"]


FONTE = _progetto().file("oracle", "FRA")
BASE = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}

TIPI_NON_TERRA = ("artifact", "battle", "creature", "enchantment", "instant", "kindred", "planeswalker", "sorcery")   # 205.2a, ruling di
                                                                                                    # Grime Gorger (29 apr 2022)
PAROLE_SEMPLICI = {"flying", "trample", "vigilance", "menace", "haste", "reach", "deathtouch", "lifelink", "first strike",
                   "double strike", "defender", "hexproof", "indestructible", "flash"}
def _parole_abilita():
    """207.2c: le parole d'abilita', lette dal regolamento (14 nov 2026)."""
    f = os.path.join(ROOT, "Regole", "MagicCompRules.txt")
    riga = next((r for r in open(f, encoding="utf-8") if r.startswith("207.2c")), "")
    lista = riga.split("The ability words are")[-1].replace(" and ", " ").rstrip(". \n")
    return {w.strip().replace("’", "'") for w in lista.split(",") if w.strip()}


PAROLE_ABILITA = _parole_abilita()


def _parole_chiave():
    """702: i nomi delle parole chiave, dai titoli del regolamento («702.178. Max speed»): un prefisso «X —» che e' una di
    queste ha un significato di regola e non si toglie (14 nov 2026)."""
    f = os.path.join(ROOT, "Regole", "MagicCompRules.txt")
    return {m.group(1).lower() for r in open(f, encoding="utf-8") for m in [re.match(r"702\.\d+\. (.+)", r.strip())] if m}


PAROLE_CHIAVE = _parole_chiave()
TIPI_FILTRO = {"artifact", "creature", "enchantment", "land", "planeswalker", "instant", "sorcery", "battle", "permanent"}   # 205.2a
ROMANI = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}                                   # 715.2a
NUMERI = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "x": "X"}


# Il posto di ogni set (carte_set.py, 14 nov 2026): una funzione (c, low, orig, car, ctx, info) -> True se il paragrafo e'
# letto dal modulo del set della carta. None per FRA e per chi usa solo questo file: la lettura resta quella di sempre.
AGGANCIO = None
AGGANCIO_FRASE = None    # (posto, frase, ctx) -> istruzioni o None: le parole d'azione di un set dentro un testo (14 nov 2026)
AGGANCIO_COSTO = None    # (posto, parte del costo) -> dict o None: i costi di un set
AGGANCIO_MAGIA = None    # (posto, paragrafi, k, car, nome) -> k dopo i paragrafi letti, o None: le parole di un set in una magia
AGGANCIO_SE = None       # (posto, resto dell'innesco) -> (resto senza il «se», {condizione}) o None: il «se» (603.4) di un set
AGGANCIO_SE_STATICA = None   # (posto, condizione) -> {condizione} o None: il «as long as» (611.3a) di un set
AGGANCIO_FINE = None     # (posto, car) -> None o il motivo per cui la carta resta mancante: il set rifinisce la carta letta
POSTO = None             # il posto della carta che si sta leggendo (traduci)
# Le seconde facce degli altri set, finche' il motore non le ha (712 trasformare e modali, 713 meld, 709 split, 716 avventure)
SECONDE_FACCE = {"transform": "712", "modal_dfc": "712", "meld": "713", "split": "709", "adventure": "716", "flip": "710"}


class Mancante(Exception):
    """Un paragrafo che nessun modello legge per intero."""


def numero(s):
    s = s.lower()
    if s in NUMERI: return NUMERI[s]
    if s.isdigit(): return int(s)
    raise Mancante(f"numero {s!r}")


def normalizza(testo, nome, corto):
    """Il paragrafo come lo leggono i modelli: il nome della carta (e il nome corto, «Arni» per «Arni, Humble Scribe»)
    diventa «~», tutto minuscolo, via la parola d'abilita' in testa («Landfall —»: 207.2c, nessun significato di regola)."""
    t = testo.replace(nome, "~")
    w = nome.split()
    if "," not in nome and len(w) >= 3:                                                          # «Captain Kirk» per Captain James T. Kirk
        t = re.sub(r"\b" + re.escape(f"{w[0]} {w[-1]}") + r"\b", "~", t)                           # (TRK, 14 nov 2026)
    if len(corto) > 2: t = re.sub(r"\b" + re.escape(corto) + r"\b", "~", t)
    t = re.sub(r"^[A-Z][a-z]+ — (?=[A-Z{~])", "", t)
    m_ = re.match(r"^([A-Z][a-z'’]+(?: [a-z'’]+){1,2}) — (?=[A-Z{~])", t)                          # 207.2c: le parole d'abilita' di piu'
    if m_ and m_.group(1).lower() in PAROLE_ABILITA: t = t[m_.end():]                               # parole («Strange new worlds —»)
    m_ = re.match(r"^([A-Z][A-Za-z'’!,.-]*(?: [A-Za-z'’!,.-]+){0,4}) — (?=When |Whenever |At |\{)", t)   # 207.2d: una flavor word
    if m_ and m_.group(1).lower() not in PAROLE_CHIAVE: t = t[m_.end():]                           # davanti a un innesco o a un
                                                                                                 # costo, se non e' una parola chiave                                              # anche «Domain — ~'s power»
    return t.lower()


def senza_nome_modo(t):
    """207.2d (14 nov 2026): il nome di un modo («Temba, his arms wide — Target creature ...», «Puff piece — ...») e' una
    flavor word: senza significato di regola, si toglie; non una parola chiave (702) e non un costo («— {2} —»)."""
    m = re.match(r"^([^—{}:]{1,60}?) — (?!\{)", t)
    if m and m.group(1).strip().lower() not in PAROLE_CHIAVE: return t[m.end():]
    return t


def pulisci(testo):
    """207.2: il testo di richiamo fra parentesi non e' regola."""
    testo = re.sub(r"\s*\([^()]*\)", "", testo or "")
    return testo.replace("−", "-").strip()


# ====================================================================== i bersagli
COLORI = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
TIPO = {"creature": "creature", "planeswalker": "planeswalker", "permanent": "permanent", "artifact": "artifact",
        "enchantment": "enchantment", "land": "land", "player": "player", "opponent": "player", "spell": "spell"}


def bersaglio(frase):
    """«target creature or planeswalker an opponent controls» -> la richiesta (115). None se non e' un bersaglio letto."""
    r_ = _bersaglio_base(frase)
    return r_ if r_ is not None else bersaglio_esteso(frase)


def bersaglio_esteso(frase):
    """115.1, 205.4b (15 nov 2026): l'ultimo tentativo per un bersaglio che _bersaglio_base non legge: i «non» davanti al tipo
    che quella non conosce, «nontoken» (111.1), «non-Assassin» (un sottotipo), «nonenchantment», anche in fila con la virgola
    («nonland, nontoken permanent»), tolti e messi come filtri; il resto lo legge _bersaglio_base. None se non si legge."""
    m = re.match(r"^((?:up to (?:one|two|three) )?(?:another |other )?target )(.+)$", frase.strip())
    if not m: return None
    resto, filtri, non_tipi = m.group(2), {}, []
    while True:
        mn = re.match(r"(nontoken|non-([a-z]+)|non([a-z]+)),? ", resto)
        if not mn: break
        if mn.group(1) == "nontoken": filtri["non_pedina"] = True
        elif mn.group(2):
            if mn.group(2) not in TIPI_CREATURA and mn.group(2) not in SOTTOTIPI_205: return None
            filtri.setdefault("non_sottotipi", []).append(mn.group(2).title())
        elif mn.group(3) in TIPI_FILTRO - {"permanent"}: non_tipi.append(mn.group(3))
        else: return None
        resto = resto[mn.end():]
    if not filtri and not non_tipi: return None
    r_ = _bersaglio_base(m.group(1) + resto)
    if r_ is None: return None
    r_ = dict(r_, **filtri)
    if non_tipi: r_["non_tipi"] = list(r_.get("non_tipi") or []) + [w for w in non_tipi if w not in (r_.get("non_tipi") or [])]
    return r_


def _bersaglio_base(frase):
    f = frase.strip()
    r = {}
    m = re.match(r"^(up to (one|two|three) )?(another |other )?target (.+)$", f)
    if f == "any target": return {"chi": ["any"]}
    if not m: return None
    if m.group(4) in ("card from a graveyard",):                                                # 115.2: una carta in un cimitero
        r = {"chi": ["card"], "zona": "cimitero"}
        if m.group(1): r["fino_a"], r["quanti"] = True, numero(m.group(2))
        return r
    if m.group(4) == "cards from a single graveyard" and m.group(1):                             # 115.2, 601.2c (14 nov 2026): tutte
        return {"chi": ["card"], "zona": "cimitero", "fino_a": True, "quanti": numero(m.group(2)), "stesso_cimitero": True}   # nello stesso
    if m.group(1): r["fino_a"], r["quanti"] = True, numero(m.group(2))
    if m.group(3): r["altra"] = True
    resto = m.group(4)
    m2 = re.search(r" that's (\w+) or (\w+)$", resto)
    if m2 and m2.group(1) in COLORI and m2.group(2) in COLORI and (" controls that's" in resto):
        r["colori"] = [COLORI[m2.group(1)], COLORI[m2.group(2)]]; resto = resto[:m2.start()]
    if resto.endswith(" that entered this turn"): r["entrata_nel_turno"] = True; resto = resto[: -len(" that entered this turn")]
    m2 = re.search(r" with mana value (\d+) or (greater|less)$", resto)
    if m2:                                                                                       # «... an opponent controls with mana value 3 or less»
        r["mv_min" if m2.group(2) == "greater" else "mv_max"] = int(m2.group(1)); resto = resto[:m2.start()]
    if resto.endswith(" with a +1/+1 counter on it"): r["con_segnalino"] = "+1/+1"; resto = resto[: -len(" with a +1/+1 counter on it")]
    if resto.endswith(" that attacked this turn"): r["ha_attaccato_turno"] = True; resto = resto[: -len(" that attacked this turn")]
    if resto.startswith("tapped "): r["tappata"] = True; resto = resto[len("tapped "):]                                    # 701.26a
    if resto.startswith("attacking or blocking "): r["in_combattimento"] = True; resto = resto[len("attacking or blocking "):]   # 506.4
    elif resto.startswith("attacking "): r["attaccante_ora"] = True; resto = resto[len("attacking "):]                        # 506.4
    m2 = re.search(r" with power (\d+) or less$", resto)
    if m2: r["forza_max"] = int(m2.group(1)); resto = resto[:m2.start()]
    m2 = re.search(r" with power (\d+) or greater$", resto)
    if m2: r["forza_min"] = int(m2.group(1)); resto = resto[:m2.start()]
    if resto in ("creature or vehicle", "creature or spacecraft"):                              # 301.7: un veicolo e' un artefatto
        r["chi"], r["o_sottotipo"] = ["creature", "artifact"], resto.split()[-1].title()
        return r
    for coda, k, v in ((" an opponent controls", "controllo", "avversario"), (" you don't control", "controllo", "avversario"),
                       (" you control", "controllo", "tuo")):                                    # «you don't control»: in due giocatori
        if resto.endswith(coda): r[k] = v; resto = resto[:-len(coda)]                            # e' l'avversario (102.2)
    if resto in ("creature or vehicle", "creature or spacecraft"):                              # 301.7 (14 nov 2026): col controllo
        r["chi"], r["o_sottotipo"] = ["creature", "artifact"], resto.split()[-1].title()
        return r
    if resto in TIPI_CREATURA and resto not in TIPO:                                            # 205.3m (14 nov 2026): «target Elf you control»
        r["chi"], r["sottotipo"] = ["permanent"], resto.title()
        return r
    if resto in ("vehicle", "spacecraft"):                                                      # 301.7: solo il sottotipo
        r["chi"], r["sottotipo"] = ["artifact"], resto.title()
        return r
    if resto.startswith("nonbasic "): r["non_base"] = True; resto = resto[len("nonbasic "):]    # 205.4a
    m2 = re.search(r" with mana value (\d+) or (greater|less)$", resto)
    if m2:
        r["mv_min" if m2.group(2) == "greater" else "mv_max"] = int(m2.group(1)); resto = resto[:m2.start()]
    m2 = re.search(r" with toughness (\d+) or greater$", resto)
    if m2: r["costituzione_min"] = int(m2.group(1)); resto = resto[:m2.start()]
    m2 = re.search(r" with flying$", resto)
    if m2:
        resto = resto[:m2.start()]
        altri = [w for w in re.split(r",? or |, ", resto) if w and w != "creature"]
        if resto.endswith("creature") and altri:                                                 # «artifact, enchantment, or creature with flying»
            r["con_parole_solo"] = {"parole": ["flying"], "tranne": altri}                       # il volo vale solo per la creatura
        else: r["con_parole"] = ["flying"]
    m2 = re.search(r" that's (\w+) or (\w+)$", resto)
    if m2 and m2.group(1) in COLORI and m2.group(2) in COLORI:
        r["colori"] = [COLORI[m2.group(1)], COLORI[m2.group(2)]]; resto = resto[:m2.start()]
    m2 = re.match(r"^(\w+) or (\w+) (creature or planeswalker|spell|creature)$", resto)
    if m2 and m2.group(1) in COLORI and m2.group(2) in COLORI:
        r["colori"] = [COLORI[m2.group(1)], COLORI[m2.group(2)]]; resto = m2.group(3)
    if resto.startswith("noncreature, nonland "): r["non_tipi"] = ["creature", "land"]; resto = resto[21:]
    if resto.startswith("nonland "): r["non_tipi"] = ["land"]; resto = resto[8:]
    if resto.startswith("noncreature "): r["non_tipi"] = ["creature"]; resto = resto[12:]
    if resto.startswith("legendary "): r["leggendario"] = True; resto = resto[10:]
    if resto.startswith("nonlegendary "): r["non_leggendario"] = True; resto = resto[13:]
    parti = re.split(r",? or |, | and/or ", resto)
    chi = []
    for x in parti:
        x = x.strip()
        if x.endswith("s") and x[:-1] in TIPO: x = x[:-1]
        if x not in TIPO: return None
        chi.append(TIPO[x])
    if "opponent" in parti:
        r["controllo"] = "avversario"
    r["chi"] = chi
    if len(chi) > 1 and chi[-1] == "creature" and ("forza_min" in r or "forza_max" in r):        # «artifact, ..., or creature with power N
        sc = {"tranne": chi[:-1]}                                                                #  or greater»: la forza solo per la creatura
        for k_ in ("forza_min", "forza_max"):
            if k_ in r: sc[k_] = r.pop(k_)
        r["solo_creatura"] = sc
    return r


def selettore(frase):
    """«creatures you control», «other creatures you control», «each creature», «each other creature you control»."""
    s_ = _selettore_base(frase)
    return s_ if s_ is not None else selettore_esteso(frase)


def selettore_esteso(frase):
    """608.2c, 611.2c (15 nov 2026): l'ultimo tentativo per un gruppo che _selettore_base non legge, a pezzi: «each/all»,
    «other», «untapped/tapped/attacking», «nonland/noncreature», un tipo di creatura davanti («Merfolk creatures»), il tipo
    («creatures», «permanents», «artifacts», «lands», «enchantments»), il controllo, «with counters on them», «with mana value N
    or less», «other than this creature». Altro: None."""
    f = frase.strip()
    f = re.sub(r"^(each|all) ", "", f)
    sel = {}
    m = re.search(r" other than (?:this creature|~)$", f)
    if m: sel["altre"] = True; f = f[:m.start()]
    m = re.search(r" with (?:one or more )?counters on (?:them|it)$| with a counter on it$", f)
    if m: sel["con_segnalini"] = True; f = f[:m.start()]
    m = re.search(r" with mana value (\d+) or less$", f)
    if m: sel["mv_max"] = int(m.group(1)); f = f[:m.start()]
    for coda, v in ((" your opponents control", "avversario"), (" an opponent controls", "avversario"), (" you don't control", "avversario"),
                    (" you control", "tuo")):                                                      # «you don't control»: in due (102.2)
        if f.endswith(coda): sel["controllo"] = v; f = f[:-len(coda)]; break
    if f.startswith("other "): sel["altre"] = True; f = f[6:]
    for pre, k, v in (("untapped ", "stappata", True), ("tapped ", "tappata", True), ("attacking ", "attaccante", True),
                      ("nonland ", "non_tipi", ["land"]), ("noncreature ", "non_tipi", ["creature"])):
        if f.startswith(pre): sel[k] = v; f = f[len(pre):]
    mt_ = re.fullmatch(r"(artifacts|creatures|enchantments|lands|planeswalkers) and (artifacts|creatures|enchantments|lands|planeswalkers)", f)
    if mt_:                                                                                       # giro 7: «all artifacts and creatures»
        sel["tipi"] = [mt_.group(1)[:-1], mt_.group(2)[:-1]]
        return sel
    voci_ = [v for v in re.split(r",? (?:and/or|and|or) |, ", f) if v]
    if len(voci_) > 1:                                                                            # giro 11: un elenco di tipi e sottotipi
        tb_ = {"creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment", "lands": "land", "planeswalkers": "planeswalker",
               "creature": "creature", "artifact": "artifact", "enchantment": "enchantment", "land": "land", "planeswalker": "planeswalker"}
        tipi_, sott_ = [], []
        for v in voci_:
            if v in tb_: tipi_.append(tb_[v]); continue
            st_ = v if v in TIPI_CREATURA else singolare(v)                                        # 205.3m
            if st_ is None and v in SOTTOTIPI_205: st_ = v                                         # 205.3g-k: «Spacecraft», «Vehicle»
            if st_ is None and v.endswith("s") and v[:-1] in SOTTOTIPI_205: st_ = v[:-1]
            if st_ is None: return None
            sott_.append(st_.title())
        if sott_ and tipi_ and len(tipi_) == 1 and len(sott_) == 1: sel.update(tipi=tipi_, o_sottotipo=sott_[0]); return sel
        if sott_ and not tipi_: sel.update(tipi=["permanent"], sottotipi_o=sott_); return sel
        if tipi_ and not sott_: sel["tipi"] = tipi_; return sel
        return None
    w = f.split()
    if not w: return None
    base = {"creature": "creature", "creatures": "creature", "permanent": "permanent", "permanents": "permanent", "artifact": "artifact",
            "artifacts": "artifact", "land": "land", "lands": "land", "enchantment": "enchantment", "enchantments": "enchantment"}
    if len(w) == 1 and w[0] not in base and singolare(w[0]):                                      # 205.3m: «Elves», «Goblins»
        sel["sottotipo"], sel["tipi"] = singolare(w[0]).title(), ["creature"]
        return sel if set(sel) - {"tipi", "sottotipo", "controllo"} or sel.get("controllo") else None
    if w[-1] not in base or len(w) > 2: return None
    if len(w) == 2:
        if base[w[-1]] != "creature" or w[0] not in TIPI_CREATURA: return None
        sel["sottotipo"] = w[0].title()
    if base[w[-1]] == "permanent" and not sel.get("controllo") and not sel.get("non_tipi"): return None
    sel["tipi"] = [base[w[-1]]]
    if not (set(sel) - {"tipi"}): return None                                                     # «creatures»: la lettura di sempre
    return sel


def _selettore_base(frase):
    f = frase.strip()
    f = re.sub(r"^(each|all) ", "", f)
    sel = {}
    if f.startswith("other "): sel["altre"] = True; f = f[6:]
    for coda, v in ((" your opponents control", "avversario"), (" an opponent controls", "avversario"), (" you control", "tuo")):
        if f.endswith(coda): sel["controllo"] = v; f = f[:-len(coda)]
    if f.startswith("nontoken "): sel["non_pedina"] = True; f = f[9:]
    if f.endswith(" with a +1/+1 counter on it"):                                                # «each creature you control with ...»
        f = f[: -len(" with a +1/+1 counter on it")]; sel["con_segnalino"] = "+1/+1"
        for coda, v in ((" your opponents control", "avversario"), (" an opponent controls", "avversario"), (" you control", "tuo")):
            if f.endswith(coda): sel["controllo"] = v; f = f[:-len(coda)]
    if f in ("token", "tokens"): return dict(sel, pedina=True, tipi=["permanent"])
    if f in ("creatures and vehicles", "creature and vehicle"): return dict(sel, tipi=["creature"], o_sottotipo="Vehicle")   # 301.7 (14 nov 2026)
    if f in ("permanent", "permanents") and sel.get("controllo"): return dict(sel, tipi=["permanent"])   # «permanents you control»
    m = re.fullmatch(r"(creature|creatures|creature token|creature tokens|creature and planeswalker|creatures and planeswalkers|land|lands|artifact|artifacts)", f)
    if not m:
        m2 = re.fullmatch(r"([a-z]+?)s?", f)                                                     # «each Angel you control»: un sottotipo
        if m2 and sel.get("controllo") and m2.group(1) in SOTTOTIPI: return dict(sel, tipi=["permanent"], sottotipo=m2.group(1).title())
        w_ = {"elves": "elf", "dwarves": "dwarf", "wolves": "wolf"}.get(f) or (m2.group(1) if m2 else None)
        if w_ and sel.get("controllo") and w_ in TIPI_CREATURA:                                  # 205.3m (14 nov 2026): ogni tipo di creatura
            return dict(sel, tipi=["permanent"], sottotipo=w_.title())
        return None
    t = m.group(1)
    if "token" in t: sel["pedina"] = True
    if "planeswalker" in t: sel["tipi"] = ["creature", "planeswalker"]
    elif t.startswith("land"): sel["tipi"] = ["land"]
    elif t.startswith("artifact"): sel["tipi"] = ["artifact"]
    else: sel["tipi"] = ["creature"]
    return sel


# ====================================================================== le frasi d'effetto
class Contesto:
    """I bersagli dell'abilita' che si sta leggendo, per «it», «that creature», «its controller»."""

    def __init__(self, nome):
        self.nome, self.reqs, self.ultimo_chi = nome, [], None

    def nuovo(self, r):
        if getattr(self, "per_ogni_avversario", False): r = dict(r, per_ogni_avversario=True)
        self.reqs.append(r)
        return f"bersaglio:{len(self.reqs) - 1}"

    def ultimo(self):
        if not self.reqs: raise Mancante("«it» senza un bersaglio prima")
        return f"bersaglio:{len(self.reqs) - 1}"


def chi_frase(x, ctx):
    """Chi subisce: un bersaglio (nuovo), «it», «this creature», un gruppo («creatures you control»)."""
    x = x.strip()
    if x == "those creatures" and ctx.ultimo_chi == "oggetti_eventi": return "oggetti_eventi"
    if x in ("each creature target player controls", "creatures target player controls"):        # il selettore relativo a un bersaglio
        return {"tipi": ["creature"], "di_bersaglio": ctx.nuovo({"chi": ["player"]})}
    if x == "each creature except for tokens you control": return {"tipi": ["creature"], "tranne_pedine_tue": True}
    if x in ("~", "this creature", "this permanent", "this token", "this saga", "this class", "this vehicle", "this spacecraft", "this enchantment",
             "this artifact", "this land", "this planet"):                                        # 14 nov 2026: ogni permanente
        if not ctx.reqs: ctx.ultimo_chi = "fonte"                                                # «... on this creature. It gains ...»
        return "fonte"
    if x in ("this card",): return "questa_carta"
    m_ = re.fullmatch(r"each of up to (one|two|three) target creatures( you control)?", x)
    if m_: return ctx.nuovo(dict({"chi": ["creature"], "fino_a": True, "quanti": numero(m_.group(1))},   # 115.1, 601.2c
                                 **({"controllo": "tuo"} if m_.group(2) else {})))
    if x in ("enchanted creature", "equipped creature", "enchanted permanent"):
        ctx.ultimo_chi = {"attaccata": True}; return ctx.ultimo_chi
    if x in ("one or two target creatures", "one or two target creatures each"):                    # 115.6 con un minimo di uno (14 nov 2026)
        return ctx.nuovo({"chi": ["creature"], "fino_a": True, "quanti": 2, "minimo": 1})
    if x == "that token" and ctx.ultimo_chi == "create": return "create"                             # 111.1 (giro 7): la pedina appena creata
    if x in ("it", "that creature", "that permanent", "them", "he", "she", "him", "her", "the chosen creature", "the chosen permanent",
             "each of them"):
        if not ctx.reqs and ctx.ultimo_chi is not None: return ctx.ultimo_chi
        return ctx.ultimo()
    r = bersaglio(x)
    if r is not None: return ctx.nuovo(r)
    s = selettore(x)
    if s is not None:
        ctx.ultimo_chi = s; return s
    raise Mancante(f"chi: {x!r}")


PT = r"([+-]\d+|[+-]X)/([+-]\d+|[+-]X)"
PTX = r"([+-]\d+|[+-]x)/([+-]\d+|[+-]x)"
SOTTOTIPI = {"angel", "thopter", "wizard", "cat", "dragon", "beast", "knight", "zombie", "elf", "human"}


def _tipi_creatura():
    """205.3m: i tipi di creatura, letti dal regolamento (14 nov 2026)."""
    f = os.path.join(ROOT, "Regole", "MagicCompRules.txt")
    riga = next((r for r in open(f, encoding="utf-8") if r.startswith("205.3m")), "")
    lista = riga.split("All other creature types are one word long:")[-1]
    return {w.strip().rstrip(".").lower() for w in lista.split(",") if w.strip()} | {"time lord"}


TIPI_CREATURA = _tipi_creatura()


def _sottotipi_205():
    """205.3g-i: i tipi di artefatto, di incantesimo e di terra, letti dal regolamento (14 nov 2026)."""
    f = os.path.join(ROOT, "Regole", "MagicCompRules.txt")
    out = set()
    for r in open(f, encoding="utf-8"):
        if r.startswith(("205.3g", "205.3h", "205.3i", "205.3k")):
            lista = re.sub(r"\([^()]*\)", "", r.split(" types are ", 1)[-1]).replace(" and ", " ").rstrip().rstrip(".")
            out |= {w.strip().lower() for w in lista.split(",") if w.strip()}
    return out


SOTTOTIPI_205 = _sottotipi_205()
PLURALI = {"elves": "elf", "dwarves": "dwarf", "wolves": "wolf", "werewolves": "werewolf", "merfolk": "merfolk", "faeries": "faerie",
           "fungi": "fungus", "mice": "mouse", "octopi": "octopus", "sphinxes": "sphinx", "foxes": "fox", "allies": "ally"}


def singolare(w):
    """«elves» -> «elf», «goblins» -> «goblin»: None se non e' un tipo di creatura (205.3m)."""
    s = PLURALI.get(w) or (w[:-1] if w.endswith("s") else w)
    if s not in TIPI_CREATURA and w.endswith("es") and w[:-2] in TIPI_CREATURA: s = w[:-2]        # «heroes» -> «hero» (giro 8)
    return s if s in TIPI_CREATURA else None


def parole_lista(s):
    ps = [x.strip() for x in re.split(r", and |, | and ", s.strip())]
    if not all(p in PAROLE_SEMPLICI for p in ps): raise Mancante(f"parole {s!r}")
    return ps


def pedina(m_quante, p, t, colore, tipi, artefatto, con, nome):
    tipo_riga = ("Token " + ("Artifact " if artefatto else "") + "Creature — " + tipi.title()).strip()
    col = "".join(COLORI[c] for c in re.findall(r"white|blue|black|red|green", colore or ""))
    d = {"fa": "pedina", "quante": numero(m_quante), "nome": (nome or tipi.split()[-1]).title(), "tipo": tipo_riga,
         "forza": int(p), "costituzione": int(t), "colori": col, "parole": parole_lista(con) if con else []}
    return d


def _pedina_prowess(d_fn):
    """702.108a (14 nov 2026): una pedina «with prowess» ha l'abilita' innescata della parola chiave, come una carta."""
    def f(m_quante, p, t, colore, tipi, artefatto, con, nome):
        ps = [x.strip() for x in re.split(r", and |, | and ", con.strip())] if con else []
        if "prowess" not in ps: return d_fn(m_quante, p, t, colore, tipi, artefatto, con, nome)
        resto = [x for x in ps if x != "prowess"]
        d = d_fn(m_quante, p, t, colore, tipi, artefatto, ", ".join(resto) if resto else None, nome)
        d["parole"] = list(d["parole"]) + ["prowess"]
        d["abilita"] = list(d.get("abilita") or []) + [{"tipo": "innescata", "da_parola": "prowess", "quando": {"evento": "lanci", "non_tipi": ["creature"]},
                                                        "fa": [{"fa": "pompa", "chi": "fonte", "p": 1, "t": 1, "durata": "fine_turno"}]}]
        return d
    return f


pedina = _pedina_prowess(pedina)


# 111.10: le pedine predefinite, col testo della regola (letto dal file il 14 nov 2026); l'abilita' si legge col lettore
PREDEFINITE = {"treasure": ("Token Artifact — Treasure", None),                                   # 111.10a: abilita' di mana
               "food": ("Token Artifact — Food", "{2}, {T}, Sacrifice this token: You gain 3 life."),          # 111.10b
               "shard": ("Token Enchantment — Shard", "{2}, Sacrifice this token: Scry 1, then draw a card."), # 111.10e
               "clue": ("Token Artifact — Clue", "{2}, Sacrifice this token: Draw a card."),                   # 111.10f
               "blood": ("Token Artifact — Blood", "{1}, {T}, Discard a card, Sacrifice this token: Draw a card."),   # 111.10g
               "lander": ("Token Artifact — Lander", "{2}, {T}, Sacrifice this token: Search your library for a basic land card, "
                          "put it onto the battlefield tapped, then shuffle."),                                 # 111.10u
               "mutagen": ("Token Artifact — Mutagen", "{1}, {T}, Sacrifice this token: Put a +1/+1 counter on target creature. "
                           "Activate only as a sorcery.")}                                                       # 111.10v


def abilita_pedina(testo, tipo):
    """113.1a, 111.4 (14 nov 2026): l'abilita' scritta tra virgolette di una pedina, letta col lettore intero come il testo di
    una piccola carta («this token» = «this creature»; gli agganci dei posti valgono). -> le parti per l'istruzione pedina."""
    testo_ = re.sub(r"\bthis token\b", "this creature", testo)
    finta = {"faces": [{"name": "Token", "mana_cost": "", "type": tipo.replace("Token ", ""), "oracle": testo_[:1].upper() + testo_[1:]}],
             "_posto": POSTO}
    tr = _traduci(finta)
    if tr.mancanti: raise Mancante(f"111.4: l'abilita' della pedina non si legge ({tr.mancanti[0][1]})")
    car = tr.voce[2]
    extra = {k: v for k, v in car.items() if k not in ("costo", "parole", "abilita", "forza", "costituzione", "fedelta")}
    out = {"abilita": car.get("abilita") or []}
    if car.get("parole"): out["parole_extra"] = car["parole"]
    if extra: out["car_extra"] = extra
    return out


def pedina_predefinita(nome, quante=1, tappata=False):
    tipo, testo = PREDEFINITE[nome]
    d = {"fa": "pedina", "quante": quante, "nome": nome.capitalize(), "tipo": tipo, "colori": ""}
    if testo is None: d.update(mana=["{W}", "{U}", "{B}", "{R}", "{G}"], mana_sacrifica=True)
    else:
        ab = attivata(testo, normalizza(testo, "Token", "Token"), Contesto("Token"))
        if not ab or ab == "mana": raise Mancante(f"111.10: l'abilita' della pedina {nome} non si legge")
        d["abilita"] = ab
    if tappata: d["tappata"] = True
    return d


def frase(s, ctx, x_ammessa=False):
    """Una frase d'effetto -> le istruzioni del motore. Mancante se nessun modello la legge per intero. x_ammessa: la X
    della frase e' una quantita' da contare (la dice «where X is»)."""
    s = s.strip().rstrip(".")
    if AGGANCIO_FRASE is not None and POSTO is not None:                                          # la frase di un set, nel suo posto
        r_ = AGGANCIO_FRASE(POSTO, s, ctx)
        if r_ is not None: return r_
    s = re.sub(r"^you ", "", s) if re.match(r"^you (draw|gain|lose|may draw|create)", s) else s
    m0 = re.match(r"^for each opponent, (.+?) target (.+?) that player controls(.*)$", s)
    if m0:                                                                                       # in due giocatori: un bersaglio solo
        s = f"{m0.group(1)} target {m0.group(2)} an opponent controls{m0.group(3)}"
        ctx.per_ogni_avversario = True
    m = re.fullmatch(r"(target instant or sorcery card in your graveyard) gains flashback until end of turn", s)
    if m: return [{"fa": "dai_flashback", "chi": ctx.nuovo({"chi": ["card"], "zona": "cimitero", "controllo": "tuo", "tipi": ["instant", "sorcery"]})}]
    m = re.fullmatch(r"put a \+1/\+1 counter on (target creature) for each (land|creature|artifact) you control", s)
    if m: return [{"fa": "segnalini", "tipo": "+1/+1", "n": {"conta": {"tipo": "controlli", "sel": {"controllo": "tuo", "tipi": [m.group(2)]}}},
                   "chi": chi_frase(m.group(1), ctx)}]
    m = re.fullmatch(r"until end of turn, whenever you tap an? (plains|island|swamp|mountain|forest) for mana, add an additional (\{[wubrgc]\})", s)
    if m:                                                                                        # 603.7, 605.1b, 605.4a, 106.12a
        return [{"fa": "mana_in_piu", "sottotipo": m.group(1).title(), "mana": m.group(2).upper(), "durata": "fine_turno"}]
    m = re.fullmatch(r"(until your next turn|until end of turn), whenever (.+?), (.+)", s)
    if m:                                                                                        # 603.7, 603.7b: con una durata
        cond = m.group(2)
        RIT = {"one or more creatures attack one of your opponents": ({"evento": "attacca_avversario", "una_per_azione": True}, "oggetti_eventi"),
               "a creature attacks you or a planeswalker you control": ({"evento": "attacca_te_o_pw"}, "oggetto_evento"),
               "~ deals combat damage to a player": ({"evento": "danno_a_giocatore"}, None)}
        if cond not in RIT: raise Mancante(f"innesco ritardato {cond!r}")
        q, quelli = RIT[cond]
        c = Contesto(ctx.nome)
        c.ultimo_chi = quelli
        fa = frasi(m.group(3).rstrip(".") + ".", c)
        if c.reqs: raise Mancante("bersagli in un'abilita' ritardata")
        return [{"fa": "ritardata", "fino": "prossimo_turno" if m.group(1) == "until your next turn" else "fine_turno",
                 "ab": {"tipo": "innescata", "quando": q, "fa": fa}}]
    m = re.fullmatch(r'(target land) gains "\{t\}: add ((?:\{[wubrgc]\})+)" until this card is cast from exile', s)
    if m:                                                                                        # 613.1f, 605.1a, 611.2a, 400.7j
        return [{"fa": "dai_mana", "chi": chi_frase(m.group(1), ctx), "mana": m.group(2).upper(), "durata": "finche_lanciata_dall_esilio"}]
    m = re.fullmatch(r"search your library for up to (x|one|two|three|four|five) basic land cards with different names, reveal them, "
                     r"put them into your hand", s)
    if m:                                                                                        # 701.23a-b, 107.3m (la X della magia)
        return [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "mano", "quante": numero(m.group(1)), "fino_a": True, "nomi_diversi": True}]
    if s == ("until end of turn, you may activate loyalty abilities of jace planeswalkers you control on any player's turn any time "
             "you could cast an instant"):                                                       # 606.3, 117.1a, 514.2: un permesso
        return [{"fa": "fedelta_rapida", "sottotipo": "Jace", "durata": "fine_turno"}]
    if s == "exile all but the bottom card of each opponent's library": return [{"fa": "esilia_tranne_fondo", "chi": "avversari"}]
    m = re.fullmatch(r"draw (a|one|two|three|four|x) cards?", s)
    if m: return [{"fa": "pesca", "n": numero(m.group(1))}]
    m = re.fullmatch(r"target player draws (a|one|two|three) cards?", s)
    if m: return [{"fa": "pesca", "n": numero(m.group(1)), "chi": ctx.nuovo({"chi": ["player"]})}]
    m = re.fullmatch(r"(gain|lose) (\d+) life", s)
    if m: return [{"fa": "guadagna" if m.group(1) == "gain" else "perde", "n": int(m.group(2))}]
    m = re.fullmatch(r"that player loses (\d+) life", s)                                            # 119.3: chi dice l'innesco
    if m and getattr(ctx, "giocatore", None): return [{"fa": "perde", "chi": ctx.giocatore, "n": int(m.group(1))}]
    m = re.fullmatch(r"target (opponent|player) sacrifices a (creature|creature or planeswalker|nonland permanent)(?: of their choice)?", s)
    if m:                                                                                        # 701.21a: sceglie chi sacrifica
        tipi_ = {"creature": ["creature"], "creature or planeswalker": ["creature", "planeswalker"],
                 "nonland permanent": ["artifact", "battle", "creature", "enchantment", "planeswalker"]}[m.group(2)]
        r_ = {"chi": ["player"], "controllo": "avversario"} if m.group(1) == "opponent" else {"chi": ["player"]}
        return [{"fa": "sacrifica", "tipi": tipi_, "chi": ctx.nuovo(r_)}]
    m = re.fullmatch(r"target opponent loses (\d+) life", s)                                       # 119.3 (14 nov 2026)
    if m: return [{"fa": "perde", "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"}), "n": int(m.group(1))}]
    if s == "investigate": return [pedina_predefinita("clue")]                                          # 701.16a
    if s == "create a token that's a copy of this creature": return [{"fa": "copia_pedina", "chi": "fonte"}]   # 707.2, 111.1
    m = re.fullmatch(r"create a token that's a copy of (target creature you control), except it has haste and \"at the beginning of the end "
                     r"step, sacrifice this token\.\"", s)
    if m and bersaglio(m.group(1)) is not None:                                                  # 707.9a, 111.1, 603.2 (14 nov 2026)
        return [{"fa": "copia_pedina", "chi": ctx.nuovo(bersaglio(m.group(1))), "parole": ["haste"],
                 "abilita": [{"tipo": "innescata", "quando": {"evento": "inizio_passo", "passo": "finale"},
                              "fa": [{"fa": "sacrifica_oggetti", "chi": "fonte"}]}]}]
    m = re.fullmatch(r"create a token that's a copy of (target [a-z -]+?), except (it's legendary|it isn't legendary|it's not legendary|"
                     r"it has ([a-z]+))", s)                                                     # 707.9a-b (giro 13): le eccezioni
    if m and bersaglio(m.group(1)) is not None and (not m.group(3) or m.group(3) in PAROLE_CHIAVE):
        d_ = {"fa": "copia_pedina", "chi": ctx.nuovo(bersaglio(m.group(1)))}
        if m.group(3): d_["parole"] = [m.group(3)]
        else: d_["leggendaria"] = m.group(2) == "it's legendary"
        return [d_]
    m = re.fullmatch(r"create a token that's a copy of (target [a-z ]+)", s)                         # 707.2, 111.1 (14 nov 2026)
    if m and bersaglio(m.group(1)) is not None: return [{"fa": "copia_pedina", "chi": ctx.nuovo(bersaglio(m.group(1)))}]
    if s == "each opponent loses x life" and x_ammessa: return [{"fa": "perde", "chi": "avversari", "n": "X"}]   # 119.3, 107.3
    m = re.fullmatch(r"return (?:it|that card) to the battlefield transformed under (your|its owner's) control", s)
    if m: return [{"fa": "ritorna_esiliata", "trasformata": True, "tuo": m.group(1) == "your"}]    # 712.11a (14 nov 2026)
    if s in ("transform ~", "transform this creature", "transform this land", "transform this artifact", "transform this enchantment",
             "transform it") and (s != "transform it" or ctx.ultimo_chi == "fonte" or not ctx.reqs):
        return [{"fa": "gira_faccia", "chi": "fonte"}]                                            # 701.27a (14 nov 2026)
    if s in ("this vehicle becomes an artifact creature", "~ becomes an artifact creature"):        # 613.1d, 301.7b (14 nov 2026)
        if not ctx.reqs: ctx.ultimo_chi = "fonte"                                                # «Put a +1/+1 counter on it»
        return [{"fa": "diventa_tipo", "chi": "fonte", "tipi": ["creature"]}]
    m = re.fullmatch(r"choose ((?:up to one )?(?:other |another )?target .+)", s)
    if m and bersaglio(m.group(1)) is not None:                                                  # 115.1, 601.2c (14 nov 2026): solo la
        ctx.nuovo(bersaglio(m.group(1))); ctx.ultimo_chi = None; return []                       # scelta; «that creature» dopo
    if s == "sacrifice another creature":                                                           # 701.21a (14 nov 2026)
        return [{"fa": "sacrifica", "tipi": ["creature"], "chi": "tu", "altra": True}]
    if s in ("attach this equipment to it", "attach it to it") and ctx.ultimo_chi != "fonte":       # 701.3a: la pedina appena creata
        return [{"fa": "attacca", "chi": "create"}]
    if s == "each opponent loses x life and you gain x life" and x_ammessa:                        # 119.3, 608.2h
        return [{"fa": "perde", "chi": "avversari", "n": "X"}, {"fa": "guadagna", "n": "X"}]
    if s == "sacrifice another creature or artifact":                                              # 701.21a
        return [{"fa": "sacrifica", "tipi": ["creature", "artifact"], "chi": "tu", "altra": True}]
    m = re.fullmatch(r"sacrifice an? (artifact or creature|creature or artifact|artifact|creature|enchantment|land)", s)
    if m: return [{"fa": "sacrifica", "tipi": m.group(1).split(" or "), "chi": "tu"}]                  # 701.21a
    if s == "put a land card from your hand onto the battlefield tapped":                              # 305.4 (non e' giocare una terra)
        return [{"fa": "dalla_mano_in_campo", "tipi": ["land"], "tappata": True}]
    if s == "return a land card from your graveyard to your hand":                                     # 400.7 (si sceglie, non bersaglia)
        return [{"fa": "dal_cimitero_in_mano", "tipi": ["land"]}]
    m = re.fullmatch(r"pay (\d+) life", s)
    if m: return [{"fa": "paga_vite", "n": int(m.group(1))}]                                            # 119.4
    m = re.fullmatch(r"target opponent discards (a|one|two) cards?", s)
    if m: return [{"fa": "scarta", "n": numero(m.group(1)), "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"})}]   # 701.9a
    m = re.fullmatch(r"return up to (one|two|three) target (creature|permanent|nonland permanent|artifact|creature or food|land) cards? from your graveyard "
                     r"to (your hand|the battlefield)", s)
    if m and not (m.group(1) == "two" and m.group(2) == "creature" and m.group(3) == "your hand"):   # quella c'era gia', sotto
        r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo", "fino_a": True, "quanti": numero(m.group(1))}
        g2 = m.group(2)
        if g2 == "nonland permanent": r["tipi"], r["non_tipi"] = ["artifact", "battle", "creature", "enchantment", "planeswalker"], ["land"]
        elif g2 == "creature or food": r["tipi"], r["o_sottotipo"] = ["creature", "artifact"], "Food"
        elif g2 != "permanent": r["tipi"] = [g2]
        else: r["tipi"] = ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"]
        d = {"fa": "ritorna", "chi": ctx.nuovo(r)}
        if m.group(3) == "the battlefield": d["dove"] = "campo"
        return [d]
    m = re.fullmatch(r"return up to (one|two|three) target (creature|permanent|land) cards from your graveyard to your hand", s)
    if m:                                                                                        # 115.1, 400.7
        r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo", "fino_a": True, "quanti": numero(m.group(1))}
        if m.group(2) != "permanent": r["tipi"] = [m.group(2)]
        return [{"fa": "ritorna", "chi": ctx.nuovo(r)}]
    m = re.fullmatch(r"search your library for an? (basic )?(creature|artifact|land|plains|island|swamp|mountain|forest) card, reveal it, "
                     r"put it into your hand(?:, then shuffle)?", s)
    if m:                                                                                        # 701.23a, 701.24b
        tipo = ([ "Basic"] if m.group(1) else []) + [m.group(2).capitalize()]
        return [{"fa": "cerca", "tipo": tipo, "dove": "mano"}]
    m = re.fullmatch(r"create (a|an|one|two|three) tapped (\d+)/(\d+) ((?:white|blue|black|red|green|colorless)(?: and (?:white|blue|black|red|green))?) "
                     r"((?:[a-z]+ )+?)(artifact )?creature tokens?", s)
    if m:                                                                                        # 111.4, «tapped»
        return [dict(pedina(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5).strip(), bool(m.group(6)), None, None), tappata=True)]
    if s == "attach it to target creature you control":                                                # 701.3a, 301.5
        return [{"fa": "attacca", "chi": ctx.nuovo({"chi": ["creature"], "controllo": "tuo"})}]
    m = re.fullmatch(r"(target creature|it) can't block this turn", s)
    if m:                                                                                        # 509.1b, 611.2a
        c = chi_frase(m.group(1), ctx)
        return [{"fa": "non_blocca", "chi": c, "durata": "fine_turno"}]
    if s == "if that creature would die this turn, exile it instead":                                    # 614.1a
        return [{"fa": "esilia_se_muore", "chi": ctx.ultimo()}]
    m = re.fullmatch(r"counter target spell unless its controller pays (\{\d\})", s)
    if m: return [{"fa": "contrasta_salvo", "chi": ctx.nuovo({"chi": ["spell"]}), "costo": m.group(1).upper()}]   # 701.6a
    m = re.fullmatch(r"draw a card and lose (\d+) life", s)
    if m: return [{"fa": "pesca", "n": 1}, {"fa": "perde", "chi": "tu", "n": int(m.group(1))}]                    # 121.1, 119.3
    m = re.fullmatch(r"(?:you )?gain (\d+) life and draw a card", s)
    if m: return [{"fa": "guadagna", "n": int(m.group(1))}, {"fa": "pesca", "n": 1}]
    m = re.fullmatch(r"each opponent loses (\d+) life", s)
    if m: return [{"fa": "perde", "n": int(m.group(1)), "chi": "avversari"}]
    m = re.fullmatch(r"(?:~|this planeswalker) deals (\d+) damage to (up to one target creature or planeswalker) and (\d+) damage to (target player)", s)
    if m:                                                                                        # due quantita' a due bersagli
        return [{"fa": "danno", "n": int(m.group(1)), "chi": chi_frase(m.group(2), ctx)},
                {"fa": "danno", "n": int(m.group(3)), "chi": chi_frase(m.group(4), ctx)}]
    if s == "exile the top card of your library": return [{"fa": "esilia_cima", "n": 1}]           # 701.13a, 406.3
    m = re.fullmatch(r"exile the top (two|three) cards of your library", s)
    if m: return [{"fa": "esilia_cima", "n": numero(m.group(1))}]                                  # 701.13a, 406.3
    m = re.fullmatch(r"gain control of (target creature|target artifact or creature) until end of turn", s)
    if m: return [{"fa": "prendi_controllo", "chi": chi_frase(m.group(1), ctx), "durata": "fine_turno"}]   # 613.1b, 611.2a
    if s == "this land becomes a copy of target creature you control until end of turn":           # 707.2, 613.2a, 611.2a
        return [{"fa": "diventa_copia", "chi": ["fonte", ctx.nuovo(bersaglio("target creature you control"))], "durata": "fine_turno"}]
    if s == 'the "legend rule" doesn\'t apply to permanents you control this turn':                # 704.5j, 613.11, 514.2
        return [{"fa": "senza_leggenda", "durata": "fine_turno"}]
    if s == "create a token that's a copy of it" and ctx.ultimo_chi == "fonte_com_era":
        return [{"fa": "copia_pedina", "chi": "fonte_com_era"}]                                     # 707.2, 111.1
    m = re.fullmatch(r"for each creature target player controls, create a token that's a copy of that creature, except it has (.+?) and \"(.+)\"", s)
    if m:                                                                                        # Face Yourself: 707.9a, le eccezioni
        ab = innesco(m.group(2).rstrip(".") + ".", Contesto(ctx.nome))
        if not ab: raise Mancante("abilita' data alla copia non letta")
        return [{"fa": "copia_pedina", "chi": chi_frase("each creature target player controls", ctx), "parole": parole_lista(m.group(1)), "abilita": ab}]
    m = re.fullmatch(r"(~|it|this creature|this enchantment|this class|this artifact|this equipment|this planeswalker|this emblem) deals (\d+|x) damage to (.+)", s)
    if m:
        n, a = numero(m.group(2)), m.group(3)
        if a == "each opponent": return [{"fa": "danno", "n": n, "chi": "avversari"}]
        if a == "that creature's controller": return [{"fa": "danno", "n": n, "chi": "controllore_oggetto_evento"}]
        if a == "that player" and getattr(ctx, "giocatore", None): return [{"fa": "danno", "n": n, "chi": ctx.giocatore}]
        if a == "each player": return [{"fa": "danno", "n": n, "chi": "giocatori"}]
        if a == "you": return [{"fa": "danno", "n": n, "chi": "tu"}]                                   # 120.3a (14 nov 2026)
        if a in ("that creature", "that permanent") and ctx.reqs: return [{"fa": "danno", "n": n, "chi": chi_frase(a, ctx)}]   # il bersaglio di prima
        if a == "each creature except for tokens you control": return [{"fa": "danno", "n": n, "chi": {"tipi": ["creature"], "tranne_pedine_tue": True}}]
        sel = selettore(a)
        if sel is not None: return [{"fa": "danno", "n": n, "chi": sel}]
        r = bersaglio(a)
        if r is None: raise Mancante(f"danno a {a!r}")
        return [{"fa": "danno", "n": n, "chi": ctx.nuovo(r)}]
    m = re.fullmatch(r"exile (.+?) until (?:~|this enchantment|this creature|this artifact) leaves the battlefield", s)
    if m: return [{"fa": "esilia_finche", "chi": chi_frase(m.group(1), ctx)}]                       # 610.3
    m = re.fullmatch(r"(destroy|exile) (.+)", s)
    if m:
        verbo = "distruggi" if m.group(1) == "destroy" else "esilia"
        return [{"fa": verbo, "chi": chi_frase(m.group(2), ctx)}]
    m = re.fullmatch(r"return (.+) to its owner's hand", s)
    if m: return [{"fa": "rimbalza", "chi": chi_frase(m.group(1), ctx)}]
    if s == "return this card from your graveyard to your hand": return [{"fa": "ritorna", "chi": "questa_carta"}]
    m = re.fullmatch(r"return (another )?target (legendary )?(creature|permanent|land|creature or planeswalker)? ?card from your graveyard to your hand", s)
    if m:
        tipi = {"permanent": ["artifact", "creature", "enchantment", "land", "planeswalker", "battle"], None: []}.get(m.group(3), (m.group(3) or "").split(" or "))
        r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo"}
        if tipi: r["tipi"] = tipi
        if m.group(1): r["altra"] = True
        if m.group(2): r["leggendario"] = True
        return [{"fa": "ritorna", "chi": ctx.nuovo(r)}]
    m = re.fullmatch(r"return target (creature|creature or planeswalker) card(?: with mana value (\d+) or less)? from your graveyard to the battlefield"
                     r"( with an additional \+1/\+1 counter on it)?", s)
    if m:
        r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo", "tipi": m.group(1).split(" or ")}
        if m.group(2): r["mv_max"] = int(m.group(2))
        d = {"fa": "ritorna", "chi": ctx.nuovo(r), "dove": "campo"}
        if m.group(3): d["con_segnalini"] = {"+1/+1": 1}
        return [d]
    m = re.fullmatch(r"put target creature card(?: with mana value (\d+) or less)? from (a|your) graveyard onto the battlefield under your control"
                     r"(?: with an? (finality|\+1/\+1) counter on it)?", s)                        # 400.7, 404.2, 110.2 (giro 13)
    if m:
        r = {"chi": ["card"], "zona": "cimitero", "tipi": ["creature"], **({"controllo": "tuo"} if m.group(2) == "your" else {})}
        if m.group(1): r["mv_max"] = int(m.group(1))
        d = {"fa": "ritorna", "chi": ctx.nuovo(r), "dove": "campo"}
        if m.group(3): d["con_segnalini"] = {m.group(3): 1}
        return [d]
    m = re.fullmatch(r"put a loyalty counter on (each planeswalker you control|~)", s)
    if m: return [{"fa": "segnalini", "tipo": "fedelta", "n": 1, "chi": "fonte" if m.group(1) == "~" else {"tipi": ["planeswalker"], "controllo": "tuo"}}]
    m = re.fullmatch(r"if that land is a (plains|island|swamp|mountain|forest), add (\{[wubrg]\})", s)
    if m: return [{"fa": "aggiungi_mana", "mana": m.group(2).upper(), "se": {"evento_sottotipo": m.group(1).title()}}]
    m = re.fullmatch(r"put its counters on (.+)", s)
    if m: return [{"fa": "segnalini_della_fonte", "chi": chi_frase(m.group(1), ctx)}]
    m = re.fullmatch(r"(target .+?)'s owner shuffles it into their library", s)
    if m: return [{"fa": "mescola_nel_grimorio", "chi": chi_frase(m.group(1), ctx)}]                # 701.24a, 400.7
    m = re.fullmatch(r"(double|triple) (target .+?)'s power and toughness until end of turn", s)
    if m:                                                                                        # 701.10b, 613.4c: +X/+Y alla risoluzione
        return [{"fa": "moltiplica_fc", "chi": chi_frase(m.group(2), ctx), "volte": 2 if m.group(1) == "double" else 3, "durata": "fine_turno"}]
    m = re.fullmatch(r"(target .+?)'s owner puts it on their choice of the top or bottom of their library", s)
    if m: return [{"fa": "in_grimorio", "chi": chi_frase(m.group(1), ctx)}]                          # 401.1, 400.7
    m = re.fullmatch(r"the owner of (.+?) puts it on their choice of the top or bottom of their library", s)
    if m: return [{"fa": "in_grimorio", "chi": chi_frase(m.group(1), ctx)}]
    m = re.fullmatch(r"(.+?) gain (.+?) and get " + PTX + r" until end of turn", s)
    if m:                                                                                        # «gain trample and get +X/+0»
        c = chi_frase(m.group(1), ctx)
        p_, t_ = m.group(3).replace("x", "X"), m.group(4).replace("x", "X")
        iv = lambda v: v if "X" in v else int(v)
        if "X" in p_ + t_ and not x_ammessa: raise Mancante("+X/+X")
        return [{"fa": "dai_parole", "chi": c, "parole": parole_lista(m.group(2)), "durata": "fine_turno"},
                {"fa": "pompa", "chi": c, "p": iv(p_), "t": iv(t_), "durata": "fine_turno"}]
    m = re.fullmatch(r"(.+?) (?:gets|get) " + PTX + r" until your next turn", s)
    if m:                                                                                        # 611.2a: fino al prossimo turno di chi la controlla
        return [{"fa": "pompa", "chi": chi_frase(m.group(1), ctx), "p": int(m.group(2)), "t": int(m.group(3)), "durata": "prossimo_turno"}]
    m = re.fullmatch(r"(.+?) (?:gets|get) " + PTX + r"(?: and gains? (.+?))? until end of turn", s)
    if m:
        chi, p, t, ps = m.group(1), m.group(2).replace("x", "X"), m.group(3).replace("x", "X"), m.group(4)
        x_m = "X" in p + t and not x_ammessa and getattr(ctx, "x_magia", False)                  # 107.3a: la X della magia
        if "X" in p + t and not x_ammessa and not x_m: raise Mancante("+X/+X")
        c = chi_frase(chi, ctx)
        iv = (lambda v: {"conta": {"tipo": "x_magia"}} if "X" in v else int(v)) if x_m else (lambda v: v if "X" in v else int(v))
        out = [{"fa": "pompa", "chi": c, "p": iv(p), "t": iv(t), "durata": "fine_turno"}]
        if ps: out.append({"fa": "dai_parole", "chi": c if not isinstance(c, str) or not c.startswith("bersaglio") else c, "parole": parole_lista(ps), "durata": "fine_turno"})
        return out
    m = re.fullmatch(r"(.+?) gains? (.+?) until end of turn", s)
    if m and not m.group(2).startswith(("your choice", "\"")):
        return [{"fa": "dai_parole", "chi": chi_frase(m.group(1), ctx), "parole": parole_lista(m.group(2)), "durata": "fine_turno"}]
    m = re.fullmatch(r"(.+?) has base power and toughness (\d+)/(\d+) until end of turn", s)
    if m: return [{"fa": "base", "chi": chi_frase(m.group(1), ctx), "p": int(m.group(2)), "t": int(m.group(3)), "durata": "fine_turno"}]
    m = re.fullmatch(r"(.+?) loses all abilities until end of turn", s)
    if m: return [{"fa": "togli_abilita", "chi": chi_frase(m.group(1), ctx), "durata": "fine_turno"}]
    m = re.fullmatch(r"put a (\+1/\+1|loyalty) counter on it if it's a (creature|planeswalker)", s)
    if m:
        k = int(ctx.ultimo().split(":")[1])
        return [{"fa": "segnalini", "tipo": "+1/+1" if m.group(1) == "+1/+1" else "fedelta", "n": 1, "chi": ctx.ultimo(),
                 "se": {"bersaglio_era": [m.group(2)], "k": k}}]
    m = re.fullmatch(r"(put an? (?:\+1/\+1 )?counters? on ~) and draw a card", s)
    if m: return frase(m.group(1), ctx) + [{"fa": "pesca", "n": 1}]                               # due istruzioni, la stessa condizione
    m = re.fullmatch(r"put (?:a|an) (\+1/\+1 counter and an? )?(" + "|".join(SEGNALINI_PAROLA) + r") counter on (.+)", s)
    if m:                                                                                        # 122.1b (14 nov 2026): i segnalini parola
        ch = chi_frase(m.group(3), ctx)
        out = [{"fa": "segnalini", "tipo": "+1/+1", "n": 1, "chi": ch}] if m.group(1) else []
        return out + [{"fa": "segnalini", "tipo": m.group(2), "n": 1, "chi": ch}]
    m = re.fullmatch(r"put (a|one|two|three|four|five|six|seven|eight) \+1/\+1 counters? on (.+)", s)
    if m:
        dove = m.group(2)
        if dove.startswith("each of one or two target "):                                        # 115.6 con un minimo di uno
            r = bersaglio("target " + dove[len("each of one or two target "):])
            if r is None or not r["chi"] or r["chi"][0] != "creature": raise Mancante(f"bersaglio {dove!r}")
            r = dict(r, fino_a=True, quanti=2, minimo=1, chi=["creature" if c == "creatures" else c for c in r["chi"]])
            return [{"fa": "segnalini", "tipo": "+1/+1", "n": numero(m.group(1)), "chi": ctx.nuovo(r)}]
        return [{"fa": "segnalini", "tipo": "+1/+1", "n": numero(m.group(1)), "chi": chi_frase(dove, ctx)}]
    m = re.fullmatch(r"create two tapped heartwood tokens", s)
    if m:
        return [{"fa": "pedina", "quante": 2, "nome": "Heartwood", "tipo": "Token Artifact — Heartwood", "colori": "RG", "mana": ["{R}", "{G}"], "tappata": True}]
    m = re.fullmatch(r"return target land card from your graveyard to the battlefield tapped", s)
    if m: return [{"fa": "ritorna", "chi": ctx.nuovo({"chi": ["card"], "zona": "cimitero", "controllo": "tuo", "tipi": ["land"]}), "dove": "campo", "tappata": True}]
    m = re.fullmatch(r"create (a|an|one|two|three|x) (\d+)/(\d+) ((?:white|blue|black|red|green|colorless)(?: and (?:white|blue|black|red|green))?) "
                     r"((?:[a-z]+ )+?)(artifact )?creature tokens?(?: with ([a-z ,]+?))?(?: named (\w+))?", s, flags=0)
    if m:
        return [pedina(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5).strip(), bool(m.group(6)), m.group(7), m.group(8))]
    m = re.fullmatch(r"create a 3/3 green forest tentacle land creature token", s)
    if m:
        return [{"fa": "pedina", "quante": 1, "nome": "Forest Tentacle", "tipo": "Token Land Creature — Forest Tentacle", "forza": 3,
                 "costituzione": 3, "colori": "G", "parole": []}]
    if s == "create a heartwood token":
        return [{"fa": "pedina", "quante": 1, "nome": "Heartwood", "tipo": "Token Artifact — Heartwood", "colori": "RG",
                 "mana": ["{R}", "{G}"]}]                                                         # 111.10x
    m = re.fullmatch(r"(surveil|scry) (\d+)", s)
    if m: return [{"fa": m.group(1), "n": int(m.group(2))}]
    m = re.fullmatch(r"mill (a|one|two|three|four|five|six|seven|eight) cards?", s)
    if m: return [{"fa": "macina", "n": numero(m.group(1))}]
    m = re.fullmatch(r"target player mills (a|one|two|three|four|five|six|seven|eight) cards?", s)
    if m: return [{"fa": "macina", "n": numero(m.group(1)), "chi": ctx.nuovo({"chi": ["player"]})}]   # 701.17a
    m = re.fullmatch(r"empower (?:jace|~) (\d+|x)", s)
    if m: return [{"fa": "empower_jace", "n": numero(m.group(1))}]
    if s in ("put a stun counter on each of those creatures", "put a stun counter on it"):
        return [{"fa": "stordisci", "chi": ctx.ultimo(), "n": 1}]
    m = re.fullmatch(r"(tap|untap) (.+?)( and put a stun counter on it)?", s)
    if m:
        c = chi_frase(m.group(2), ctx)
        out = [{"fa": "tappa" if m.group(1) == "tap" else "stappa", "chi": c}]
        if m.group(3): out.append({"fa": "stordisci", "chi": c, "n": 1})
        return out
    m = re.fullmatch(r"counter target (creature or legendary|noncreature) spell unless its controller pays (\{\d\})", s)
    if m:
        r = {"chi": ["spell"], "tipi_o": ["creature", "legendary"]} if m.group(1) == "creature or legendary" else {"chi": ["spell"], "non_tipi": ["creature"]}
        return [{"fa": "contrasta_salvo", "chi": ctx.nuovo(r), "costo": m.group(2).upper()}]
    m = re.fullmatch(r"return this card from your graveyard to the battlefield( tapped)?(?: with an? (finality|\+1/\+1) counter on (?:it|her|him))?", s)
    if m:
        d = {"fa": "ritorna", "chi": "questa_carta", "dove": "campo"}
        if m.group(1): d["tappata"] = True
        if m.group(2): d["con_segnalini"] = {"finalita" if m.group(2) == "finality" else "+1/+1": 1}
        return [d]
    m = re.fullmatch(r"put an? (permanent|creature|land) card from among them into your hand", s)
    if m:                                                                                        # dopo «mill»
        return [{"fa": "prendi_tra_macinate", "tipi": ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"]
                 if m.group(1) == "permanent" else [m.group(1)]}]
    m = re.fullmatch(r"remove up to (one|two|three) counters from (.+)", s)
    if m: return [{"fa": "togli_segnalini_scelti", "n": numero(m.group(1)), "chi": chi_frase(m.group(2), ctx)}]
    if s == "return that card to the battlefield tapped under its owner's control":              # «When enchanted creature dies»
        return [{"fa": "ritorna", "chi": "carta_evento", "dove": "campo", "tappata": True, "sotto_proprietario": True}]
    if s == "you win the game": return [{"fa": "vinci"}]                                          # 104.2b
    if s == "sacrifice a planeswalker": return [{"fa": "sacrifica", "tipi": ["planeswalker"], "chi": "tu"}]   # 701.21a
    if s == "proliferate x times" and x_ammessa: return [{"fa": "prolifera", "n": "X"}]                # 701.34a
    if s == "proliferate": return [{"fa": "prolifera", "n": 1}]
    TESORO = {"fa": "pedina", "quante": 1, "nome": "Treasure", "tipo": "Token Artifact — Treasure", "colori": "",
              "mana": ["{W}", "{U}", "{B}", "{R}", "{G}"], "mana_sacrifica": True}                    # 111.10a
    if s == "they create a treasure token":                                                       # il controllore del bersaglio, com'era (608.2h)
        return [dict(TESORO, chi="controllore_" + ctx.ultimo())]
    if s == 'create a 1/1 colorless sculpture treasure artifact creature token with "{t}, sacrifice this token: add one mana of any color."':
        return [dict(TESORO, nome="Sculpture Treasure", tipo="Token Artifact Creature — Sculpture Treasure", forza=1, costituzione=1, parole=[])]
    if s == 'create a colorless artifact token named lotus with "{t}, sacrifice this token: add three mana of any one color."':
        return [dict(TESORO, nome="Lotus", tipo="Token Artifact — Lotus", mana=["{W}{W}{W}", "{U}{U}{U}", "{B}{B}{B}", "{R}{R}{R}", "{G}{G}{G}"])]
    m = re.fullmatch(r'create a (\d+)/(\d+) (white|blue|black|red|green) ([a-z ]+?) creature token named (.+?) with "(whenever .+?)"', s)
    if m:                                                                                        # 111.4: la pedina con un'abilita' innescata
        data = innesco(m.group(6).replace("this token", "~"), Contesto(ctx.nome))
        if not data: raise Mancante("abilita' della pedina non letta")
        return [{"fa": "pedina", "quante": 1, "nome": " ".join(w[:1].upper() + w[1:] for w in m.group(5).replace("~", ctx.nome.split(",")[0] if "," in ctx.nome else ctx.nome.split(" ")[0]).split()), "tipo": "Token Creature — " + m.group(4).title(),
                 "forza": int(m.group(1)), "costituzione": int(m.group(2)), "colori": COLORI[m.group(3)], "parole": [], "abilita": data}]
    if s == "draw that many cards" and getattr(ctx, "evento", None) in ("danno_a_giocatore", "tua_danno_giocatore"):   # 510.2, 608.2h
        return [{"fa": "pesca", "n": {"conta": {"tipo": "quanto_evento"}}}]                         # (14 nov 2026): il danno di quell'evento
    m = re.fullmatch(r"put that many \+1/\+1 counters on (~|this creature|him|her|it)", s)
    if m and getattr(ctx, "evento", None) in ("danno_ricevuto", "scarto") and (m.group(1) in ("~", "this creature") or ctx.ultimo_chi in (None, "fonte")) \
            and not ctx.reqs:                                                                    # 122.1, 608.2h (14 nov 2026): il danno
        tipo_ = "danno_ricevuto" if ctx.evento == "danno_ricevuto" else "eventi_innesco"          # dell'evento, le carte scartate insieme
        return [{"fa": "segnalini", "tipo": "+1/+1", "n": {"conta": {"tipo": tipo_}}, "chi": "fonte"}]
    if s == "search your library for up to that many land cards, put them onto the battlefield tapped":
        return [{"fa": "cerca", "tipo": ["Land"], "dove": "campo", "tappata": True, "quante": {"conta": {"tipo": "danno_ricevuto"}}}]
    m = re.fullmatch(r"target player draws (a|one|two|three) cards? and loses (\d+) life", s)
    if m:
        b = ctx.nuovo({"chi": ["player"]})
        return [{"fa": "pesca", "n": numero(m.group(1)), "chi": b}, {"fa": "perde", "n": int(m.group(2)), "chi": b}]
    if s == "each player may discard their hand and draw seven cards": return [{"fa": "ruota_scelta", "n": 7}]
    m = re.fullmatch(r"put an? charge counter on (this enchantment|this artifact|~)", s)
    if m: return [{"fa": "segnalini", "tipo": "carica", "n": 1, "chi": "fonte"}]                      # 122.1
    if s == "sacrifice it" and ctx.ultimo_chi == "fonte" and not ctx.reqs:                        # 701.21a (14 nov 2026): la fonte
        return [{"fa": "sacrifica_questo", "chi": "fonte"}]
    m = re.fullmatch(r"put an? plan counter on (this enchantment|this artifact|~)", s)
    if m: return [{"fa": "segnalini", "tipo": "plan", "n": 1, "chi": "fonte"}]                         # 122.1 (14 nov 2026)
    m = re.fullmatch(r"put an? quest counter on (this enchantment|this artifact|~)", s)
    if m: return [{"fa": "segnalini", "tipo": "quest", "n": 1, "chi": "fonte"}]                       # 122.1 (14 nov 2026)
    if s == "add {g} for each charge counter on this enchantment":
        return [{"fa": "aggiungi_mana", "mana": "{G}", "volte": {"conta": {"tipo": "segnalini_fonte", "segnalino": "carica"}}}]
    m = re.fullmatch(r"put x \+1/\+1 counters on (.+)", s)
    if m and x_ammessa: return [{"fa": "segnalini", "tipo": "+1/+1", "n": "X", "chi": chi_frase(m.group(1), ctx)}]
    if s == "remove a +1/+1 counter from this creature": return [{"fa": "togli_segnalini", "tipo": "+1/+1", "n": 1, "chi": "fonte"}]
    if s == "discard your hand": return [{"fa": "scarta", "tutta": True}]                          # 701.9a
    if s == "return all nonland permanent cards from your graveyard to the battlefield": return [{"fa": "ritorna_tutte"}]
    m = re.fullmatch(r"put (target card from your graveyard) on the bottom of your library", s)
    if m: return [{"fa": "in_fondo", "chi": ctx.nuovo({"chi": ["card"], "zona": "cimitero", "controllo": "tuo"})}]
    if s == "if that permanent would die this turn, exile it instead": return [{"fa": "esilia_se_muore", "chi": ctx.ultimo()}]
    if s == "if that creature or planeswalker would die this turn, exile it instead":                 # 614.1a (14 nov 2026)
        return [{"fa": "esilia_se_muore", "chi": ctx.ultimo()}]
    m = re.fullmatch(r"(it|~|this creature|target creature you control|target creature) connives", s)
    if m: return [{"fa": "trama", "chi": chi_frase(m.group(1), ctx)}]                             # 701.50a
    m = re.fullmatch(r"search your library for a card, put it into your hand(?:, (?:then )?shuffle)?", s)
    if m: return [{"fa": "cerca", "tipo": [], "dove": "mano"}]                                      # 701.23a
    m = re.fullmatch(r"search your library for an? (planeswalker|creature|land) card, put it onto the battlefield", s)
    if m: return [{"fa": "cerca", "tipo": [m.group(1).title()], "dove": "campo"}]                    # 701.23a
    m = re.fullmatch(r"draw cards equal to (.+)", s)
    if m: return [{"fa": "pesca", "n": {"conta": quantita(m.group(1))}}]                            # 608.2h
    m = re.fullmatch(r"(?:you )?lose life equal to (.+)", s)
    if m: return [{"fa": "perde", "n": {"conta": quantita(m.group(1))}}]
    m = re.fullmatch(r"put (x|a|one|two|three) stun counters? on (.+)", s)
    if m:
        if m.group(1) == "x" and not getattr(ctx, "x_costo", False): raise Mancante("X segnalini stordimento")
        return [{"fa": "stordisci", "chi": chi_frase(m.group(2), ctx), "n": "X" if m.group(1) == "x" else numero(m.group(1))}]
    m = re.fullmatch(r'you get an emblem with "(.+)"', s)
    if m and not re.match(r"(when|whenever|at) ", m.group(1)):                                    # 114.2: un emblema con una statica
        st = statica(m.group(1).rstrip(".") + ".", Contesto(ctx.nome))
        if not isinstance(st, list): raise Mancante("abilita' dell'emblema non letta")
        return [{"fa": "emblema", "abilita": st}]
    if m:                                                                                        # 114.2
        data = innesco(m.group(1).rstrip(".") + ".", Contesto(ctx.nome))
        if not data: raise Mancante("abilita' dell'emblema non letta")
        return [{"fa": "emblema", "abilita": data}]
    m = re.fullmatch(r"(?:~'s|its) owner shuffles (him|her|it) into their library", s)
    if m: return [{"fa": "mescola_nel_grimorio", "chi": "fonte" if s.startswith("~") else ctx.ultimo()}]
    if s == "the next spell you cast this turn can't be countered": return [{"fa": "prossima_incontrastabile"}]   # 101.2
    m = re.fullmatch(r"put (x|a|one|two|three) -1/-1 counters? on (.+)", s)
    if m:
        n_ = "X" if m.group(1) == "x" else numero(m.group(1))
        if n_ == "X" and not x_ammessa: raise Mancante("X segnalini")
        return [{"fa": "segnalini", "tipo": "-1/-1", "n": n_, "chi": chi_frase(m.group(2), ctx)}]
    m = re.fullmatch(r"(.+?) becomes prepared", s)
    if m: return [{"fa": "prepara", "chi": chi_frase(m.group(1), ctx)}]                             # 723.3a
    m = re.fullmatch(r"search your library for an? (land|creature) card, put it into your graveyard", s)
    if m: return [{"fa": "cerca", "tipo": [m.group(1).title()], "dove": "cimitero"}]                 # 701.23a
    m = re.fullmatch(r"(.+?) can't be blocked this turn", s)
    if m: return [{"fa": "non_bloccabile", "chi": chi_frase(m.group(1), ctx), "durata": "fine_turno"}]        # 509.1b, 611.2a
    m = re.fullmatch(r"(it|~|this creature) gains your choice of ([a-z]+(?:, [a-z]+)*,? or [a-z]+) until end of turn", s)
    if m:
        scelte = [x.strip() for x in re.split(r", or |, | or ", m.group(2)) if x.strip()]
        if not all(x in PAROLE_SEMPLICI or x == "hexproof" for x in scelte): raise Mancante(f"parole {scelte}")
        return [{"fa": "parola_scelta", "chi": chi_frase(m.group(1), ctx), "scelta": scelte, "durata": "fine_turno"}]
    m = re.fullmatch(r"target opponent sacrifices a creature or planeswalker with the greatest mana value among creatures and planeswalkers they control", s)
    if m: return [{"fa": "sacrifica", "tipi": ["creature", "planeswalker"], "massimo_mv": True, "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"})}]
    m = re.fullmatch(r"put a (\+1/\+1|loyalty) counter on it if it's a (creature|planeswalker)", s)
    if m:
        k = int(ctx.ultimo().split(":")[1])
        return [{"fa": "segnalini", "tipo": "+1/+1" if m.group(1) == "+1/+1" else "fedelta", "n": 1, "chi": ctx.ultimo(),
                 "se": {"bersaglio_era": [m.group(2)], "k": k}}]
    m = re.fullmatch(r"counter (target (?:\w+ )*spell)", s)
    if m:
        r = bersaglio(m.group(1)) or bersaglio_magia(m.group(1))
        if r is None: raise Mancante(f"contromagia {m.group(1)!r}")
        return [{"fa": "contrasta", "chi": ctx.nuovo(r)}]
    m = re.fullmatch(r"each opponent discards (a|one|two) cards?", s)
    if m: return [{"fa": "scarta", "n": numero(m.group(1)), "chi": "avversari"}]
    m = re.fullmatch(r"discard (a|one|two) cards?( at random)?", s)
    if m: return [dict({"fa": "scarta", "n": numero(m.group(1))}, **({"a_caso": True} if m.group(2) else {}))]   # 701.9b
    m = re.fullmatch(r"target player discards (a|one|two) cards?( at random)?", s)
    if m: return [{"fa": "scarta", "n": numero(m.group(1)), "a_caso": bool(m.group(2)), "chi": ctx.nuovo({"chi": ["player"]})}]
    m = re.fullmatch(r"(~|it|.+?) fights (.+)", s)
    if m:                                                                                        # 701.14a
        a = "fonte" if m.group(1) == "~" or (m.group(1) == "it" and not ctx.reqs) else chi_frase(m.group(1), ctx)
        b = chi_frase(m.group(2), ctx)
        return [{"fa": "lotta", "chi": [a, b]}]
    m = re.fullmatch(r"(.+?) deals damage equal to its power to (.+)", s)
    if m:                                                                                        # il riferimento all'indietro prima
        indietro = m.group(2) in ("it", "that creature", "that permanent", "them")
        b = chi_frase(m.group(2), ctx) if indietro else None
        a = chi_frase(m.group(1), ctx)
        if not indietro: b = chi_frase(m.group(2), ctx)
        return [{"fa": "danno_forza", "chi": [a, b]}]
    if s == "it becomes unprepared": return [{"fa": "sprepara", "chi": chi_frase("it", ctx)}]           # 723.3b
    if s == "play an additional land this turn": return [{"fa": "terra_in_piu"}]                       # 305.2
    m = re.fullmatch(r"that creature deals (\d+) damage to each opponent", s)
    if m: return [{"fa": "danno", "n": int(m.group(1)), "chi": "avversari", "da": "evento"}]
    if s == "create mowu, a legendary 3/3 green dog creature token":
        return [{"fa": "pedina", "quante": 1, "nome": "Mowu", "tipo": "Token Legendary Creature — Dog", "forza": 3, "costituzione": 3,
                 "colori": "G", "parole": []}]
    m = re.fullmatch(r"(target planeswalker you control) deals damage equal to its loyalty to (.+)", s)
    if m: return [{"fa": "danno_fedelta", "chi": [chi_frase(m.group(1), ctx), chi_frase(m.group(2), ctx)]}]
    m = re.fullmatch(r"add ((?:\{[wubrgc]\})+)", s)
    if m: return [{"fa": "aggiungi_mana", "mana": m.group(1).upper()}]
    m = re.fullmatch(r"add (\{[wubrgc]\})(?:, (\{[wubrgc]\}),)? or (\{[wubrgc]\})", s)          # 106.1a (14 nov 2026): uno a scelta
    if m: return [{"fa": "aggiungi_mana", "mana": "tra", "tra": [x.upper() for x in m.groups() if x]}]
    if s == "add one mana of any color": return [{"fa": "aggiungi_mana", "mana": "qualsiasi"}]           # 106.1a
    m = re.fullmatch(r"add (two|three|x) mana of any one color", s)                                      # 106.1a: un colore, N volte
    if m and (m.group(1) != "x" or x_ammessa): return [{"fa": "aggiungi_mana", "mana": "uno_colore", "n": "X" if m.group(1) == "x" else numero(m.group(1))}]
    m = re.fullmatch(r"add (two|three) mana in any combination of colors", s)                          # 106.1a: ognuno a scelta
    if m: return [{"fa": "aggiungi_mana", "mana": "combinazione", "n": numero(m.group(1))}]
    if s in ("sacrifice ~", "sacrifice this creature", "sacrifice this artifact", "sacrifice this enchantment"): return [{"fa": "sacrifica_questo", "chi": "fonte"}]
    m = re.fullmatch(r"pay (\{\d+\})", s)
    if m: return [{"fa": "paga", "costo": m.group(1).upper()}]
    m = re.fullmatch(r"sacrifice an? (creature|land|creature or planeswalker)", s)
    if m: return [{"fa": "sacrifica", "tipi": m.group(1).split(" or "), "chi": "tu"}]
    m = re.fullmatch(r"pay ((?:\{[0-9wubrgc]\})+)", s)
    if m: return [{"fa": "paga", "costo": m.group(1).upper()}]                                      # 608.2g (14 nov 2026)
    if s == "search your library for a basic land card, reveal it §cima": return [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "cima"}]
    if s == "search your library for a basic land card, reveal it, then shuffle and put that card on top":
        return [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "cima"}]                               # 701.23a, 701.24b
    m = re.fullmatch(r"its controller may search their library for a basic land card, (put it onto the battlefield( tapped)?|reveal it, put it into "
                     r"their hand)(?:, then shuffle)?", s)
    if m:                                                                                        # 701.23a: sceglie il controllore del bersaglio
        c_ = "controllore_" + ctx.ultimo()
        return [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "campo" if m.group(1).startswith("put") else "mano",
                 "tappata": bool(m.group(2)), "chi": c_, "puoi": True, "puoi_chi": c_}]
    m = re.fullmatch(r"search your library for an? (enchantment|basic land|planeswalker) card, reveal it, put it into your hand(?:, then shuffle)?", s)
    if m: return [{"fa": "cerca", "tipo": [w.title() for w in m.group(1).split()], "dove": "mano"}]           # 701.23a, 701.24b
    m = re.fullmatch(r"search your library for (a|up to two) basic land cards?, put (?:it|them) onto the battlefield tapped(?:, then shuffle)?", s)
    if m:                                                                                        # 701.23a, 701.24b (14 nov 2026)
        return [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "campo", "tappata": True, "quante": 1 if m.group(1) == "a" else 2}]
    m = re.fullmatch(r"create (a|an|one|two|three|x) (tapped )?(treasure|food|clue|lander|mutagen|shard|blood) tokens?", s)
    if m:                                                                                        # 111.10: le pedine predefinite
        return [pedina_predefinita(m.group(3), numero(m.group(1)), bool(m.group(2)))]
    m = re.fullmatch(r"search your library for a basic land card, put that card onto the battlefield tapped(?:, then shuffle)?", s)
    if m: return [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "campo", "tappata": True}]
    if s == "shuffle": return []                                                                 # la ricerca rimescola gia' (701.24b)
    m = re.fullmatch(r"each (opponent|player) sacrifices a (creature|creature of their choice)", s)
    if m: return [{"fa": "sacrifica", "tipi": ["creature"], "chi": "avversari" if m.group(1) == "opponent" else "giocatori"}]   # 701.21a, 101.4
    m = re.fullmatch(r"distribute (two|three|four) \+1/\+1 counters among (one, two, or three|one or two) target creatures( you control)?", s)
    if m:                                                                                        # 601.2d, 115.6 (14 nov 2026; giro 13: «one or two»)
        r_ = dict({"chi": ["creature"], "fino_a": True, "quanti": 3 if m.group(2).startswith("one, two") else 2, "minimo": 1},
                  **({"controllo": "tuo"} if m.group(3) else {}))
        return [{"fa": "distribuisci_segnalini", "tipo": "+1/+1", "n": numero(m.group(1)), "chi": ctx.nuovo(r_)}]
    if s == "double the number of +1/+1 counters on each of those creatures" and ctx.reqs:          # 701.10e
        return [{"fa": "raddoppia_segnalini", "tipo": "+1/+1", "chi": ctx.ultimo()}]
    m = re.fullmatch(r"(~|it|this creature) deals damage equal to (the number of [a-z ]+? you control) to (.+)", s)
    if m and (m.group(1) != "it" or (ctx.ultimo_chi in (None, "fonte") and not ctx.reqs)):        # 120.2b, 608.2h (14 nov 2026)
        spec_ = quantita(m.group(2), ctx)
        return [{"fa": "danno", "n": {"conta": spec_}, "chi": chi_frase(m.group(3), ctx)}]
    if s == "investigate twice": return [pedina_predefinita("clue"), pedina_predefinita("clue")]   # 701.16a (14 nov 2026)
    m = re.fullmatch(r"discover (\d+)", s)                                                        # 701.57a (14 nov 2026)
    if m: return [{"fa": "scopri", "n": int(m.group(1))}]
    m = re.fullmatch(r"each player loses (\d+) life", s)                                          # 119.3 (14 nov 2026)
    if m: return [{"fa": "perde", "chi": "giocatori", "n": int(m.group(1))}]
    m = re.fullmatch(r"(?:you )?draw (two|three) cards and (?:you )?lose (\d+) life", s)              # 121.1, 119.3 (14 nov 2026)
    if m: return [{"fa": "pesca", "n": numero(m.group(1))}, {"fa": "perde", "n": int(m.group(2))}]
    if s == "return all land cards from your graveyard to the battlefield tapped":                 # 400.7 (14 nov 2026)
        return [{"fa": "rianima_tutte", "tipi": ["land"], "tappata": True}]
    m = re.fullmatch(r"(?:then )?discard two cards unless you discard an? (creature|artifact|land|instant|sorcery|enchantment) card", s)
    if m: return [{"fa": "scarta_salvo", "tipo": m.group(1)}]                                      # 701.9a (14 nov 2026)
    if s == "discard up to two cards, then draw that many cards":                                  # 701.9a, 121.1 (14 nov 2026)
        return [{"fa": "scarta_poi_pesca", "n": 2}]
    m = re.fullmatch(r"each (opponent|player) sacrifices a nontoken creature(?: of their choice)?", s)   # 701.21a, 111.1 (14 nov 2026)
    if m: return [{"fa": "sacrifica", "tipi": ["creature"], "non_pedina": True, "chi": "avversari" if m.group(1) == "opponent" else "giocatori"}]
    if s == "put target card from a graveyard on the bottom of its owner's library":               # 401.4, 400.3 (14 nov 2026)
        return [{"fa": "in_fondo", "chi": ctx.nuovo({"chi": ["card"], "zona": "cimitero"})}]
    m = re.fullmatch(r"double the number of (\+1/\+1) counters on (.+)", s)                       # 701.10e (14 nov 2026)
    if m: return [{"fa": "raddoppia_segnalini", "tipo": "+1/+1", "chi": chi_frase(m.group(2), ctx)}]
    if s in ("draw a card for each card you've discarded this turn", "then draw a card for each card you've discarded this turn"):
        return [{"fa": "pesca", "n": {"conta": {"tipo": "scartate_turno"}}}]                        # 121.1, 701.9a (14 nov 2026)
    r_ = cerca_generica(s)
    if r_ is not None: return r_
    r_ = ritorno_generico(s, ctx)
    if r_ is not None: return r_
    m = re.fullmatch(r"create (a|an|one|two|three|x) (tapped )?(\d+)/(\d+) ((?:white|blue|black|red|green|colorless)(?: and (?:white|blue|black|red|green))?) "
                     r"((?:[a-z]+ )+?)(artifact )?creature tokens? with (?:([a-z ,]+?) and )?\"(.+?)\"", s)
    if m:                                                                                        # 111.4, 113.1a: l'abilita' tra virgolette
        d = pedina(m.group(1), m.group(3), m.group(4), m.group(5), m.group(6).strip(), bool(m.group(7)), m.group(8), None)
        d.update(abilita_pedina(m.group(9), d["tipo"]))
        if m.group(2): d["tappata"] = True
        return [d]
    raise Mancante(f"frase {s!r}")


_PAROLE_CERCA = {"basic", "legendary", "artifact", "creature", "enchantment", "land", "instant", "sorcery", "planeswalker", "equipment",
                 "vehicle", "mount", "aura", "plains", "island", "swamp", "mountain", "forest", "spacecraft", "planet", "town", "gate"}


_PERMANENTI = ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"]


def ritorno_generico(s, ctx):
    """400.7, 115.1 (14 nov 2026): «return target [nonlegendary] A[, B,] or C card [with mana value N or less] from your graveyard
    to your hand / the battlefield [tapped] [with two additional +1/+1 counters on it]»: l'ultima lettura dei ritorni."""
    m = re.fullmatch(r"return target (nonlegendary |legendary )?([a-z ,]+?) card(?: with mana value (\d+) or (less|greater))? from your graveyard "
                     r"to (your hand|the battlefield)( tapped)?(?: with (a|two|three) additional \+1/\+1 counters? on it)?", s)
    if not m: return None
    r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo"}
    tipi, sotto = [], None
    for w in [x for x in re.split(r",? or |, ", m.group(2)) if x]:
        w = w.strip()
        if w == "permanent": tipi += _PERMANENTI
        elif w == "nonland permanent": tipi += [x for x in _PERMANENTI if x != "land"]; r["non_tipi"] = ["land"]
        elif w in ("artifact", "creature", "enchantment", "instant", "sorcery", "land", "planeswalker", "battle"): tipi.append(w)
        elif w in ("vehicle", "spacecraft"): tipi.append("artifact"); sotto = w.title()
        elif w == "saga": tipi.append("enchantment"); r["sottotipo"] = "Saga"
        elif re.fullmatch(r"([a-z]+) creature", w) and w.split()[0] in TIPI_CREATURA: tipi.append("creature"); r["sottotipo"] = w.split()[0].title()
        else: return None
    if not tipi: return None
    if sotto: r["o_sottotipo" if "creature" in tipi else "sottotipo"] = sotto
    r["tipi"] = list(dict.fromkeys(tipi))
    if m.group(1) == "nonlegendary ": r["non_leggendario"] = True
    if m.group(1) == "legendary ": r["leggendario"] = True
    if m.group(3): r["mv_max" if m.group(4) == "less" else "mv_min"] = int(m.group(3))
    d = {"fa": "ritorna", "chi": ctx.nuovo(r)}
    if m.group(5) == "the battlefield":
        d["dove"] = "campo"
        if m.group(6): d["tappata"] = True
        if m.group(7): d["con_segnalini"] = {"+1/+1": numero(m.group(7))}
    elif m.group(6) or m.group(7): return None
    return [d]


def cerca_generica(s):
    """701.23a, 701.24b (14 nov 2026): «search your library for a [Mount or Vehicle] card [with mana value N or less], [reveal it,]
    put it into your hand / onto the battlefield [tapped]»: l'ultima lettura delle ricerche, dopo quelle scritte per carta."""
    m = re.fullmatch(r"search your library for (an?|up to two) ([a-z ]+?) cards?(?: with mana value (\d+)( or less| or greater)?)?"
                     r"(?:,? (?:and )?reveal (?:it|them))?,? (?:and )?put (?:it|them|that card) (into your hand|onto the battlefield( tapped)?)", s)
    if not m: return None
    alternative = [a.strip().split() for a in re.split(r" or |, or |, ", m.group(2)) if a.strip()]
    if not alternative or any(not a or not set(a) <= _PAROLE_CERCA for a in alternative): return None
    d = {"fa": "cerca", "dove": "mano" if m.group(5) == "into your hand" else "campo"}
    if len(alternative) == 1: d["tipo"] = [w.title() for w in alternative[0]]
    else: d["tipo"], d["tipo_o"] = [], [[w.title() for w in a] for a in alternative]
    if m.group(3):
        n = int(m.group(3))
        if m.group(4) == " or less": d["mv_max"] = n
        elif m.group(4) == " or greater": d["mv_min"] = n
        else: d["mv_max"] = d["mv_min"] = n
    if m.group(1) == "up to two": d["quante"] = 2
    if m.group(6): d["tappata"] = True
    return [d]


def quantita(testo, ctx=None):
    """«where X is ...» e «for each ...» -> la quantita' da contare alla risoluzione (608.2h)."""
    t = testo.strip().rstrip(".")
    if t == "the number of planeswalker types among planeswalkers you control": return {"tipo": "tipi_planeswalker"}
    if t == "the number of cards that were put into target player's graveyard from their library this turn" and ctx is not None:
        return {"tipo": "dal_grimorio_al_cimitero", "bersaglio": ctx.nuovo({"chi": ["player"]})}
    if t == "the number of cards in your graveyard": return {"tipo": "cimitero_tuo"}
    if t == "the number of differently named lands you control": return {"tipo": "terre_nomi_diversi"}    # 201.2 (14 nov 2026)
    if t == "the number of colors among permanents you control": return {"tipo": "colori_permanenti"}     # 105.2
    m = re.fullmatch(r"the number of (islands|mountains|plains|swamps|forests|artifacts|creatures|lands|planeswalkers) you control", t)
    if m:
        w = m.group(1)
        base_ = {"islands": "Island", "mountains": "Mountain", "plains": "Plains", "swamps": "Swamp", "forests": "Forest"}   # 205.3i
        sel = {"controllo": "tuo", "tipi": ["land"], "sottotipo": base_[w]} if w in base_ else {"controllo": "tuo", "tipi": [w[:-1]]}
        return {"tipo": "controlli", "sel": sel}
    if t == "that creature's power": return {"tipo": "forza_evento"}
    if t in ("this creature's power", "~'s power"): return {"tipo": "forza_fonte"}                  # 208.1, 608.2h (14 nov 2026)
    if t == "its power" and ctx is not None and not ctx.reqs and ctx.ultimo_chi in (None, "fonte"): return {"tipo": "forza_fonte"}
    if t == "the greatest power among creatures you control": return {"tipo": "forza_max_tue"}
    if t == "the greatest toughness among creatures you control": return {"tipo": "costituzione_max_tue"}   # 208.1 (15 nov 2026)
    if t == "the number of creatures that died this turn": return {"tipo": "morte_turno"}            # 700.4 (giro 7)
    if t in ("~'s toughness", "this creature's toughness"): return {"tipo": "costituzione_fonte"}  # 208.1, 608.2h
    if t == "the number of permanent cards in your graveyard":                                     # 110.4, 404.1
        return {"tipo": "cimitero_sel", "tipi": ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"]}
    if t in ("its toughness", "its power", "that creature's toughness") and ctx is not None and ctx.reqs and ctx.ultimo_chi is None:
        r_ = ctx.reqs[-1]                                                                          # 608.2h (15 nov 2026): il bersaglio,
        if "creature" in (r_.get("chi") or []) and not r_.get("zona") and not r_.get("fino_a"):     # com'era se non c'e' piu'
            return {"tipo": "fc_bersaglio", "k": len(ctx.reqs) - 1, "quale": "costituzione" if t.endswith("toughness") else "forza"}
    if t == "the amount of life you gained this turn": return {"tipo": "vita_guadagnata_turno"}
    if t == "your life total": return {"tipo": "vite_tue"}                                         # 119.1 (14 nov 2026)
    if t == "the number of creatures exiled this way": return {"tipo": "esiliate_qui"}
    m = re.fullmatch(r"the number of (creatures|permanents|artifacts|enchantments|lands) destroyed this way", t)   # 701.8a (giro 12)
    if m: return {"tipo": "distrutte_qui", **({} if m.group(1) == "permanents" else {"tipi": [m.group(1)[:-1]]})}
    if t == "the greatest mana value among cards in your graveyard": return {"tipo": "mv_max_cimitero"}
    if t == "the number of cards drawn this way": return {"tipo": "pescate_qui"}
    if t == "the number of cards in your hand": return {"tipo": "mano_tua"}
    if t == "each color among other artifacts you control": return {"tipo": "colori_altri_artefatti"}
    # 14 nov 2026: le quantita' generiche (608.2h: si contano alla risoluzione)
    m = re.fullmatch(r"the number of (\+1/\+1|charge) counters on (?:~|this creature|this artifact)", t)
    if m: return {"tipo": "segnalini_fonte", "segnalino": "+1/+1" if m.group(1) == "+1/+1" else "carica"}
    if t == "the number of cards you've drawn this turn": return {"tipo": "pescate_turno"}             # 121.1
    if t == "the amount of mana spent to cast that spell": return {"tipo": "mana_speso", "di": "evento"}   # 601.2h (14 nov 2026)
    if t in ("the amount of mana spent to cast this spell", "the amount of mana spent to cast this creature", "the amount of mana spent to cast it"):
        return {"tipo": "mana_speso", "di": "fonte"}
    m = re.fullmatch(r"the number of colors of mana spent to cast (that spell|this spell|this creature|it)", t)
    if m: return {"tipo": "colori_spesi", "di": "evento" if m.group(1) == "that spell" else "fonte"}   # 601.2h, 105.1
    if t == "the number of spells you've cast this turn": return {"tipo": "lanciate_turno"}            # 601.2i
    m = re.fullmatch(r"the number of attacking creatures( you control)?", t)
    if m: return {"tipo": "attaccanti", "tuoi": bool(m.group(1))}                                  # 506.4
    m = re.fullmatch(r"the number of ([a-z]+) cards in your graveyard", t)
    if m:
        w = m.group(1)
        if w in ("creature", "land", "artifact", "enchantment", "instant", "sorcery", "planeswalker"): return {"tipo": "cimitero_sel", "tipi": [w]}
        if w in TIPI_CREATURA or w in SOTTOTIPI: return {"tipo": "cimitero_sel", "sottotipo": w.title()}
        if w in SOTTOTIPI_205: return {"tipo": "cimitero_sel", "sottotipo": w.title()}             # 205.3k (15 nov 2026): «Lesson cards»
        raise Mancante(f"quantita' {t!r}")
    m = re.fullmatch(r"the number of (.+? (?:you|your opponents) control)", t)
    if m:
        sel = selettore(m.group(1))
        if sel is not None: return {"tipo": "campo_sel", "sel": sel}
    m = re.fullmatch(r"the number of ([a-z]+?)s you control", t)
    if m and m.group(1) in SOTTOTIPI_205:                                                        # 205.3g-i (14 nov 2026): «Shrines»
        return {"tipo": "campo_sel", "sel": {"controllo": "tuo", "tipi": ["permanent"], "sottotipo": m.group(1).title()}}
    # 15 nov 2026: le quantita' composte (608.2h)
    m = re.fullmatch(r"the number of (equipment|vehicles|auras|treasures|clues|foods) you control", t)
    if m:                                                                                        # 205.3g: «equipment» e' anche plurale
        st = {"equipment": "Equipment", "vehicles": "Vehicle", "auras": "Aura", "treasures": "Treasure", "clues": "Clue", "foods": "Food"}[m.group(1)]
        return {"tipo": "campo_sel", "sel": {"controllo": "tuo", "tipi": ["permanent"], "sottotipo": st}}
    m = re.fullmatch(r"the number of (.+? you control) with power (\d+) or greater", t)
    if m:
        sel = selettore(m.group(1))
        if sel is not None: return {"tipo": "campo_sel", "sel": dict(sel, forza_min=int(m.group(2)))}
    m = re.fullmatch(r"the number of (.+? you control) with \+1/\+1 counters on them", t)
    if m:
        sel = selettore(m.group(1))
        if sel is not None: return {"tipo": "campo_sel", "sel": dict(sel, con_segnalino="+1/+1")}
    if t in ("the number of counters on ~", "the number of counters on this creature"):          # 122.1: di ogni tipo
        return {"tipo": "segnalini_fonte_tutti"}
    m = re.fullmatch(r"the number of permanents you control that are (.+)", t)                    # giro 11: «that are creatures and/or
    if m:                                                                                        # Vehicles»
        sel = selettore_esteso(m.group(1) + " you control")
        if sel is not None: return {"tipo": "campo_sel", "sel": sel}
    m = re.fullmatch(r"(one|two|three|\d+) plus (.+)", t)
    if m: return {"tipo": "somma", "piu": int(m.group(1)) if m.group(1).isdigit() else numero(m.group(1)), "parti": [quantita(m.group(2), ctx)]}
    m = re.fullmatch(r"(the number of .+?) plus (the number of .+)", t)
    if m: return {"tipo": "somma", "piu": 0, "parti": [quantita(m.group(1), ctx), quantita(m.group(2), ctx)]}
    raise Mancante(f"quantita' {t!r}")


def _con_x(lista, spec):
    """Mette la quantita' al posto di X nelle istruzioni della frase."""
    out = []
    for d in lista:
        d = dict(d)
        for k in ("n", "quante"):
            if d.get(k) == "X": d[k] = {"conta": spec}
        for k in ("p", "t"):
            if d.get(k) in ("X", "+X", "-X"): d[k] = {"conta": spec, "segno": -1 if d[k] == "-X" else 1}
        out.append(d)
    return out


def _tipi_negati(voci):
    """«noncreature, nonland» (ogni voce un tipo negato: le carte che non hanno nessuno di quei tipi) o «nonland permanent» (una
    voce sola: un tipo, tolto un altro), come 205.4b legge «non» davanti a un tipo. None se non e' una di queste due forme."""
    if voci and all(re.fullmatch(r"non([a-z]+)", w) and w[3:] in TIPI_FILTRO for w in voci):
        return {"non_tipi": [w[3:] for w in voci]}
    m = re.fullmatch(r"non([a-z]+) ([a-z]+)", voci[-1]) if voci else None                          # «noncreature, nonland permanent»
    if m and m.group(1) in TIPI_FILTRO and m.group(2) in TIPI_FILTRO \
            and all(re.fullmatch(r"non([a-z]+)", w) and w[3:] in TIPI_FILTRO for w in voci[:-1]):
        return {"tipi": [m.group(2)], "non_tipi": [w[3:] for w in voci[:-1]] + [m.group(1)]}
    return None


_N_CIMA = {"nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20}


def guarda_cima(t, ctx):
    """701.20a, 401.4 (14 nov 2026): «look at / reveal the top N cards of your library[, where X is ...]. <una scelta> from among
    them <dove>. <il resto>», la famiglia intera: in mano (una, o «you may reveal a X card»), in campo («you may put a X card»,
    «put any number of X cards», anche «tapped»), col valore di mana massimo; il resto in fondo in ordine casuale, nel
    cimitero o «then shuffle» (701.24a). Una frase in piu' o diversa: None (resta agli altri modelli)."""
    m = re.fullmatch(r"(look at|reveal) the top (\w+) cards? of your library(?:, where x is ([^.]+?))?(?:\. |, )(.+)", t)
    if not m: return None
    if m.group(2) == "x":
        if not m.group(3): return None                                                           # la X della magia: non qui
        n = {"conta": quantita(m.group(3), ctx)}
    elif m.group(3): return None
    else:
        n = _N_CIMA.get(m.group(2)) or NUMERI.get(m.group(2))
        if not isinstance(n, int): return None
    F = r"((?:[a-z]+, )*(?:[a-z]+,? (?:and/)?or )?(?:non[a-z]+ )?[a-z]+)"                       # «nonland permanent» (15 nov 2026)
    MV = r"(?: with mana value (\d+) or less)?"
    scelte = [(r"put one of (?:them|those cards) into your hand", {"dove": "mano"}),
              (r"you may reveal an? " + F + " card" + MV + r" from among them and put it into your hand", {"dove": "mano", "puoi": True}),
              (r"you may put an? " + F + " card" + MV + r" from among them onto the battlefield( tapped)?", {"dove": "campo", "puoi": True}),
              (r"put an? " + F + " card" + MV + r" from among them onto the battlefield( tapped)?", {"dove": "campo"}),
              (r"(?:you may )?put any number of " + F + " cards" + MV + r" from among them onto the battlefield( tapped)?",
               {"dove": "campo", "puoi": True, "quanti": "tutte"}),
              (r"put up to two " + F + " cards" + MV + r" from among them onto the battlefield( tapped)?",   # 15 nov 2026
               {"dove": "campo", "puoi": True, "quanti": 2}),
              (r"you may reveal up to two " + F + " cards" + MV + r" from among them and put them into your hand",
               {"dove": "mano", "puoi": True, "quanti": 2})]
    resti = [(r"(?:\. put| and) the (?:rest|other) on the bottom(?: of your library)? in (?:a random|any) order\.", "fondo"),
             (r"(?:\. put| and) the (?:rest|other) into your graveyard\.", "cimitero"),
             (r"(?:, then|\.(?: then)?) shuffle\.", "mescola")]
    for sp, d0 in scelte:
        for rp, resto in resti:
            mm = re.match(sp + rp, m.group(4))
            if not mm: continue
            coda = m.group(4)[mm.end():].strip()                                                 # le frasi dopo: agli altri modelli
            d = dict({"fa": "guarda_cima_prendi", "n": n, "resto": resto}, **d0)
            g = mm.groups()
            if g:
                tipi = [w for w in re.split(r",? (?:and/)?or |, ", g[0]) if w]
                tn_ = _tipi_negati(tipi)                                                         # 205.4b, 15 nov 2026: «noncreature,
                if tn_ is not None: d.update(tn_)                                                # nonland», «nonland permanent»
                else:
                    if not all(w in TIPI_FILTRO or w in TIPI_CREATURA or w in SOTTOTIPI_205 for w in tipi): raise Mancante(f"tipi {tipi}")
                    d["tipi"] = tipi
                if g[1]: d["mv_max"] = int(g[1])                                                   # 202.3
                if len(g) > 2 and g[2]: d["tappata"] = True
            mn = re.fullmatch(r"if you didn't put a card into your hand this way, (.+)", coda)
            if mn and d["dove"] == "mano":                                                         # 608.2c: dipende da cosa e' successo
                return [dict(d, segna=True)] + [dict(x, se=dict(x.get("se") or {}, fatto=False)) for x in frasi(mn.group(1), ctx)]
            return [d] + (frasi(coda, ctx) if coda else [])
    return None


VERBI_IMP = ("gain", "lose", "draw", "create", "scry", "surveil", "investigate", "put", "mill", "discard", "return", "exile",
             "sacrifice", "tap", "untap", "destroy", "add")
VERBI_3P = ("gains", "loses", "draws", "discards", "mills", "sacrifices", "creates", "exiles", "returns")


def conta_per_ogni(x, ctx):
    """«for each X»: la quantita' «the number of X», anche col nome al plurale («gate you control» -> «gates you control»);
    «+1/+1 counter on it» sulla fonte. -> la quantita' o None (15 nov 2026)."""
    if x in ("+1/+1 counter on it", "+1/+1 counter on ~", "+1/+1 counter on this creature"):
        return {"tipo": "segnalini_fonte", "segnalino": "+1/+1"}
    prove_ = [x]
    w_ = x.split(" ")
    if w_[0] not in ("plains",): prove_.append(" ".join([w_[0] + "s"] + w_[1:]))
    if x.endswith(" with a +1/+1 counter on it"):                                                # giro 7: «each creature you control with a
        prove_.append(x[: -len(" with a +1/+1 counter on it")].replace("creature you control", "creatures you control") + " with +1/+1 counters on them")
    inv_ = {v: k for k, v in PLURALI.items()}                                                     # 15 nov 2026: il nome dopo un aggettivo
    for i_ in range(1, len(w_)):
        if w_[i_] in TIPI_CREATURA or w_[i_] in ("creature", "artifact", "land", "permanent", "enchantment"):
            prove_.append(" ".join(w_[:i_] + [inv_.get(w_[i_], w_[i_] + "s")] + w_[i_ + 1:]))
            break
    for y in prove_:
        try: return quantita("the number of " + y, ctx)
        except Mancante: pass
    return None


def vincolo_mana(s):
    """106.6 (15 nov 2026): «spend this mana only to <s>» -> il codice del vincolo (effetti._vincolo_ok) o None. Le magie di un
    tipo o di un sottotipo (205.3), le abilita' attivate (602) di ogni fonte o delle fonti di un tipo o sottotipo."""
    s = s.strip().rstrip(".")
    fissi = {"cast a noncreature spell": "solo_noncreatura", "cast a planeswalker spell": "solo_planeswalker",
             "cast an artifact spell": "artefatto", "cast an instant or sorcery spell": "istantaneo_stregoneria",
             "cast instant and sorcery spells": "istantaneo_stregoneria", "activate abilities": "solo_abilita",
             "activate abilities of artifact sources": "abilita_artefatto", "activate abilities of creature sources": "abilita_creatura"}
    if s in fissi: return fissi[s]
    def tipo_(w):                                                                                # «an Elf», «Elves», «creature»
        w = w.strip()
        if w in _TIPI_CARTA: return "tipo:" + w
        st = w if w in TIPI_CREATURA or w in SOTTOTIPI_205 else singolare(w)
        if st is None and w.endswith("s") and w[:-1] in SOTTOTIPI_205: st = w[:-1]
        return ("sottotipo:" + st.title()) if st else None
    m = re.fullmatch(r"cast (?:an? )?([a-z]+) spells?", s)
    if m: return tipo_(m.group(1))
    m = re.fullmatch(r"cast (?:an? )?([a-z]+) (?:spell )?or (?:an? )?([a-z]+) spells?", s)          # (giro 13) «a Dragon spell or an Omen
    if m and tipo_(m.group(1)) and tipo_(m.group(2)): return "o:" + tipo_(m.group(1)) + "§" + tipo_(m.group(2))   # spell», «a Lesson or Shrine spell»
    m = re.fullmatch(r"cast (?:an? )?([a-z]+) spells? (?:or|and) (?:to )?activate (?:an ability|abilities) of (?:an? )?([a-z]+) sources?", s)
    if m and tipo_(m.group(1)) and tipo_(m.group(1)) == tipo_(m.group(2)): return tipo_(m.group(1)) + "|abilita"
    return None


def bersaglio_magia(x):
    """115.2, 701.6a (15 nov 2026): «target [A or B / A, B, or C / nonA] spell [with mana value N [or less/greater]]» -> la
    richiesta o None: i tipi di carta (205.2a) in alternativa, «non...» come tipi esclusi, il valore di mana (202.3)."""
    mo_ = re.fullmatch(r"(target .+?spell with mana value (\d+)) or (less|greater)", x)              # giro 7
    if mo_:
        r_ = bersaglio_magia(mo_.group(1))
        if r_ is None: return None
        r_ = dict(r_); r_.pop("mv_min"); r_.pop("mv_max")
        r_["mv_max" if mo_.group(3) == "less" else "mv_min"] = int(mo_.group(2))
        return r_
    m = re.fullmatch(r"target (.+? )?spell(?: with mana value (\d+))?", x)
    if not m: return None
    r = {"chi": ["spell"]}
    if m.group(1):
        d_ = m.group(1).strip()
        mn = re.fullmatch(r"non([a-z]+)", d_)
        if mn:
            if mn.group(1) not in _TIPI_CARTA: return None
            r["non_tipi"] = [mn.group(1)]
        else:
            tipi_ = [w for w in re.split(r",? or |, ", d_) if w]
            if not tipi_ or not all(w in _TIPI_CARTA for w in tipi_): return None
            r["tipi_o"] = tipi_
    if m.group(2): r["mv_min"] = r["mv_max"] = int(m.group(2))
    return r


_SUPERTIPI = {"basic", "legendary", "snow"}
_TIPI_CARTA = {"artifact", "battle", "creature", "enchantment", "instant", "kindred", "land", "planeswalker", "sorcery"}


def cerca_estesa(s, ctx=None):
    """701.23a, 701.24b (15 nov 2026): l'ultimo tentativo dopo cerca_generica, per le forme che quella non legge: «search your library for <quante> <descrizione> card[s][ with mana value N or less]
    [, reveal it/them][,] put it/them into your hand / onto the battlefield [tapped] / into your graveyard[, then shuffle]».
    La descrizione: una o piu' alternative («an artifact card», «a basic Plains card or a creature card», «basic land cards
    and/or Gate cards»), ognuna di soli supertipi, tipi e sottotipi (205), confrontati per parola intera; «a card»: ogni carta.
    Il valore di mana massimo solo con un'alternativa (a quale si riferisce, se no, non e' detto). Altro: None."""
    m = re.fullmatch(r"search your library for (a|an|up to (?:one|two|three|four)|two|three|four) (.+?)( with mana value (\d+|x) or less)?"
                     r"(?:,| and) (?:reveal (?:it|them),? (?:and )?)?put (?:it|them|that card|those cards) (into your hand|"
                     r"onto the battlefield( tapped)?|into your graveyard)(?:, then shuffle)?", s)
    if not m: return None
    q = m.group(1)
    quante = 1 if q in ("a", "an") else numero(q.replace("up to ", ""))
    if not isinstance(quante, int): return None
    alts = [a for a in re.split(r",? (?:and/)?or (?:an? )?|, (?:an? )?", m.group(2)) if a]
    in_fila_ = len(alts) > 1 and not any(re.search(r"\bcards?$", a) for a in alts[:-1])         # giro 10: «A, B, and/or C cards»
    if len(alts) > 1 and re.search(r"\bcards?$", alts[-1]) and not any(re.search(r"\bcards?$", a) for a in alts[:-1]):
        suff_ = re.search(r"\bcards?$", alts[-1]).group(0)                                          # 15 nov 2026: «card» una volta
        pre_ = ""                                                                                  # sola, in fondo; «basic» davanti a
        mb_ = re.match(r"(basic) ", alts[0])                                                       # tipi di terra base (205.3i, 305.6)
        if mb_ and all(re.fullmatch(r"(?:basic )?(plains|island|swamp|mountain|forest)( cards?)?", a) for a in alts): pre_ = "basic "
        alts = [(pre_ if pre_ and not a.startswith("basic ") else "") + re.sub(r" cards?$", "", a) + " " + suff_ for a in alts]
    tipi_o = []
    for a in alts:
        mw = re.fullmatch(r"(?:([a-z ]+) )?cards?", a)
        if not mw: return None
        parole_ = (mw.group(1) or "").split()
        if not all(w in _SUPERTIPI or w in _TIPI_CARTA or w in TIPI_CREATURA or w in SOTTOTIPI_205 for w in parole_): return None
        tipi_o.append([w.title() for w in parole_])
    if m.group(3) and len(tipi_o) > 1 and not in_fila_: return None                              # (il valore di mana vale per tutte)
    if m.group(4) == "x" and not (ctx is not None and getattr(ctx, "x_magia", False)): return None
    d = {"fa": "cerca", "tipo": tipi_o[0] if len(tipi_o) == 1 else [], "parole_intere": True,
         "dove": {"into your hand": "mano", "into your graveyard": "cimitero"}.get(m.group(5), "campo")}
    if len(tipi_o) > 1: d["tipo_o"] = tipi_o
    if quante != 1: d["quante"] = quante
    if m.group(4): d["mv_max"] = "X" if m.group(4) == "x" else int(m.group(4))                    # 202.3, 107.3a
    if m.group(6): d["tappata"] = True
    return [d]


def _alt_cerca(a, ctx):
    """205, 202.3, 702.8a (giro 13): una alternativa di «search your library for ...»: «nonland permanent card with mana value 3 or
    less», «artifact card with mana value 4 or 5», «card with flash», «basic Plains card». None se non si legge."""
    m = re.fullmatch(r"(?:an? )?(.*?)\bcards?(?: with (flash)| with mana value (\d+|x) or less| with mana value (\d+) or greater"
                     r"| with mana value (\d+) or (\d+))?", a.strip())
    if not m: return None
    d = {}
    for w in m.group(1).split():
        if w == "permanent": d["perm"] = True
        elif w.startswith("non") and w[3:] in _TIPI_CARTA: d.setdefault("non", []).append(w[3:])
        elif w in _SUPERTIPI or w in _TIPI_CARTA or w in TIPI_CREATURA or w in SOTTOTIPI_205: d.setdefault("tipi", []).append(w)
        else: return None
    if m.group(2): d["flash"] = True
    if m.group(3):
        if m.group(3) == "x" and not (ctx is not None and getattr(ctx, "x_magia", False)): return None
        d["mv_max"] = "X" if m.group(3) == "x" else int(m.group(3))
    if m.group(4): d["mv_min"] = int(m.group(4))
    if m.group(5): d["mv_in"] = [int(m.group(5)), int(m.group(6))]
    return d


def cerca_piu(s, ctx=None):
    """701.23a-b, 701.24b (giro 13): «search your library [and/or graveyard] for <una o piu' alternative> [, reveal it,] [and] put
    it into your hand / onto the battlefield [tapped] / into your graveyard [, then shuffle]». Le alternative le legge _alt_cerca
    (ognuna col suo valore di mana); «a card named A or B» per nome (201.2). «and/or graveyard»: chi cerca sceglie dove; chi
    non sceglie cerca prima nel grimorio, poi nel cimitero (401.2, 404.2: il cimitero e' pubblico). Dopo cerca_estesa."""
    m = re.fullmatch(r"search your library( and/or graveyard)? for (a|an|up to (?:one|two|three)|two|three) (.+?)"
                     r"(?:,? (?:and )?reveal (?:it|them))?,? (?:and )?put (?:it|them|that card) (into your hand|onto the battlefield( tapped)?|"
                     r"into your graveyard)(?:, then shuffle)?", s)
    if not m: return None
    q = m.group(2)
    quante = 1 if q in ("a", "an") else numero(q.replace("up to ", ""))
    if not isinstance(quante, int): return None
    desc = m.group(3)
    mn = re.fullmatch(r"(?:a )?card named (.+?) or (.+)", desc)
    if mn:
        alts = [{"nome": x.strip()} for x in (mn.group(1), mn.group(2))]
        if any(re.search(r"[,]|\bcard\b", a["nome"]) for a in alts): return None
    else:
        alts = [_alt_cerca(a, ctx) for a in re.split(r",? or (?=an? )", desc)]
        if any(a is None for a in alts): return None
    d = {"fa": "cerca", "tipo": [], "alt": alts, "dove": {"into your hand": "mano", "into your graveyard": "cimitero"}.get(m.group(4), "campo")}
    if quante != 1: d["quante"] = quante
    if m.group(5): d["tappata"] = True
    if m.group(1): d["anche_cimitero"] = True
    return [d]


_CONTROLLORE_FA = {"creates": "create", "draws": "draw", "loses": "lose", "gains": "gain", "discards": "discard", "mills": "mill"}


def _cambia_e_dai(s, ctx):
    """611.2a, 613.1d, 613.1f, 613.4b-c, 205.1b (15 nov 2026): «X <pezzo> and <pezzo> ... until end of turn», un soggetto e i suoi
    pezzi in qualunque ordine: «gets +P/+T», «gains <parole chiave>», «gains "<abilita'>"» (l'abilita' data, letta come le
    innescate), «becomes an artifact creature [with base power and toughness P/T]» e «becomes a P/T artifact creature» (205.1b:
    restano i tipi di prima), «becomes a/an <tipo o sottotipo> in addition to its other types», «has base power and toughness
    P/T». Solo con «until end of turn» (la durata letta, 611.2a). Un pezzo che non si legge: None, e il contesto torna com'era."""
    m = re.fullmatch(r"(.+?) ((?:gets?|gains?|becomes|has) .+) until end of turn", s)
    if not m: return None
    citate = re.findall(r'"([^"]+)"', m.group(2))
    resto = re.sub(r'"[^"]+"', "§Q", m.group(2))
    if resto.count("§Q") != len(citate) or '"' in resto: return None
    pezzi = re.split(r",? and (?=(?:gets?|gains?|becomes|has) )", resto)
    n0_, ul_ = len(ctx.reqs), ctx.ultimo_chi
    try:
        c = chi_frase(m.group(1), ctx)
        out, q = [], iter(citate)
        for x in pezzi:
            mp = re.fullmatch(r"gets? ([+-]\d+)/([+-]\d+)", x)
            if mp: out.append({"fa": "pompa", "chi": c, "p": int(mp.group(1)), "t": int(mp.group(2)), "durata": "fine_turno"}); continue
            mq = re.fullmatch(r"gains? (?:([a-z ,]+?),? and )?§Q", x)
            if mq:
                if mq.group(1): out.append({"fa": "dai_parole", "chi": c, "parole": parole_lista(mq.group(1)), "durata": "fine_turno"})
                testo_ = next(q).strip()
                testo_ = re.sub(r"\bthis creature\b", "~", testo_)
                ab_ = innesco(testo_ if testo_.endswith(".") else testo_ + ".", Contesto(ctx.nome))
                if not ab_: raise Mancante("abilita' data non letta")
                out.append({"fa": "dai_abilita_fino", "chi": c, "abilita": ab_, "durata": "fine_turno"}); continue
            mk = re.fullmatch(r"gains? ([a-z ,]+)", x)
            if mk: out.append({"fa": "dai_parole", "chi": c, "parole": parole_lista(mk.group(1)), "durata": "fine_turno"}); continue
            mb = re.fullmatch(r"(?:becomes an artifact creature with base power and toughness|becomes an?|has base power and toughness) (\d+)/(\d+)"
                              r"( artifact creature)?", x)
            if mb and (mb.group(3) or not x.startswith("becomes a")):
                if x.startswith("becomes"): out.append({"fa": "diventa_tipo", "chi": c, "tipi": ["artifact", "creature"], "durata": "fine_turno"})
                out.append({"fa": "base", "chi": c, "p": int(mb.group(1)), "t": int(mb.group(2)), "durata": "fine_turno"}); continue
            if x == "becomes an artifact creature":
                out.append({"fa": "diventa_tipo", "chi": c, "tipi": ["artifact", "creature"], "durata": "fine_turno"}); continue
            mt = re.fullmatch(r"becomes an? ([a-z]+) in addition to (?:its|his|her|their) other types", x)
            if mt and mt.group(1) in TIPI_FILTRO - {"permanent"} - {"instant", "sorcery"}:
                out.append({"fa": "diventa_tipo", "chi": c, "tipi": [mt.group(1)], "durata": "fine_turno"}); continue
            if mt and (mt.group(1) in TIPI_CREATURA or mt.group(1) in SOTTOTIPI_205):
                out.append({"fa": "diventa_tipo", "chi": c, "sottotipi": [mt.group(1).title()], "durata": "fine_turno"}); continue
            raise Mancante(f"pezzo {x!r}")
        if next(q, None) is not None or not out: raise Mancante("")
        return out
    except Mancante:
        del ctx.reqs[n0_:]; ctx.ultimo_chi = ul_
        return None


def pedina_generica(s, ctx, x_ammessa=False):
    """111.2-111.4, 111.10, 508.4, 205.4a (15 nov 2026): l'ultimo tentativo per «create ... token», a pezzi: il nome davanti
    («redwing, a legendary 1/1 ...»), quante («a/two/.../x», «a number of ... equal to Q»), «tapped», forza e costituzione,
    i colori, i sottotipi, «artifact», poi in coda «with <parole> [and "<abilita'>"]», «named <nome>», «that's/that are tapped
    and attacking»; e la pedina artefatto non creatura col nome e l'abilita' tra virgolette («... named axe with "equipped
    creature gets +1/+0" and equip {2}»). Un pezzo che non si legge: None."""
    import string as _s
    m = re.fullmatch(r"create (?:([a-z' ]+?), a (legendary)|(a|an|one|two|three|four|five|six|seven|eight|x|a number of))( tapped)? (\d+)/(\d+) "
                     r"((?:white|blue|black|red|green|colorless)(?:,? (?:and )?(?:white|blue|black|red|green))*) ((?:[a-z]+ )+?)(artifact )?"
                     r"creature tokens?(.*)", s)
    if m:
        nome0, leg, q, tap, pp, tt, col, sub, art, coda = m.groups()
        q = q or "a"                                                                             # «Galactus, a legendary ...»: una
        if q == "x" and not x_ammessa: return None
        d = pedina("a" if q == "a number of" else q, pp, tt, col, sub.strip(), bool(art), None, None)
        if leg: d["tipo"] = d["tipo"].replace("Token ", "Token Legendary ", 1)
        if nome0: d["nome"] = _s.capwords(nome0)
        if tap: d["tappata"] = True
        coda = coda.strip()
        mq = re.match(r"equal to (.+)$", coda) if q == "a number of" else None
        if q == "a number of":
            if not mq: return None
            spec_ = quantita(mq.group(1), ctx)
            d["quante"] = {"conta": spec_}
            coda = ""
        ma = re.search(r"(?:^|,? )that(?:'s| are) tapped and attacking$", coda)
        if ma: coda = coda[:ma.start()]; d["tappata"] = True; d["attaccando"] = True
        mn = re.search(r" ?named (.+)$", coda)
        if mn:
            nm_ = mn.group(1).replace("~", ctx.nome.split(",")[0].lower() if ctx.nome else "~")   # 201.5: il nome corto
            coda = coda[:mn.start()]; d["nome"] = _s.capwords(nm_)
        coda = coda.strip()
        if coda in ("with changeling",):                                                            # 702.73a (giro 9): «with changeling»
            d["car_extra"] = dict(d.get("car_extra") or {}, tutti_i_tipi_creatura=True); coda = ""
        if coda:
            mw = re.fullmatch(r'with (?:([a-z ,]+?),? and )?"(.+)"', coda)
            if mw:
                if mw.group(1): d["parole"] = parole_lista(mw.group(1))
                q_ = re.sub(r"\b" + re.escape(nome0) + r"\b", "this token", mw.group(2)) if nome0 else mw.group(2)   # 201.5
                d.update(abilita_pedina(q_, d["tipo"]))
            else:
                mk = re.fullmatch(r"with ([a-z ,]+)", coda)
                if not mk: return None
                d["parole"] = parole_lista(mk.group(1))
        return [d]
    m = re.fullmatch(r'create a colorless (equipment )?artifact token named ([a-z\' ]+) with "(.+?)"(?: and equip (\{\d+\}))?', s)
    if m:
        testo_ = m.group(3) if m.group(3).endswith(".") else m.group(3) + "."
        if m.group(4):
            if not m.group(1): return None
            testo_ += "\nEquip " + m.group(4)
        tipo_ = "Token Artifact — Equipment" if m.group(1) else "Token Artifact"
        d = {"fa": "pedina", "quante": 1, "nome": _s.capwords(m.group(2)), "tipo": tipo_, "colori": "", "parole": []}
        d.update(abilita_pedina(testo_, tipo_))
        return [d]
    return None


def _ultimi_g7(s, ctx):
    """Gli ultimi tentativi del giro 7 (15 nov 2026), ognuno una forma generale con la sua regola; None se nessuno legge."""
    n0_, ul_ = len(ctx.reqs), ctx.ultimo_chi
    def via():
        del ctx.reqs[n0_:]; ctx.ultimo_chi = ul_
    try:
        m = re.fullmatch(r"(.+?) loses all abilities", s)                                          # 613.1f, 611.2c: senza durata, per sempre
        if m: return [{"fa": "togli_abilita", "chi": chi_frase(m.group(1), ctx)}]
        m = re.fullmatch(r"return all (.+?) to (?:their|its) owners?'?s? hands?", s)               # 400.3, 608.2c
        if m:
            sel_ = selettore(m.group(1))
            if sel_ is not None: return [{"fa": "rimbalza", "chi": sel_}]
        m = re.fullmatch(r"put (a|an|one|two|three|four|five|six|seven|eight) -1/-1 counters? on (.+)", s)   # 122.1, 122.6
        if m: return [{"fa": "segnalini", "tipo": "-1/-1", "n": numero(m.group(1)), "chi": chi_frase(m.group(2), ctx)}]
        m = re.fullmatch(r"double (.+?)'s power until end of turn", s)                              # 701.10b-c: +X/+0, X la forza adesso
        if m:
            if m.group(1) in ("~", "this creature"): spec_ = {"tipo": "forza_fonte"}; c_ = "fonte"
            else:
                c_ = chi_frase(m.group(1), ctx)
                if not (isinstance(c_, str) and c_.startswith("bersaglio")): raise Mancante("double")
                spec_ = {"tipo": "fc_bersaglio", "k": int(c_.split(":")[1]), "quale": "forza"}
            return [{"fa": "pompa", "chi": c_, "p": {"conta": spec_}, "t": 0, "durata": "fine_turno"}]
        m = re.fullmatch(r"add (four|five|six|seven|eight) mana (of any one color|in any combination of colors)", s)   # 106.1a
        if m:
            n_ = numero(m.group(1))
            return [{"fa": "aggiungi_mana", "mana": "uno_colore" if "one color" in m.group(2) else "combinazione", "n": n_}]
        m = re.fullmatch(r"(it|~|this creature|this enchantment|this artifact|this land|target creature you control|target creature) becomes an? "
                         r"(?:(\d+)/(\d+) )?([a-z ]+?) in addition to (?:its|his|her|their) other types( until end of turn)?", s)
        if m:                                                                                      # 205.1b, 613.1d, 613.4b: con o senza durata
            ws_ = m.group(4).split()
            tipi_ = [w for w in ws_ if w in ("legendary", "artifact", "enchantment", "creature", "land")]
            sotto_ = [w for w in ws_ if w not in tipi_]
            if all(w in TIPI_CREATURA or w in SOTTOTIPI_205 for w in sotto_) and (tipi_ or sotto_) \
                    and (m.group(2) is None or "creature" in tipi_):
                c_ = chi_frase(m.group(1), ctx)
                d_ = {"fa": "diventa_tipo", "chi": c_, "tipi": tipi_, "sottotipi": [w.title() for w in sotto_]}
                out_ = [d_]
                if m.group(2): out_.append({"fa": "base", "chi": c_, "p": int(m.group(2)), "t": int(m.group(3))})
                if m.group(5): out_ = [dict(x, durata="fine_turno") for x in out_]
                return out_
        m = re.fullmatch(r"counter (target .+?spell with mana value \d+)", s)                         # 701.6a, 115.2 (giro 7)
        if m and bersaglio_magia(m.group(1)) is not None: return [{"fa": "contrasta", "chi": ctx.nuovo(bersaglio_magia(m.group(1)))}]
        m = re.fullmatch(r"return all (nonland permanents|creatures|permanents) target player controls to (?:their|its) owners?'?s? hands?", s)
        if m:                                                                                      # 400.3, 608.2c (giro 7)
            sel_ = {"tipi": ["permanent"] if "permanents" in m.group(1) else ["creature"], "di_bersaglio": ctx.nuovo({"chi": ["player"]})}
            if m.group(1).startswith("nonland"): sel_["non_tipi"] = ["land"]
            return [{"fa": "rimbalza", "chi": sel_}]
        m = re.fullmatch(r"(?:you )?draw x cards and (?:you )?lose x life", s)                      # 107.3a, 121.1, 119.3
        if m and getattr(ctx, "x_magia", False): return [{"fa": "pesca", "n": "X"}, {"fa": "perde", "n": "X"}]
        m = re.fullmatch(r"this spell (deals .+)", s)                                              # 201.5: «~»
        if m:
            try: return frase("~ " + m.group(1), ctx)
            except Mancante: pass
        m = re.fullmatch(r"(target player|target opponent) mills cards equal to (.+)", s)           # 701.17a, 608.2h
        if m:
            b_ = ctx.nuovo({"chi": ["player"], **({"controllo": "avversario"} if "opponent" in m.group(1) else {})})
            return [{"fa": "macina", "n": {"conta": quantita(m.group(2), ctx)}, "chi": b_}]
        m = re.fullmatch(r"counter (target .+?spell with mana value \d+ or (?:less|greater))", s)       # 701.6a, 115.2
        if m and bersaglio_magia(m.group(1)) is not None: return [{"fa": "contrasta", "chi": ctx.nuovo(bersaglio_magia(m.group(1)))}]
        m = re.fullmatch(r"(each opponent|each player|you) sacrifices? (an?|one|two|three) (nontoken )?((?:artifact|creature|enchantment|land|planeswalker|permanent)s?"
                         r"(?: or (?:artifact|creature|enchantment|land|planeswalker)s?)*)(?: of their choice)?", s)
        if m and (m.group(2) in ("a", "an", "one") or m.group(4).endswith("s")):                  # 701.21a, 101.4 (giri 7 e 9)
            tipi_ = [w.rstrip("s") for w in m.group(4).split(" or ")]
            d_ = {"fa": "sacrifica", "tipi": tipi_, "chi": {"each opponent": "avversari", "each player": "giocatori"}.get(m.group(1), "tu")}
            if m.group(3): d_["non_pedina"] = True
            if numero(m.group(2)) > 1: d_["quante"] = numero(m.group(2))
            return [d_]
        m = re.fullmatch(r"(target player|target opponent|each opponent|each player) (gains?|loses?|discards?|mills?|draws?) x (life|cards)", s)
        if m and getattr(ctx, "x_magia", False):                                                   # 107.3a (giro 9): la X della magia
            v_ = m.group(2).rstrip("s"); fa_ = {"gain": "guadagna", "lose": "perde", "discard": "scarta", "mill": "macina", "draw": "pesca"}[v_]
            if (fa_ in ("guadagna", "perde")) != (m.group(3) == "life"): raise Mancante("x")
            chi_ = {"each opponent": "avversari", "each player": "giocatori"}.get(m.group(1))
            if chi_ is None: chi_ = ctx.nuovo({"chi": ["player"], **({"controllo": "avversario"} if "opponent" in m.group(1) else {})})
            return [{"fa": fa_, "n": "X", "chi": chi_}]
        m = re.fullmatch(r"(each opponent|target opponent|target player) (loses life|mills cards) equal to (.+)", s)
        if m and "they" not in m.group(3) and "that player" not in m.group(3):                      # 119.3, 701.17a, 608.2h (giro 9)
            sp_ = quantita(m.group(3), ctx)
            chi_ = "avversari" if m.group(1) == "each opponent" else ctx.nuovo({"chi": ["player"], **({"controllo": "avversario"} if "opponent" in m.group(1) else {})})
            return [{"fa": "perde" if "life" in m.group(2) else "macina", "n": {"conta": sp_}, "chi": chi_}]
        m = re.fullmatch(r"its controller (creates .+ tokens?(?: with .+)?)", s)
        if m and ctx.reqs:                                                                         # 608.2h (giro 9): la pedina sotto chi
            pg_ = pedina_generica("create " + m.group(1)[len("creates "):], ctx)                   # controllava il bersaglio
            if pg_: return [dict(d, chi="controllore_" + ctx.ultimo()) for d in pg_]
        if s in ("each player discards their hand", "each opponent discards their hand"):              # 701.9a
            return [{"fa": "scarta", "tutta": True, "chi": "giocatori" if "player" in s else "avversari"}]
        m = re.fullmatch(r"(surveil|scry) x", s)
        if m and getattr(ctx, "x_magia", False): return [{"fa": "surveil" if m.group(1) == "surveil" else "scry", "n": "X"}]   # 107.3a
        m = re.fullmatch(r"(.+?) gets? \+(\d+)/\+(\d+) until end of turn for each (.+)", s)              # 611.2a, 608.2h: contata adesso
        if m:
            sp_ = conta_per_ogni(m.group(4), ctx)
            if sp_ is not None:
                c_ = chi_frase(m.group(1), ctx)
                return [{"fa": "pompa", "chi": c_, "p": {"conta": sp_, "molt": int(m.group(2))} if int(m.group(2)) else 0,
                         "t": {"conta": sp_, "molt": int(m.group(3))} if int(m.group(3)) else 0, "durata": "fine_turno"}]
        m = re.fullmatch(r"until end of turn, (.+?) (gets?) (\+\d+/\+\d+) for each (.+)", s) or \
            re.fullmatch(r"(.+?) (gets?) (\+\d+/\+\d+) for each (.+?) until end of turn", s)
        if m and "until end of turn for each" not in s:                                           # 611.2a (giro 12): l'altro ordine
            n1_ = len(ctx.reqs)
            try: return frase_o_azioni(f"{m.group(1)} {m.group(2)} {m.group(3)} until end of turn for each {m.group(4)}", ctx)
            except Mancante: del ctx.reqs[n1_:]
        m = re.fullmatch(r"(~|this creature|target creature|it) can attack this turn as though it didn't have defender", s)
        if m: return [{"fa": "attacca_con_difensore", "chi": chi_frase(m.group(1), ctx), "durata": "fine_turno"}]   # 702.3b, 611.2a
        m = re.fullmatch(r"double the power and toughness of (.+?) until end of turn", s)           # 701.10b
        if m: return [{"fa": "moltiplica_fc", "chi": chi_frase(m.group(1), ctx), "volte": 2, "durata": "fine_turno"}]
        m = re.fullmatch(r"(target creature) deals damage to itself equal to its power", s)          # 120.2b, 608.2h
        if m:
            c_ = chi_frase(m.group(1), ctx)
            return [{"fa": "danno_forza", "chi": [c_, c_]}]
        m = re.fullmatch(r"(?:~|this creature|it) deals damage equal to (.+?) to (any target|target .+|each opponent|each creature .+)", s)
        if m and not m.group(1).startswith(("the number of", "its power")):                       # 120.2b, 608.2h (giro 7)
            sp_ = quantita(m.group(1), ctx)
            return [{"fa": "danno", "n": {"conta": sp_}, "chi": chi_frase(m.group(2), ctx) if m.group(2) != "each opponent" else "avversari"}]
        r_ = ritorno_esteso(s, ctx)
        if r_ is not None: return r_
        m = re.fullmatch(r"(?:~|this creature|it|he|she) deals damage to (any target|target .+?) equal to (.+)", s)   # 120.2b, 608.2h
        if m and (not s.startswith("it ") or ctx.ultimo_chi in (None, "fonte") and not ctx.reqs):
            sp_ = quantita(m.group(2), ctx)
            return [{"fa": "danno", "n": {"conta": sp_}, "chi": chi_frase(m.group(1), ctx)}]
        if s.endswith(" until end of turn") and " and " in s:                                       # 611.2a (giro 7): due soggetti, ognuno
            corpo_ = s[: -len(" until end of turn")]                                               # col suo verbo («this creature gets +1/+0
            for mm_ in re.finditer(r" and ", corpo_):                                              # and creatures you control gain trample»)
                a_, b_ = corpo_[: mm_.start()], corpo_[mm_.end():]
                if not (re.search(r" (?:gets?|gains?) ", a_) and re.match(r"(?:[a-z~]+ )+?(?:gets?|gains?) ", b_)) or re.match(r"(?:gets?|gains?) ", b_): continue
                n1_ = len(ctx.reqs)
                try: return frase_o_azioni(a_ + " until end of turn", ctx) + frase_o_azioni(b_ + " until end of turn", ctx)
                except Mancante: del ctx.reqs[n1_:]
        m = re.fullmatch(r"sacrifice an? (permanent|token or a land|token)", s)                     # 701.21a (giro 7)
        if m:
            if m.group(1) == "permanent": return [{"fa": "sacrifica", "tipi": ["permanent"], "chi": "tu"}]
        SEGNI_ = ("page", "promotion", "growth", "fire", "hone", "conqueror", "blight", "bait", "oil", "wish", "film", "incubation",
                  "soul", "invasion", "fellowship", "revival", "peace", "plan", "quest")
        m = re.fullmatch(r"put (.+?) counters? on (.+)", s)                                        # 122.1, 122.1b (giro 10): uno o piu' tipi di
        if m and not m.group(1).startswith(("a number", "any number")):                            # segnalini insieme, i segni e le parole chiave
            pezzi_ = [x for x in re.split(r",? and |, ", m.group(1)) if x]
            lista_ = []
            for x_ in pezzi_:
                mx_ = re.fullmatch(r"(a|an|one|two|three|four|five|x) (\+1/\+1|-1/-1|[a-z ]+?)(?: counters?)?", x_)
                if not mx_: lista_ = None; break
                tipo_ = mx_.group(2)
                if not (tipo_ in ("+1/+1", "-1/-1") or tipo_ in PAROLE_SEMPLICI or tipo_ in SEGNI_): lista_ = None; break
                if mx_.group(1) == "x" and not (getattr(ctx, "x_magia", False)): lista_ = None; break
                lista_.append((tipo_, "X" if mx_.group(1) == "x" else numero(mx_.group(1))))
            if lista_:
                c_ = "fonte" if m.group(2) in ("~", "this creature", "this artifact", "this enchantment", "this vehicle", "her", "him") else chi_frase(m.group(2), ctx)
                return [{"fa": "segnalini", "tipo": tp_, "n": n_, "chi": c_} for tp_, n_ in lista_]
        m = re.fullmatch(r"(~|this creature|it|target creature) (gets [+-]\d+/[+-]\d+ until end of turn) and (deals .+)", s)
        if m:                                                                                      # 608.2c (giro 10): due azioni, lo stesso
            n1_ = len(ctx.reqs)                                                                    # soggetto
            try:
                a_ = frase_o_azioni(m.group(1) + " " + m.group(2), ctx)
                return a_ + frase_o_azioni(("it" if m.group(1) == "target creature" else m.group(1)) + " " + m.group(3), ctx)
            except Mancante: del ctx.reqs[n1_:]
        m = re.fullmatch(r"(.+?) become artifact creatures until end of turn", s)                    # 205.1b, 613.1d (giro 10)
        if m:
            so_ = _soggetto_statica(m.group(1))
            if so_ is not None and so_[1]: return [{"fa": "diventa_tipo", "chi": so_[0], "tipi": ["artifact", "creature"], "durata": "fine_turno"}]
        m = re.fullmatch(r"(?:until your next turn, )?(.+?) gains? ([a-z ,]+?)(?: until your next turn)?", s)
        if m and ("until your next turn" in s) and m.group(1) not in ("you",):                       # 611.2a (giro 10): fino al tuo prossimo turno
            return [{"fa": "dai_parole", "chi": chi_frase(m.group(1), ctx), "parole": parole_lista(m.group(2)), "durata": "prossimo_turno"}]
        m = re.fullmatch(r"add an amount of (\{[wubrgc]\}) equal to (.+)", s)                    # 106.1, 605.1a (giro 13): «Add an amount of
        if m:                                                                                      # {G} equal to this creature's power»
            try: q_ = quantita(m.group(2), ctx)
            except Mancante: q_ = None
            if q_ is not None: return [{"fa": "aggiungi_mana", "mana": m.group(1).upper(), "volte": {"conta": q_}}]
        m = re.fullmatch(r"when that creature dies this turn, (.+)", s)                            # 603.7, 603.6c, 700.4 (giro 13): l'innesco
        if m and ctx.reqs and ctx.ultimo_chi is None and "creature" in (ctx.reqs[-1].get("chi") or []):   # ritardato sul bersaglio
            c_ = Contesto(ctx.nome)
            try: fa_ = frasi(m.group(1).rstrip(".") + ".", c_)
            except Mancante: fa_ = None
            if fa_ is not None and not c_.reqs and not re.search(r"\b(its|it|that creature)\b", m.group(1)):
                return [{"fa": "ritardata_muore", "chi": ctx.ultimo(), "ab": {"tipo": "innescata", "fa": fa_}}]
        m = re.fullmatch(r"add (\{[wubrgc]\}) for each (.+)", s)                                 # 106.1, 605.1a (giro 12): «Add {G} for
        if m:                                                                                      # each Elf you control»
            sp_ = conta_per_ogni(m.group(2), ctx)
            if sp_ is not None: return [{"fa": "aggiungi_mana", "mana": m.group(1).upper(), "volte": {"conta": sp_}}]
        if s.startswith("each of your opponents "):                                                 # 102.2: «each opponent»
            return frase_o_azioni("each opponent " + s[len("each of your opponents "):], ctx)
        m = re.fullmatch(r"sacrifice (an?|another) (nonland permanent|artifact|creature|enchantment|land|artifact or creature)", s)
        if m:                                                                                      # 701.21a (giro 7)
            tipi_ = [w for w in _PERMANENTI if w != "land"] if m.group(2) == "nonland permanent" else m.group(2).split(" or ")
            d_ = {"fa": "sacrifica", "tipi": tipi_, "chi": "tu"}
            if m.group(1) == "another": d_["altra"] = True
            return [d_]
        m = re.fullmatch(r"(each opponent loses|you lose|you gain|target player loses|target opponent loses) x life", s)
        if m and getattr(ctx, "x_magia", False):                                                   # 107.3a, 119.3: la X della magia
            if m.group(1) == "you gain": return [{"fa": "guadagna", "n": "X"}]
            if m.group(1) == "you lose": return [{"fa": "perde", "n": "X"}]
            if m.group(1) == "each opponent loses": return [{"fa": "perde", "chi": "avversari", "n": "X"}]
            b_ = ctx.nuovo({"chi": ["player"], **({"controllo": "avversario"} if "opponent" in m.group(1) else {})})
            return [{"fa": "perde", "chi": b_, "n": "X"}]
        m = re.fullmatch(r"return an? ((?:artifact|creature|enchantment|land|instant|sorcery|planeswalker)(?: or (?:artifact|creature|enchantment|land|instant|sorcery|planeswalker))*) card from your graveyard to your hand", s)
        if m: return [{"fa": "dal_cimitero_in_mano", "tipi": m.group(1).split(" or ")}]          # 400.7: si sceglie (115.10)
        m = re.fullmatch(r"(each opponent mills|target player mills|target opponent mills|you mill|mill) x cards", s)
        if m and getattr(ctx, "x_magia", False):                                                   # 701.17a, 107.3a
            if m.group(1) in ("you mill", "mill"): return [{"fa": "macina", "n": "X"}]
            if m.group(1) == "each opponent mills": return [{"fa": "macina", "n": "X", "chi": "avversari"}]
            return [{"fa": "macina", "n": "X", "chi": ctx.nuovo({"chi": ["player"], **({"controllo": "avversario"} if "opponent" in m.group(1) else {})})}]
        m = re.fullmatch(r"(?:you )?mill cards equal to (.+)", s)                                   # 701.17a, 608.2h
        if m: return [{"fa": "macina", "n": {"conta": quantita(m.group(1), ctx)}}]
        m = re.fullmatch(r"double the power of (.+?) until end of turn", s)                          # 701.10b
        if m: return _ultimi_g7("double " + m.group(1) + "'s power until end of turn", ctx)
        if s == "double your life total": return [{"fa": "guadagna", "n": {"conta": {"tipo": "vite_tue"}}}]   # 119.5, 701.10d
        m = re.fullmatch(r"attach (?:this equipment|~) to (target creature you control|target creature)", s)   # 701.3a, 301.5
        if m: return [{"fa": "attacca", "chi": ctx.nuovo(bersaglio(m.group(1)))}]
        m = re.fullmatch(r"return ((?:up to (?:one|two|three) )?(?:other |another )?target .+?) to (?:its owner's hand|their owners' hands)", s)
        if m:                                                                                      # 400.3 (giro 7)
            b_ = bersaglio(m.group(1))
            if b_ is not None and not b_.get("zona"): return [{"fa": "rimbalza", "chi": ctx.nuovo(b_)}]
        m = re.fullmatch(r"remove (a|one|two|three) (-1/-1|\+1/\+1) counters? from (this creature|~)", s)   # 122.1 (giro 7)
        if m: return [{"fa": "togli_segnalini", "tipo": m.group(2), "n": numero(m.group(1)), "chi": "fonte"}]
    except Mancante:
        via(); return None
    via()
    return None


def ritorno_esteso(s, ctx):
    """400.7, 115.1, 601.2c (giro 7, 15 nov 2026): l'ultimo tentativo dopo ritorno_generico: «return [up to N|one or two] target
    <descrizione> card[s] [with mana value N or less/greater] from your graveyard to your hand / the battlefield [tapped]», con la
    descrizione di sole parole note: «card» (ogni carta), un sottotipo da solo («Villain card»), «non-Doctor permanent», piu' tipi
    con «and/or». Altro: None."""
    altra_ = s.startswith("return another target ")
    if altra_: s = "return target " + s[len("return another target "):]                          # «another target»: non questa carta
    m = re.fullmatch(r"return (up to (?:one|two|three) |one or two )?target ([a-z ,/-]+?) cards?(?: with mana value (\d+) or (less|greater))? "
                     r"from your graveyard to (your hand|the battlefield)( tapped)?", s)
    if not m: return None
    r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo"}
    if altra_: r["altra"] = True
    desc = m.group(2).strip()
    mn = re.match(r"non-([a-z]+) ", desc)
    if mn:
        if mn.group(1) not in TIPI_CREATURA and mn.group(1) not in SOTTOTIPI_205: return None
        r["non_sottotipi"] = [mn.group(1).title()]; desc = desc[mn.end():]
    if desc in ("", "card"): tipi = list(TIPI_CARTA_TUTTI)
    elif desc == "permanent": tipi = list(_PERMANENTI)
    elif desc in TIPI_CREATURA or desc in SOTTOTIPI_205: tipi, r["sottotipo"] = list(TIPI_CARTA_TUTTI), desc.title()
    else:
        tipi = [w for w in re.split(r",? and/or |,? or |, ", desc) if w]
        if not all(w in TIPI_CARTA_TUTTI for w in tipi): return None
    r["tipi"] = tipi
    if m.group(3): r["mv_max" if m.group(4) == "less" else "mv_min"] = int(m.group(3))
    q = m.group(1)
    if q == "one or two ": r.update(fino_a=True, quanti=2, minimo=1)
    elif q: r.update(fino_a=True, quanti=numero(q.split()[2]))
    d = {"fa": "ritorna", "chi": ctx.nuovo(r)}
    if m.group(5) == "the battlefield":
        if "instant" in tipi or "sorcery" in tipi: return None                                      # 400.4a
        d["dove"] = "campo"
        if m.group(6): d["tappata"] = True
    elif m.group(6): return None
    return [d]


def frase_o_azioni(f, ctx):
    """608.2c (14 nov 2026): una frase; se nessun modello la legge intera, «A and B» / «A, B, and C» fatta di azioni che si
    leggono da sole, nell'ordine scritto («gain 2 life and draw two cards»; col soggetto ripetuto: «each opponent discards a card
    and loses 2 life»). Solo come ultimo tentativo: una frase gia' letta non cambia."""
    try: return frase(f, ctx)
    except Mancante as e_:
        s = f.strip().rstrip(".")
        cg_ = cerca_estesa(s, ctx)                                                                # 701.23a (15 nov 2026)
        if cg_ is not None: return cg_
        cg_ = cerca_piu(s, ctx)                                                                   # 701.23a (giro 13)
        if cg_ is not None: return cg_
        if s == "if you search your library this way, shuffle": return []                         # 701.24b: la ricerca nel grimorio rimescola gia'
        mt_ = re.fullmatch(r"target (player|opponent) ((?:" + "|".join(_CONTROLLORE_FA) + r"|investigates)\b.*)", s)
        if mt_:                                                                                   # 115.1, 608.2c (15 nov 2026): «target player
            parti_ = re.split(r",? and (?=(?:" + "|".join(_CONTROLLORE_FA) + r"|investigates)\b)", mt_.group(2))   # draws three cards
            n0_ = len(ctx.reqs)                                                                    # and gains 3 life»: un bersaglio solo
            b_ = ctx.nuovo({"chi": ["player"], **({"controllo": "avversario"} if mt_.group(1) == "opponent" else {})})
            out_ = []
            try:
                for x_ in parti_:
                    v_, _, r_ = x_.partition(" ")
                    imp_ = "investigate" if v_ == "investigates" else (_CONTROLLORE_FA[v_] + " " + r_)
                    if v_ == "investigates" and r_: raise Mancante("investigates ...")
                    out_ += frase(imp_, ctx)
                if len(ctx.reqs) != n0_ + 1 or not out_ or not all(d.get("fa") in ("pedina", "pesca", "perde", "guadagna", "scarta", "macina")
                                                                   and d.get("chi", "tu") == "tu" for d in out_): raise Mancante("")
            except Mancante:
                del ctx.reqs[n0_:]; out_ = None                                                     # gli altri tentativi provano ancora
            if out_: return [dict(d, chi=b_) for d in out_]
        mu_ = re.fullmatch(r"counter (target .+? spell(?: with mana value \d+)?) unless its controller pays (\{\d\})", s)
        if mu_ and bersaglio_magia(mu_.group(1)) is not None:                                    # 701.6a, 118.12 (15 nov 2026)
            return [{"fa": "contrasta_salvo", "chi": ctx.nuovo(bersaglio_magia(mu_.group(1))), "costo": mu_.group(2).upper()}]
        mo_ = re.fullmatch(r"(each opponent|each player|that player) ((?:" + "|".join(_CONTROLLORE_FA) + r")\b.*)", s)
        if mo_ and (mo_.group(1) != "that player" or getattr(ctx, "giocatore", None)):          # 608.2c (15 nov 2026): «each opponent mills
            chi_ = {"each opponent": "avversari", "each player": "giocatori"}.get(mo_.group(1)) or ctx.giocatore   # two cards», «that player ...»
            n0_ = len(ctx.reqs); out_ = []
            try:
                for x_ in re.split(r",? and (?=(?:" + "|".join(_CONTROLLORE_FA) + r")\b)", mo_.group(2)):
                    v_, _, r_ = x_.partition(" ")
                    out_ += frase(_CONTROLLORE_FA[v_] + " " + r_, ctx)
                if len(ctx.reqs) != n0_ or not out_ or not all(d.get("fa") in ("pedina", "pesca", "perde", "guadagna", "scarta", "macina")
                                                               and d.get("chi", "tu") == "tu" for d in out_): raise Mancante("")
            except Mancante:
                del ctx.reqs[n0_:]; out_ = None
            if out_: return [dict(d, chi=chi_) for d in out_]
        mi_ = re.fullmatch(r"if it's an? ([a-z]+)(?: card)?, (.+)", s) or \
            re.fullmatch(r"if that creature is (?:an? )?([a-z]+), (?:it also (?=gets|gains)|(?=it ))?(.+)", s)   # (giro 13)
        if mi_ and ctx.reqs and ctx.ultimo_chi is None:                                           # 608.2h (15 nov 2026): il bersaglio com'era
            w_ = mi_.group(1); k_ = int(ctx.ultimo().split(":")[1])
            if w_ in _TIPI_CARTA or (w_ == "legendary" and s.startswith("if that creature is legendary")): c_ = {"bersaglio_era": [w_], "k": k_}
            elif w_ in TIPI_CREATURA or w_ in SOTTOTIPI_205: c_ = {"bersaglio_sottotipo": w_.title(), "k": k_}
            else: raise e_
            corpo_s_ = mi_.group(2)
            if s.startswith("if that creature is") and not corpo_s_.startswith("it ") and re.match(r"(gets|gains) ", corpo_s_): corpo_s_ = "it " + corpo_s_
            try: corpo_ = frase_o_azioni(corpo_s_, ctx)
            except Mancante: raise e_
            return [dict(d, se=dict(d.get("se") or {}, **c_)) for d in corpo_]
        mk_ = re.fullmatch(r"its controller (" + "|".join(_CONTROLLORE_FA) + r") (.+)", s)
        if mk_ and ctx.reqs:                                                                       # 608.2h (15 nov 2026): «its controller
            try: base_ = frase(_CONTROLLORE_FA[mk_.group(1)] + " " + mk_.group(2), ctx)            # creates/draws/loses ...»: chi
            except Mancante: base_ = None                                                          # controllava il bersaglio (giro 9: se no,
            if base_ is None:                                                                      # gli altri tentativi)
                r9_ = _ultimi_g7(s, ctx)
                if r9_ is not None: return r9_
                raise e_
            if base_ and all(d.get("fa") in ("pedina", "pesca", "perde", "guadagna", "scarta", "macina") and d.get("chi", "tu") == "tu"
                             for d in base_):
                c_ = "controllore_" + ctx.ultimo()
                return [dict(d, chi=c_) for d in base_]
            raise e_
        mf_ = re.fullmatch(r"(?:you )?(draw a card|gain (\d+) life|create (?:a|an) .+? token|put a \+1/\+1 counter on .+?) for each (.+)", s)
        if mf_:                                                                                   # 608.2h (15 nov 2026): «for each X»
            spec_ = conta_per_ogni(mf_.group(3), ctx)
            if spec_ is not None:
                try: base_ = frase(mf_.group(1), ctx)
                except Mancante: raise e_
                if len(base_) == 1:
                    d_ = dict(base_[0])
                    k_ = {"pesca": "n", "guadagna": "n", "segnalini": "n", "pedina": "quante"}.get(d_["fa"])
                    if k_ and d_.get(k_, 1) in (1, int(mf_.group(2) or 1)):
                        d_[k_] = {"conta": spec_, "molt": int(mf_.group(2) or 1)}
                        return [d_]
            raise e_
        if s.startswith("until end of turn, ") and not s.endswith("until end of turn"):        # 611.2a (15 nov 2026): la durata in testa
            try: return frase_o_azioni(s[len("until end of turn, "):] + " until end of turn", ctx)
            except Mancante: raise e_
        mq_ = re.fullmatch(r"(.+?) if (?!able)([^,]+)", s)
        if mq_ and " instead" not in mq_.group(1):                                               # 608.2c (15 nov 2026): la condizione in coda
            cq_ = cond_statica(mq_.group(2))
            if cq_ is not None:
                try: return [dict(d, se=dict(d.get("se") or {}, statica=cq_)) for d in frase_o_azioni(mq_.group(1), ctx)]
                except Mancante: raise e_
        mc_ = re.fullmatch(r"(?:then )?if ([^,]+), (.+)", s)
        if mc_ and " instead" not in mc_.group(2) and not mc_.group(2).startswith("instead"):
            cs_ = cond_statica(mc_.group(1))                                                      # 608.2c (15 nov 2026): la condizione
            if cs_ is not None:                                                                   # si guarda alla risoluzione
                try: return [dict(d, se=dict(d.get("se") or {}, statica=cs_)) for d in frase_o_azioni(mc_.group(2), ctx)]
                except Mancante: raise e_
        mr_ = re.fullmatch(r"return it to the battlefield( tapped)? under its owner's control( with a \+1/\+1 counter on it)?", s)
        if mr_ and getattr(ctx, "evento", None) == "muore":                                       # 603.10a, 400.7 (15 nov 2026): «when this
            d_ = {"fa": "ritorna", "chi": "carta_evento", "dove": "campo", "sotto_proprietario": True}   # creature dies, return it»: la
            if mr_.group(1): d_["tappata"] = True                                                 # carta arrivata nel cimitero
            if mr_.group(2): d_["con_segnalini"] = {"+1/+1": 1}
            return [d_]
        mn_ = re.fullmatch(r"search your library for a card named ~(?:, reveal it,|,) put it (into your hand|onto the battlefield( tapped)?)(?:, then shuffle)?", s)
        if mn_ and ctx.nome:                                                                       # 701.23a, 201.2 (15 nov 2026)
            d_ = {"fa": "cerca", "tipo": [], "nome": ctx.nome, "dove": "mano" if "hand" in mn_.group(1) else "campo"}
            if mn_.group(2): d_["tappata"] = True
            return [d_]
        mo2_ = re.fullmatch(r"put an? ((?:artifact|creature|enchantment|land|planeswalker)(?: or (?:artifact|creature|enchantment|land|planeswalker))+) card "
                            r"from your hand onto the battlefield( tapped)?", s)
        if mo2_:                                                                                   # 110.2 (giro 7): piu' tipi
            d_ = {"fa": "dalla_mano_in_campo", "tipi": mo2_.group(1).split(" or ")}
            if mo2_.group(2): d_["tappata"] = True
            return [d_]
        mh_ = re.fullmatch(r"put an? ([a-z]+(?: [a-z]+)?) card(?: with mana value (\d+|x) or less)? from your hand onto the battlefield( tapped)?", s)
        if mh_:                                                                                    # 110.2, 305.4 (15 nov 2026): una scelta,
            w_ = mh_.group(1).split()                                                              # non un bersaglio
            tipo_ = w_[-1]; sotto_ = w_[0] if len(w_) == 2 else None
            ok_ = tipo_ in ("land", "creature", "permanent", "artifact", "enchantment") and (sotto_ is None or sotto_ in TIPI_CREATURA or sotto_ in SOTTOTIPI_205)
            if ok_ and not (mh_.group(2) == "x" and not getattr(ctx, "x_magia", False)):
                d_ = {"fa": "dalla_mano_in_campo", "tipi": [tipo_]}
                if sotto_: d_["sottotipo"] = sotto_.title()
                if mh_.group(2): d_["mv_max"] = "X" if mh_.group(2) == "x" else int(mh_.group(2))
                if mh_.group(3): d_["tappata"] = True
                return [d_]
        mv_ = re.fullmatch(r"(?:then )?if this is the (second|third|fourth) time this ability has resolved this turn, (.+)", s)
        if mv_:                                                                                    # 608.2c, 113.6 (15 nov 2026): le volte che
            k_ = {"second": 2, "third": 3, "fourth": 4}[mv_.group(1)]                              # questa abilita' si e' risolta nel turno
            try: corpo_ = frase_o_azioni(mv_.group(2), ctx)
            except Mancante: raise e_
            return [dict(d, se=dict(d.get("se") or {}, risolta_volte=k_)) for d in corpo_]
        if s in ("create a token that's a copy of this equipment", "create a token that's a copy of this artifact",
                 "create a token that's a copy of this creature", "create a token that's a copy of this enchantment",
                 "create a token that's a copy of ~"):                                             # 707.2, 111.1 (15 nov 2026): la fonte
            return [{"fa": "copia_pedina", "chi": "fonte"}]
        mc_ = re.fullmatch(r"create a token that's a copy of ((?:another )?target [a-z ,]+)", s)
        if mc_ and bersaglio(mc_.group(1)) is not None:                                          # 707.2, 111.1 (15 nov 2026)
            return [{"fa": "copia_pedina", "chi": ctx.nuovo(bersaglio(mc_.group(1)))}]
        mo_ = re.fullmatch(r"return one or two (target .+?) (to (?:their owners'|your) hands?|from your graveyard to your hand)", s)
        if mo_:                                                                                  # 115.1, 601.2c (15 nov 2026): uno o due
            b_ = bersaglio(re.sub(r"\bcards\b", "card", re.sub(r"\bpermanents\b", "permanent", mo_.group(1))) + (" from a graveyard" if "graveyard" in mo_.group(2) else ""))
            if b_ is not None and "graveyard" in mo_.group(2): b_ = None                              # (le carte nel cimitero: ritorno_generico)
            if b_ is not None:
                b_ = dict(b_, fino_a=True, quanti=2, minimo=1)
                return [{"fa": "rimbalza", "chi": ctx.nuovo(b_)}]
        ms_ = re.fullmatch(r"(?:he|she|this saga|this creature|this vehicle|this enchantment|this artifact|this spacecraft|this land) (deals .+)", s)
        if ms_:                                                                                    # 201.5 (15 nov 2026): «he deals», «this
            try: return frase("~ " + ms_.group(1), ctx)                                           # saga deals»: la fonte, come «~»
            except Mancante: pass
        mg_ = re.fullmatch(r"(?:you )?gain life equal to (.+)", s)
        if mg_:                                                                                    # 119.3, 608.2h (15 nov 2026)
            n0_ = len(ctx.reqs)
            try: return [{"fa": "guadagna", "n": {"conta": quantita(mg_.group(1), ctx)}}]
            except Mancante: del ctx.reqs[n0_:]
        mk_ = re.fullmatch(r"gain control of ((?:up to one )?target .+?)( until end of turn)?", s)
        if mk_ and bersaglio(mk_.group(1)) is not None:                                          # 613.1b, 611.2a (15 nov 2026)
            d_ = {"fa": "prendi_controllo", "chi": ctx.nuovo(bersaglio(mk_.group(1)))}
            if mk_.group(2): d_["durata"] = "fine_turno"
            return [d_]
        r_ = _ultimi_g7(s, ctx)
        if r_ is not None: return r_
        cd_ = _cambia_e_dai(s, ctx)
        if cd_ is not None: return cd_
        n0_, ul_ = len(ctx.reqs), ctx.ultimo_chi
        try: pg_ = pedina_generica(s, ctx)
        except Mancante: pg_ = None
        if pg_ is not None: return pg_
        del ctx.reqs[n0_:]; ctx.ultimo_chi = ul_
        try: return _spezza_azioni(s, ctx, r", and |, | and ")
        except Mancante: pass
        V_ = "|".join(VERBI_3P + VERBI_IMP + ("you",))                                             # 15 nov 2026: solo davanti a un verbo
        try: return _spezza_azioni(s, ctx, r"(?:, and |, | and )(?=(?:" + V_ + r")\b)")           # («a 1/1 blue and black Faerie»)
        except Mancante: pass
        if s.startswith("you ") and s[4:].split(" ")[0] in VERBI_IMP:                             # giro 7: «you gain 1 life and scry 1»
            try: return _spezza_azioni(s[4:], ctx, r"(?:, and |, | and )(?=(?:" + V_ + r")\b)")   # (il soggetto «you» non si ripete)
            except Mancante: pass
        raise e_


def _spezza_azioni(s, ctx, sep):
    """608.2c: «A and B», ogni parte un'azione letta da sola (col soggetto ripetuto se c'e')."""
    if True:
        n0_, ul_ = len(ctx.reqs), ctx.ultimo_chi
        parti = [x.strip() for x in re.split(sep, s)]
        if len(parti) < 2: raise Mancante("una parte sola")
        sogg = None
        m0 = re.match(r"(each opponent|each player|you) (" + "|".join(VERBI_3P + VERBI_IMP) + r") ", parti[0])
        if m0: sogg = m0.group(1)
        out = []
        for k, x in enumerate(parti):
            w = x.split(" ")[0]
            if k > 0 and w in VERBI_3P + VERBI_IMP and sogg is not None and w not in ("put",): x = f"{sogg} {x}"
            elif k > 0 and w not in VERBI_IMP and not (w == "you" and len(x.split(" ")) > 1 and x.split(" ")[1] in VERBI_IMP):
                del ctx.reqs[n0_:]; ctx.ultimo_chi = ul_; raise Mancante("parte senza verbo")
            try: out += frase_o_azioni(x, ctx)                                                       # (giro 10: frase_o_azioni prova
            except Mancante:                                                                       # prima frase, poi gli ultimi tentativi)
                del ctx.reqs[n0_:]; ctx.ultimo_chi = ul_; raise
        return out


def cima_fissa(t, ctx):
    """701.20a, 401.4: le letture di «look at the top N cards of your library ...» (le forme fisse, poi guarda_cima). None se
    nessuna legge il testo intero. Usata da frasi sul testo intero e, dal 15 nov 2026, anche sulle frasi che restano quando
    lo sguardo viene dopo un'altra frase («~ deals 2 damage ... . look at the top two cards ...»)."""
    m = re.fullmatch(r"look at the top (two|three|four|five|six|seven) cards of your library\. you may reveal an? ((?:[a-z]+, )*(?:[a-z]+,? or )?[a-z]+) "
                     r"card from among them and put it into your hand\. put the rest on the bottom of your library in (a random|any) order\.", t)
    if m:                                                                                        # 14 nov 2026: 701.20a, 401.4
        tipi = [w for w in re.split(r",? or |, ", m.group(2)) if w]
        if all(w in TIPI_FILTRO or w in TIPI_CREATURA or w in SOTTOTIPI_205 or w in ("plains", "island", "swamp", "mountain", "forest") for w in tipi):
            return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "tipi": tipi, "puoi": True, "resto": "fondo"}]   # (15 nov 2026: se no
                                                                                                                       # provano gli altri)
    N_ = r"(two|three|four|five|six|seven|eight)"
    m = re.fullmatch(r"look at the top " + N_ + r" cards of your library\. you may reveal an? ((?:[a-z]+, )*(?:[a-z]+,? or )?[a-z]+) card with power (\d+) or less "
                     r"from among them and put it into your hand\. put the rest on the bottom of your library in (a random|any) order\.", t)
    if m:                                                                                        # 14 nov 2026: 701.20a, 208.1
        tipi = [w for w in re.split(r",? or |, ", m.group(2)) if w]
        if all(w in TIPI_FILTRO or w in TIPI_CREATURA for w in tipi):
            return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "tipi": tipi, "forza_max": int(m.group(3)), "puoi": True, "resto": "fondo"}]
    m = re.fullmatch(r"look at the top " + N_ + r" cards of your library\. you may reveal up to two ([a-z]+) cards from among them and put them into your hand\. "
                     r"put the rest on the bottom of your library in (a random|any) order\.", t)
    if m and (m.group(2) in TIPI_FILTRO or m.group(2) in TIPI_CREATURA):
        return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "tipi": [m.group(2)], "quanti": 2, "puoi": True, "resto": "fondo"}]
    m = re.fullmatch(r"look at the top " + N_ + r" cards of your library\. put two of them into your hand and the rest (on the bottom of your library in any order|into your graveyard)\.", t)
    if m: return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "quanti": 2, "resto": "fondo" if "bottom" in m.group(2) else "cimitero"}]
    m = re.fullmatch(r"look at the top " + N_ + r" cards of your library\. you may put one of those cards back on top of your library\. put the rest into your graveyard\.", t)
    if m: return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "dove": "cima", "puoi": True, "resto": "cimitero"}]   # 401.4
    m = re.fullmatch(r"look at the top two cards of your library\. put one of those cards into your hand and the other on the bottom of your library\.", t)
    if m: return [{"fa": "guarda_cima_prendi", "n": 2, "resto": "fondo"}]
    m = re.fullmatch(r"look at the top (two|three) cards of your library\. put one (?:of them )?into your hand and the (?:other|rest) into your graveyard\.", t)
    if m: return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "resto": "cimitero"}]                    # 401.4
    m = re.fullmatch(r"look at the top (two|three|four|five) cards of your library\. put one of them into your hand and the rest on the bottom of "
                     r"your library in any order\.", t)
    if m: return [{"fa": "guarda_cima_prendi", "n": numero(m.group(1)), "resto": "fondo"}]
    return guarda_cima(t, ctx)


def frasi(testo, ctx):
    """Un testo d'effetto, frase per frase (608.2c: nell'ordine scritto); «X, then Y» e «X and you gain N» sono due."""
    out = []
    t = testo.strip()
    m = re.fullmatch(r"draw two cards\. then you may exile this spell and four cards named ~ from your graveyard\. if you do, "
                     r"search your library for a (\w+) creature card, put it onto the battlefield, then shuffle\.", t)
    if m:                                                                                        # Sphinx's Approach
        return [{"fa": "pesca", "n": 2}, {"fa": "esilia_e_cerca", "n": 4, "tipo": [m.group(1).title(), "Creature"], "puoi": True}]
    m = re.fullmatch(r"(.+?\.) then if there are (seven|four|five|six|three) or more cards in your graveyard, (.+)", t)
    if m:                                                                                        # «Then if ...»: 608.2c, una volta
        n = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}[m.group(2)]
        prima = frasi(m.group(1), ctx)
        parti = [x for x in re.split(r", and |, ", m.group(3).strip().rstrip(".")) if x.strip()]
        dopo = [dict(d, se=dict(d.get("se") or {}, cimitero_almeno=n, gruppo=1)) for x in parti for d in frase(x, ctx)]
        return prima + dopo
    if t == "choose a creature type. destroy all creatures that aren't of the chosen type.": return [{"fa": "distruggi_tranne_tipo"}]   # 205.3m
    g_ = cima_fissa(t, ctx)
    if g_ is not None: return g_
    m = re.fullmatch(r"target opponent reveals their hand\. you choose an? (nonland|noncreature, nonland|instant or sorcery|creature|artifact or creature) "
                     r"card from it\. that player discards that card\.", t)
    if m:                                                                                        # 701.9b, 701.20a (14 nov 2026)
        d = {"fa": "scarta_scelta_da_te", "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"}), "ogni_tipo": True}
        k = m.group(1)
        if k.startswith("non"): d["non_tipi"] = [w.strip()[3:] for w in k.split(",")]
        else: d["tipi"] = [w for w in k.split(" or ")]
        return [d]
    if t == "target opponent reveals their hand. you choose a nonland permanent card from it. that player discards that card.":
        return [{"fa": "scarta_scelta_da_te", "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"}), "non_tipi": ["land"]}]
    m = re.fullmatch(r"~ deals (\d+) damage to target opponent\. that player reveals their hand\. you choose a nonland card from it\. they discard that card\.", t)
    if m:                                                                                        # Stinging Vitriol, 701.9b
        b = ctx.nuovo({"chi": ["player"], "controllo": "avversario"})
        return [{"fa": "danno", "n": int(m.group(1)), "chi": b}, {"fa": "scarta_scelta_da_te", "chi": b, "non_tipi": ["land"], "ogni_tipo": True}]
    m = re.fullmatch(r"exile up to one target nonland card of each card type from your graveyard\. copy those cards\. you may cast any number "
                     r"of spells with total mana value (\d+) or less from among the copies without paying their mana costs\.", t)
    if m:                                                                                        # Uldaros Theorix: 115.3, 707.12, 707.12a,
        r = {"chi": ["card"], "zona": "cimitero", "controllo": "tuo", "non_tipi": ["land"], "fino_a": True,   # 118.9, 107.3b, 608.3f
             "quanti": len(TIPI_NON_TERRA), "uno_per_tipo": True}
        return [{"fa": "esilia_e_lancia_copie", "chi": ctx.nuovo(r), "mv_totale": int(m.group(1))}]
    if t == ("you may reveal exactly two cards you own with different names from outside the game. an opponent chooses one of them. "
             "you put that card into your hand."):                                               # 400.11, 100.4b, 701.20a, 400.11b
        return [{"fa": "dal_fuori", "n": 2}]
    if t == "target opponent reveals their hand. you choose a nonland card from it. exile that card.":   # Null Summoner: 701.20a,
        return [{"fa": "esilia_scelta_da_te", "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"}),   # 701.13a, 607.2a
                 "non_tipi": ["land"], "collega": True}]
    m = re.fullmatch(r"target opponent reveals their hand\. you choose an? (nonland|noncreature, nonland|artifact or creature|creature|instant or sorcery) "
                     r"card from it(?:\. exile| and exile) that card\.(.*)", t)
    if m:                                                                                        # 701.20a, 701.13a (14 nov 2026): la
        d = {"fa": "esilia_scelta_da_te", "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"})}   # sceglie chi la lancia
        k = m.group(1)
        if k.startswith("non"): d["non_tipi"] = [w.strip()[3:] for w in k.split(",")]
        else: d["tipi"] = k.split(" or ")
        return [d] + (frasi(m.group(2).strip(), ctx) if m.group(2).strip() else [])
    if t == "copy it. you may choose new targets for the copy.":                                  # 707.10, 707.10c
        return [{"fa": "copia_magia", "chi": "magia_evento", "nuovi_bersagli": True}]
    if t == "search your library for a planeswalker card, reveal it, then shuffle and put that card on top.":
        return [{"fa": "cerca", "tipo": ["Planeswalker"], "dove": "cima"}]                        # 701.23a, 701.24b
    if t == "when you next cast an instant or sorcery spell this turn, copy that spell. you may choose new targets for the copy.":
        return [{"fa": "ritardata", "fino": "fine_turno",                                         # 603.7b, 707.10, 707.10c
                 "ab": {"tipo": "innescata", "una_volta": True, "quando": {"evento": "lanci", "tipi": ["instant", "sorcery"]},
                        "fa": [{"fa": "copia_magia", "chi": "magia_evento", "nuovi_bersagli": True}]}}]
    m = re.fullmatch(r"choose target (.+?)\. its owner shuffles it into their library\.", t)
    if m:                                                                                        # Living Library
        r = bersaglio("target " + m.group(1))
        if r is None: raise Mancante(f"bersaglio {m.group(1)!r}")
        return [{"fa": "mescola_nel_grimorio", "chi": ctx.nuovo(r)}]
    m = re.fullmatch(r"choose target (.+?)\. its owner may put it on top of their library\. if they do, ~ deals (\d+) damage to them\. "
                     r"if they didn't put the card on top of their library, they put it on the bottom\.", t)
    if m:                                                                                        # Clash of Elements
        r = bersaglio("target " + m.group(1))
        if r is None: raise Mancante(f"bersaglio {m.group(1)!r}")
        return [{"fa": "cima_o_fondo", "chi": ctx.nuovo(r), "danno_se_cima": int(m.group(2))}]
    t = t.replace("reveal it, then shuffle and put that card on top", "reveal it §cima")       # 701.24b: una frase sola
    t = re.sub(r", then ", ". ", t)
    t = re.sub(r"(?<=\. )then ", "", t)
    t = re.sub(r"^draw a card\. if this spell wasn't cast from your hand, draw two cards instead\.?$", "§gemelli", t)
    if t == "§gemelli": return [{"fa": "pesca", "n": 1, "se_non_dalla_mano": 2}]                       # «instead»: una sostituzione del testo
    t = " ".join(x if re.match(r"(?:then )?if ", x) else re.sub(r" and you (gain|lose) (?!x life, where x is)", r". you \1 ", x)
                 for x in re.split(r"(?<=\.)\s+", t))                                              # (la stessa X: una frase sola, 608.2h;
                                                                                                   # «if ..., A and you gain»: una sola, 608.2c)
    t = re.sub(r",? and put a plan counter on this enchantment\.", r". put a plan counter on this enchantment.", t)   # 608.2c (14 nov 2026)
    t = re.sub(r"^((?:you )?draw (?:a|one|two) cards?) and (gain \d+ life)", r"\1. \2", t)
    t = re.sub(r"^((?:you )?draw a card) and (put a \+1/\+1 counter on (?:~|this creature))", r"\1. \2", t)   # 14 nov 2026
    inizio_prec = inizio = 0
    lista_f = [x for x in re.split(r"(?<=\.)\s+", t) if x.strip()]
    k_f = -1
    while k_f + 1 < len(lista_f):
        k_f += 1
        f = lista_f[k_f].strip()
        inizio_prec, inizio = inizio, len(out)
        mq = re.fullmatch(r"(?:then )?if (?:it|this enchantment|this artifact|~) has (two|three|four|five|six|seven|eight) or more (quest|charge) counters "
                          r"on it, (instead )?(.+?)( instead)?\.?", f)
        if mq:                                                                                   # 608.2c (14 nov 2026): alla risoluzione
            soglia = {"tipo": {"quest": "quest", "charge": "carica"}[mq.group(2)], "n": numero(mq.group(1))}
            nuove = frasi(mq.group(4) + ".", ctx)
            if mq.group(3) or mq.group(5):                                                        # «instead»: l'istruzione di prima
                if inizio_prec == len(out): raise Mancante("«instead» senza l'effetto da sostituire")   # vale solo sotto la soglia
                for j_ in range(inizio_prec, len(out)): out[j_] = dict(out[j_], se=dict(out[j_].get("se") or {}, segnalini_fonte_meno=soglia))
            out += [dict(d, se=dict(d.get("se") or {}, segnalini_fonte_almeno=soglia)) for d in nuove]
            continue
        mk = re.fullmatch(r"if (?:(?:this spell|this creature|it|~) was kicked|this spell's additional cost was paid), (instead )?(.+?)( instead)?\.?", f)
        if mk:                                                                                   # 702.33d, 608.2c (14 nov 2026)
            sost = bool(mk.group(1) or mk.group(3))
            n_req = len(ctx.reqs)
            md = re.fullmatch(r"it deals (\d+) damage", mk.group(2))
            if sost and md and out and out[-1]["fa"] == "danno": nuove = [dict(out[-1], n=int(md.group(1)))]   # lo stesso bersaglio
            else: nuove = frasi(mk.group(2) + ".", ctx)
            if len(ctx.reqs) != n_req: raise Mancante("702.33d: col kicker i bersagli cambiano")
            if sost:
                if inizio_prec == len(out): raise Mancante("«instead» senza l'effetto da sostituire")
                for j_ in range(inizio_prec, len(out)): out[j_] = dict(out[j_], se=dict(out[j_].get("se") or {}, facoltativo_pagato=False))
            out += [dict(d, se=dict(d.get("se") or {}, facoltativo_pagato=True)) for d in nuove]
            continue
        mc = re.fullmatch(r"(?:then )?if you control (.+?), (.+?)\.?", f)
        if mc and "instead" not in f:                                                            # 608.2c: «if you control ..., X» alla risoluzione
            cond = cond_controlli(mc.group(1))
            if cond is not None:
                out += [dict(d, se=dict(d.get("se") or {}, controlli_cond=cond)) for d in frase(mc.group(2), ctx)]
                continue
        ms_ = re.fullmatch(r"if (four|five|six|seven|eight) or more mana was spent to cast that spell, (.+?)( instead)?\.?", f)
        if ms_:                                                                                  # 608.2c, 601.2h (14 nov 2026)
            n_ = numero(ms_.group(1))
            if ms_.group(3):                                                                     # «... instead»: al posto dell'ultima
                if not out: raise Mancante("«instead» senza l'effetto da sostituire")
                out[-1] = dict(out[-1], se=dict(out[-1].get("se") or {}, mana_speso_meno=n_))
            out += [dict(d, se=dict(d.get("se") or {}, mana_speso_almeno=n_)) for d in frase(ms_.group(2), ctx)]
            continue
        if re.fullmatch(r"if excess damage was dealt to that permanent this way, empower jace x, where x is that excess damage\.?", f):
            out.append({"fa": "empower_jace", "n": {"conta": {"tipo": "eccesso"}}, "se": {"eccesso": True}}); continue   # 120.10
        if f.rstrip(".") == "sacrifice it at the beginning of the next end step" and out and out[-1]["fa"] in ("pedina", "copia_pedina"):
            out.append({"fa": "sacrifica_ritardata", "chi": "create"}); continue                  # 603.7 (14 nov 2026)
        ms_ = re.fullmatch(r"sacrifice (?:that token|those tokens|them) (at the beginning of the next end step|at end of combat)\.?", f)
        if ms_ and out and out[-1]["fa"] == "pedina":                                            # 603.7, 511.2 (15 nov 2026): «at end of
            d_ = {"fa": "sacrifica_ritardata", "chi": "create"}                                     # combat» = all'inizio del passo di fine
            if "combat" in ms_.group(1): d_["passo"] = "fine"                                       # combattimento
            out.append(d_); continue
        ms_ = re.fullmatch(r"search your library for up to x basic land cards, where x is (.+?)\.?", f)
        if ms_:                                                                                  # 701.23a, 608.2h (14 nov 2026)
            out.append({"fa": "cerca", "tipo": ["Basic", "Land"], "quante": {"conta": quantita(ms_.group(1), ctx)}, "dove": "?"}); continue
        if out and out[-1].get("fa") == "cerca" and out[-1].get("dove") == "?":
            if re.fullmatch(r"reveal those cards, put them into your hand(?:, then shuffle)?\.?", f):
                out[-1] = dict(out[-1], dove="mano"); continue
            if re.fullmatch(r"put those cards onto the battlefield tapped(?:, then shuffle)?\.?", f):
                out[-1] = dict(out[-1], dove="campo", tappata=True); continue
            raise Mancante(f"ricerca senza la destinazione: {f!r}")
        if out and out[-1].get("fa") == "cerca" and f.rstrip(".") in ("then shuffle", "shuffle"): continue   # 701.24b: cerca mescola gia'
        mx = re.fullmatch(r"(.+), where x is (.+?)\.?", f)
        if mx and mx.group(1).startswith("you may "):                                            # 603.5, 608.2h (14 nov 2026)
            out += [dict(d, puoi=True) for d in _con_x(frase(mx.group(1)[8:], ctx, x_ammessa=True), quantita(mx.group(2), ctx))]
            continue
        if mx:                                                                                   # 608.2h: X si conta alla risoluzione
            spec = quantita(mx.group(2), ctx)
            out += _con_x(frase(mx.group(1), ctx, x_ammessa=True), spec)
            continue
        mk = re.fullmatch(r"draw a card for each color among other artifacts you control\.?", f)
        if mk: out.append({"fa": "pesca", "n": {"conta": {"tipo": "colori_altri_artefatti"}}}); continue
        mx = re.fullmatch(r"draw a card for each ([a-z]+) you control\.?", f)
        if mx and mx.group(1) in SOTTOTIPI_205:                                                  # 205.3g-i (14 nov 2026)
            out.append({"fa": "pesca", "n": {"conta": {"tipo": "controlli", "sel": {"tipi": ["permanent"], "sottotipo": mx.group(1).title()}}}}); continue
        mx = re.fullmatch(r"for each ([a-z]+) you control, (create .+?)\.?", f)
        if mx and (mx.group(1) in SOTTOTIPI_205 or mx.group(1) in ("creature", "artifact", "land", "enchantment")):   # 14 nov 2026
            nuove_ = frase(mx.group(2), ctx)
            if len(nuove_) == 1 and nuove_[0].get("fa") == "pedina" and nuove_[0].get("quante", 1) == 1:
                w_ = mx.group(1)
                sel_ = {"tipi": [w_]} if w_ in ("creature", "artifact", "land", "enchantment") else {"tipi": ["permanent"], "sottotipo": w_.title()}
                out.append(dict(nuove_[0], quante={"conta": {"tipo": "controlli", "sel": sel_}})); continue
        mx = re.fullmatch(r"draw a card for each (creature|artifact|land) you control\.?", f)
        if mx:
            out.append({"fa": "pesca", "n": {"conta": {"tipo": "controlli", "sel": {"controllo": "tuo", "tipi": [mx.group(1)]}}}}); continue
        m0 = re.fullmatch(r"put a (\+1/\+1|loyalty) counter on it if it's a (creature|planeswalker)\.?", f)
        if m0:
            out += frase(f.rstrip("."), ctx); continue
        if f == "reveal cards from the top of your library until you reveal a creature or planeswalker card.":
            out.append({"fa": "rivela_fino", "tipi": ["creature", "planeswalker"]}); continue      # 701.20a
        mrv = re.fullmatch(r"(you may )?reveal cards from the top of your library until you reveal (a|an|two) ([a-z]+(?: or [a-z]+)?) cards?\.?", f)
        if mrv and all(w in TIPI_FILTRO - {"permanent"} for w in mrv.group(3).split(" or ")):   # 701.20a (14 nov 2026)
            out.append(dict({"fa": "rivela_fino", "tipi": mrv.group(3).split(" or "), "n": 2 if mrv.group(2) == "two" else 1},
                            **({"puoi": True} if mrv.group(1) else {}))); continue
        mrv = re.fullmatch(r"put (that card|those (?:land |creature )?cards) (onto the battlefield( tapped)?|into your hand) and the rest on the bottom "
                           r"of your library in a random order\.?", f)
        if mrv and out and out[-1]["fa"] == "rivela_fino" and (mrv.group(1) == "that card") == (out[-1].get("n", 1) == 1) \
                and not (f == "put that card onto the battlefield and the rest on the bottom of your library in a random order."):
            out[-1] = dict(out[-1], dove="mano" if "hand" in mrv.group(2) else "campo", **({"tappata": True} if mrv.group(3) else {}))
            continue
        if f == "put that card onto the battlefield and the rest on the bottom of your library in a random order.":
            if not out or out[-1]["fa"] != "rivela_fino": raise Mancante("«that card» senza rivelare")
            continue
        if f in ("the flashback cost is equal to its mana cost.", "the flashback cost is equal to its mana cost"):
            if not out or out[-1]["fa"] != "dai_flashback": raise Mancante("costo di flashback senza flashback dato")
            continue
        if re.fullmatch(r"if that permanent's mana value was 3 or less, return it to the battlefield tapped under your control\.?", f):
            if not out or out[-1]["fa"] != "esilia": raise Mancante("«that permanent» senza esilio")
            out.append({"fa": "ritorna_esiliata_tua", "mv_max": 3}); continue
        if f in ("exile it at the beginning of the next end step.", "exile it at the beginning of the next end step"):
            if not out or out[-1]["fa"] != "ritorna_esiliata_tua": raise Mancante("ritardata senza oggetto")
            continue                                                                             # la crea ritorna_esiliata_tua (603.7)
        mr = re.fullmatch(r"if this spell was cast from a graveyard, put a \+1/\+1 counter on each of them for every (two|three|four) cards in your graveyard\.?", f)
        if mr and out and out[-1]["fa"] == "pedina":
            out.append({"fa": "segnalini", "tipo": "+1/+1", "n": {"conta": {"tipo": "cimitero_ogni", "ogni": numero(mr.group(1))}}, "chi": "create",
                        "se": {"dal_cimitero": True}}); continue
        if re.fullmatch(r"if you've scried or surveilled this turn, put a \+1/\+1 counter on that creature instead\.?", f):
            if not out or out[-1]["fa"] != "pompa": raise Mancante("«instead» senza l'effetto da sostituire")
            ch = out[-1]["chi"]
            out[-1] = dict(out[-1], se=dict(out[-1].get("se") or {}, guardato_turno=False))
            out.append({"fa": "segnalini", "tipo": "+1/+1", "n": 1, "chi": ch, "se": {"guardato_turno": True}}); continue
        if re.fullmatch(r"if you put a noncreature, nonland card into your graveyard this way, put that card into your hand\.?", f):
            out.append({"fa": "riprendi_sorvegliata", "non_tipi": ["creature", "land"]}); continue
        mv_ = re.fullmatch(r"spend this mana only to (.+?)\.?", f)
        if mv_ and vincolo_mana(mv_.group(1)) is not None:                                       # 106.6 (15 nov 2026: ogni vincolo letto)
            if not out or out[-1]["fa"] != "aggiungi_mana": raise Mancante("vincolo senza mana prima")
            out[-1] = dict(out[-1], vincolo=vincolo_mana(mv_.group(1))); continue
        if f.rstrip(".") in ("return it to the battlefield", "return that card to the battlefield"):   # 110.2a: sotto chi ce la mette
            if not out or out[-1]["fa"] != "esilia": raise Mancante("«return it» senza un esilio prima")
            out.append({"fa": "ritorna_esiliata", "tuo": True}); continue
        if f.rstrip(".") in ("return that card to the battlefield tapped under its owner's control",
                             "return it to the battlefield tapped under its owner's control") and out and out[-1]["fa"] == "esilia":
            out.append({"fa": "ritorna_esiliata", "tappata": True}); continue                     # 400.7, 110.2 (15 nov 2026): dopo un esilio
        if f in ("return that card to the battlefield under its owner's control.", "return that card to the battlefield under its owner's control"):
            if not out or out[-1]["fa"] != "esilia": raise Mancante("«that card» senza un esilio prima")
            out.append({"fa": "ritorna_esiliata"}); continue
        mr_ = re.fullmatch(r"(?:if you do, )?return (it|that card|those cards|them) to the battlefield under (its|their) owner's control"
                           r"( with a \+1/\+1 counter on it)?( at the beginning of the next end step)?\.?", f)
        if mr_ and ((mr_.group(1) in ("it", "that card")) == (mr_.group(2) == "its")):          # 400.7, 603.7, 614.1c (14 nov 2026)
            if not out or out[-1]["fa"] != "esilia": raise Mancante("«return it» senza un esilio prima")
            if mr_.group(3) and mr_.group(4): raise Mancante("ritorno ritardato coi segnalini")
            d_ = {"fa": "ritorna_esiliata"}
            if mr_.group(3): d_["segnalini"] = {"+1/+1": 1}
            if mr_.group(4): d_["ritardata"] = True
            out.append(d_); continue
        if re.fullmatch(r"if you put a card with mana value less than or equal to the amount of life you gained this turn into your "
                        r"graveyard this way, put that card into your hand\.?", f):
            out.append({"fa": "riprendi_sorvegliata"}); continue
        mj = re.fullmatch(r"put a \+1/\+1 counter on (.+) for each card you've discarded this turn\.?", f)
        if mj:
            out.append({"fa": "segnalini", "tipo": "+1/+1", "n": {"conta": {"tipo": "scartate_turno"}}, "chi": chi_frase(mj.group(1), ctx)}); continue
        if f in ("if your library has no cards in it, you win the game.", "if your library has no cards in it, you win the game"):
            out.append({"fa": "vinci", "se": {"grimorio_vuoto": True}}); continue
        mc = re.fullmatch(r"choose target (.+?)\. its owner shuffles it into their library\.?", f)
        if mc: raise Mancante("frase in due")
        if re.fullmatch(r"if that permanent was a legendary enchantment, draw a card\.?", f):
            out.append({"fa": "pesca", "n": 1, "se": {"bersaglio_era": ["legendary", "enchantment"], "k": int(ctx.ultimo().split(":")[1])}})
            continue
        m = re.fullmatch(r"if it wasn't attacking, its controller draws a card\.?", f)
        if m:
            out.append({"fa": "pesca", "n": 1, "chi": "controllore_" + ctx.ultimo(), "se": {"bersaglio_attaccava": False,
                        "k": int(ctx.ultimo().split(":")[1])}})
            continue
        if f.rstrip(".") == "choose one of them":                                                # «choose one of them» (dopo l'esilio di due)
            if not out or out[-1]["fa"] != "esilia_cima" or out[-1].get("n", 1) < 2: raise Mancante("«one of them» senza un esilio di piu' carte")
            out[-1] = dict(out[-1], scegli_uno=True); continue
        if f.rstrip(".") in ("until the end of your next turn, you may play that card",                 # 601.3, 611.2a
                             "until the end of your next turn, you may play those cards"):
            if not out or out[-1]["fa"] != "esilia_cima": raise Mancante("«that card» senza un esilio dal grimorio prima")
            if f.rstrip(".").endswith("that card") and out[-1].get("n", 1) > 1 and not out[-1].get("scegli_uno"):
                raise Mancante("«that card» dopo un esilio di piu' carte")
            if f.rstrip(".").endswith("those cards") and out[-1].get("scegli_uno"): raise Mancante("«those cards» dopo «one of them»")
            out.append(dict({"fa": "permesso_gioca", "fino": "fine_prossimo_turno"}, **({"uno": True} if out[-1].get("scegli_uno") else {}))); continue
        if f.rstrip(".") == "you may play that card this turn":                                  # 601.3, 611.2a
            if not out or out[-1]["fa"] not in ("esilia_cima", "esilia_fino_non_terra"): raise Mancante("«that card» senza un esilio dal grimorio prima")
            out.append({"fa": "permesso_gioca", "fino": "fine_turno"}); continue
        if f.rstrip(".") in ("exile cards from the top of your library until you exile a nonland card",   # 701.13a (14 nov 2026)
                             "then exile cards from the top of your library until you exile a nonland card"):
            out.append({"fa": "esilia_fino_non_terra"}); continue
        if out and out[-1]["fa"] == "esilia_fino_non_terra" and f.rstrip(".") in ("you may cast that card this turn", "you may play that card this turn"):
            out.append({"fa": "permesso_gioca", "fino": "fine_turno"}); continue                  # 601.3, 611.2a
        mg_ = re.fullmatch(r"you may cast (?:that card|it) without paying its mana cost if (?:the|that) spell's mana value is "
                           r"(?:(\d+) or less|(less than or equal to|less than) (.+?))\.?", f)
        if mg_ and out and out[-1]["fa"] in ("esilia_fino_non_terra", "esilia_cima") and out[-1].get("n", 1) == 1:   # 118.9, 608.2g
            d_ = {"fa": "lancia_esiliata", "puoi": True, "gratis": True}
            if mg_.group(1): d_["n"] = int(mg_.group(1))
            else: d_["n"], d_["minore"] = {"conta": quantita(mg_.group(3), ctx)}, mg_.group(2) == "less than"
            out.append(d_); continue
        if re.fullmatch(r"(?:if you don't(?: cast (?:that card|it) this way)?|otherwise), put (?:that card|it) into your hand\.?", f) and out and out[-1]["fa"] == "lancia_esiliata":
            out[-1] = dict(out[-1], segna=True)                                                   # 608.2c: «If you don't»
            out.append({"fa": "in_mano_esiliata", "se": {"fatto": False}}); continue
        if f.rstrip(".") == "you may cast that card":                                            # 608.2g, 603.5
            if not out or out[-1]["fa"] != "esilia_cima": raise Mancante("«that card» senza un esilio dal grimorio prima")
            out.append({"fa": "lancia_esiliata", "puoi": True}); continue
        m1 = re.fullmatch(r"if you sacrificed a creature this way, (.+)", f)
        if m1:                                                                                   # «this way»: lo dice il sacrificio di prima
            if not out or out[-1]["fa"] != "sacrifica": raise Mancante("«sacrificed this way» senza un sacrificio prima")
            for d in frasi(m1.group(1), ctx): out.append(dict(d, se=dict(d.get("se") or {}, sacrificato_tu=True)))
            continue
        if f.rstrip(".") == "for each opponent who didn't discard two nonland cards this way, you draw a card":
            if not out or out[-1]["fa"] != "scarta": raise Mancante("«discard this way» senza uno scarto prima")
            out.append({"fa": "pesca", "n": {"conta": {"tipo": "avversari_senza_due_nonterra"}}}); continue   # 608.2h
        m1 = re.fullmatch(r"if you don't, (.+)", f)
        if m1:                                                                                   # «If you don't»: l'azione con «you may» non e' successa
            if not out or not out[-1].get("puoi"): raise Mancante("«if you don't» senza un «you may» prima")
            for d in frasi(m1.group(1), ctx): out.append(dict(d, se=dict(d.get("se") or {}, fatto=False)))
            continue
        if f.rstrip(".") == "you may cast this card for as long as it remains exiled":            # 601.3, 611.2b, 400.7j: un permesso
            out.append({"fa": "permesso_questa", "fino": "finche_in_esilio"}); continue
        if f in ("you may play an additional land this turn.", "you may play an additional land this turn"):
            out += frase("play an additional land this turn", ctx); continue                     # un permesso, non una scelta
        m1 = re.fullmatch(r"when you discard one or more nonland cards this way, tap up to that many target creatures and put a stun "
                          r"counter on each of them\.?", f)
        if m1:                                                                                   # 603.12, 601.2c, 115.6: la riflessa,
            if not out or out[-1]["fa"] != "scarta": raise Mancante("«this way» senza uno scarto prima")   # quante carte la dice lo scarto
            ab = {"tipo": "innescata", "quando": {"evento": "riflessa"},
                  "bersagli": [{"chi": ["creature"], "fino_a": True, "quanti": "N"}],
                  "fa": [{"fa": "tappa", "chi": "bersaglio:0"}, {"fa": "stordisci", "chi": "bersaglio:0", "n": 1}]}
            out.append({"fa": "riflessa", "ab": ab, "conta": {"tipo": "scartate_qui", "non_tipi": ["land"]}})
            continue
        m1 = re.fullmatch(r"when you do, (.+)", f)
        if m1:                                                                                   # 603.12: l'abilita' riflessa, fino alla
            cr = Contesto(ctx.nome)                                                              # fine del paragrafo (14 nov 2026)
            corpo = " ".join([m1.group(1)] + [x.strip() for x in lista_f[k_f + 1:]])
            k_f = len(lista_f)
            se_r = None
            ms_ = re.match(r"if (?:it|this enchantment|this artifact|~) has (two|three|four|five|six|seven|eight) or more (quest|charge) counters on it, ", corpo)
            if ms_:                                                                              # 603.4: il «se» della riflessa
                corpo, se_r = corpo[ms_.end():], {"segnalini_fonte_almeno": {"tipo": {"quest": "quest", "charge": "carica"}[ms_.group(2)],
                                                                             "n": numero(ms_.group(1))}}
            ab = {"tipo": "innescata", "quando": {"evento": "riflessa"}, "fa": frasi(corpo, cr)}
            if se_r: ab["se"] = se_r
            if cr.reqs: ab["bersagli"] = cr.reqs
            if not out: raise Mancante("«when you do» senza un'azione prima")
            out[-1] = dict(out[-1], segna=True)
            out.append({"fa": "riflessa", "ab": ab})
            continue
        m1 = re.fullmatch(r"if you do, (.+)", f)
        if m1:                                                                                   # «If you do»
            if not out: raise Mancante("«if you do» senza un'azione prima")
            out[-1] = dict(out[-1], segna=True)
            for d in frasi(m1.group(1), ctx): out.append(dict(d, se=dict(d.get("se") or {}, fatto=True)))
            continue
        if f.startswith("you may "):
            for d in frase_o_azioni(f[8:], ctx): out.append(dict(d, puoi=True))                  # 15 nov 2026: anche gli ultimi tentativi
            continue
        if f in ("choose a creature type.", "choose a creature type"):                           # 205.3m, 608.2c (14 nov 2026)
            out.append({"fa": "scegli_tipo"}); continue
        if out and any(d_.get("fa") == "scegli_tipo" for d_ in out):                             # «of that type»: il tipo appena scelto
            if re.fullmatch(r"draw a card for each permanent you control of (?:that|the chosen) type\.?", f):
                out.append({"fa": "pesca", "n": {"conta": {"tipo": "controlli", "sel": {"tipi": ["permanent"], "tipo_scelto": True}}}}); continue
            m_t = re.fullmatch(r"other permanents you control of (?:that|the chosen) type gain ([a-z ,]+) until end of turn\.?", f)
            if m_t:
                out.append({"fa": "dai_parole", "chi": {"tipi": ["permanent"], "controllo": "tuo", "altre": True, "tipo_scelto": True},
                            "parole": parole_lista(m_t.group(1)), "durata": "fine_turno"}); continue
            if re.fullmatch(r"return all creature cards of (?:that|the chosen) type from your graveyard to the battlefield\.?", f):
                out.append({"fa": "rianima_tutte", "tipi": ["creature"], "tipo_scelto": True}); continue   # 400.7
            if re.fullmatch(r"create a treasure token for each creature you control of (?:that|the chosen) type\.?", f):
                out.append(dict(pedina_predefinita("treasure"), quante={"conta": {"tipo": "controlli", "sel": {"tipi": ["creature"], "tipo_scelto": True}}}))
                continue
        mw = re.fullmatch(r"put a \+1/\+1 counter on each other ([a-z]+) token you control\.?", f)
        if mw and out and out[-1]["fa"] == "pedina" and mw.group(1) in SOTTOTIPI:               # «other»: oltre la pedina appena creata
            out.append({"fa": "segnalini", "tipo": "+1/+1", "n": 1,
                        "chi": {"tipi": ["permanent"], "pedina": True, "sottotipo": mw.group(1).title(), "controllo": "tuo", "non_create": True}})
            continue
        mi_ = re.fullmatch(r"(?:then )?if ([^,]+), (instead )?(.+?)( instead)?\.?", f)
        if not (mi_ and (mi_.group(2) or mi_.group(4))):
            mi2_ = re.fullmatch(r"(.+?) instead if (.+?)\.?", f)                                   # «X instead if COND»
            mi_ = None
            if mi2_ and "," not in mi2_.group(2): cond_i_, corpo_i_ = mi2_.group(2), mi2_.group(1)
            else: cond_i_ = corpo_i_ = None
        else: cond_i_, corpo_i_ = mi_.group(1), mi_.group(3)
        if cond_i_ is not None and cond_statica(cond_i_) is not None and inizio_prec < len(out):   # 608.2c, 614.1a (giro 9): «instead»
            cs_ = cond_statica(cond_i_)                                                            # sostituisce l'istruzione di prima quando
            n_req = len(ctx.reqs)                                                                  # la condizione e' vera alla risoluzione
            try:
                md_ = re.fullmatch(r"(?:it|that creature|~) (?:deals|gets) (.+)", corpo_i_)
                if md_ and len(out) - inizio_prec == 1 and out[-1]["fa"] in ("danno", "pompa"):     # «it deals 5 damage instead»: stesso
                    base_ = out[-1]                                                                # bersaglio, un numero diverso
                    mn_ = re.fullmatch(r"(\d+) damage(?: to .+)?", md_.group(1)) if base_["fa"] == "danno" else re.fullmatch(r"([+-]\d+)/([+-]\d+) until end of turn", md_.group(1))
                    if not mn_: raise Mancante("instead")
                    nuove = [dict(base_, n=int(mn_.group(1)))] if base_["fa"] == "danno" else [dict(base_, p=int(mn_.group(1)), t=int(mn_.group(2)))]
                else: nuove = frasi(corpo_i_ + ".", ctx)
                if len(ctx.reqs) != n_req: raise Mancante("608.2c: con la condizione i bersagli cambiano")
            except Mancante:
                del ctx.reqs[n_req:]; nuove = None
            if nuove:
                for j_ in range(inizio_prec, len(out)): out[j_] = dict(out[j_], se=dict(out[j_].get("se") or {}, statica_non=cs_))
                out += [dict(d, se=dict(d.get("se") or {}, statica=cs_)) for d in nuove]
                continue
        mh_ = re.fullmatch(r"if you have fewer than (two|three|four|five|six|seven|eight|nine|ten) cards in hand, draw cards equal to the difference\.?", f)
        if mh_:                                                                                    # 121.1, 608.2h (giro 9)
            out.append({"fa": "pesca", "n": {"conta": {"tipo": "mano_fino", "n": _N_MANO[mh_.group(1)]}}}); continue
        mg_ = re.fullmatch(r"if this spell was cast from a graveyard, (instead |also )?(.+?)( instead)?\.?", f)
        if mg_:                                                                                  # 601.2a, 608.2c (15 nov 2026, l'ultimo tentativo): da dove e'
            sost = bool((mg_.group(1) or "").startswith("instead") or mg_.group(3))              # stata lanciata, alla risoluzione
            n_req = len(ctx.reqs)
            nuove = frasi(mg_.group(2) + ".", ctx)
            if len(ctx.reqs) != n_req: raise Mancante("608.2c: dal cimitero i bersagli cambiano")
            if sost:
                if inizio_prec == len(out): raise Mancante("«instead» senza l'effetto da sostituire")
                for j_ in range(inizio_prec, len(out)): out[j_] = dict(out[j_], se=dict(out[j_].get("se") or {}, lanciata_dal_cimitero=False))
            out += [dict(d, se=dict(d.get("se") or {}, lanciata_dal_cimitero=True)) for d in nuove]
            continue
        n_req_, ul_ = len(ctx.reqs), ctx.ultimo_chi
        try: nuove = frase_o_azioni(f, ctx)
        except Mancante as e0_:
            if k_f == 0 or not re.match(r"(?:look at|reveal) the top ", f): raise
            del ctx.reqs[n_req_:]; ctx.ultimo_chi = ul_                                         # 15 nov 2026: lo sguardo dopo
            try: r_ = cima_fissa(" ".join(lista_f[k_f:]), ctx)                                  # un'altra frase, letto con le frasi
            except Mancante: r_ = None                                                          # che seguono (701.20a, 401.4)
            if r_ is None:
                del ctx.reqs[n_req_:]; ctx.ultimo_chi = ul_
                raise e0_
            out += r_
            break
        out += nuove
        if nuove and nuove[-1]["fa"] == "pedina" and not ctx.reqs: ctx.ultimo_chi = "create"     # «It gains haste»
    return out


# ====================================================================== le abilita'
QUANDO = [
    (r"(?:~|this creature|this enchantment|this artifact|this equipment|this land|this vehicle|this spacecraft|this aura|this saga|"
     r"this class|this planeswalker) enters", {"evento": "entra"}),
    (r"~ enter", {"evento": "entra"}),                                                          # un nome plurale («Culber and Stamets enter»)
    (r"~ attack", {"evento": "attacca"}),                                                       # un nome plurale («Don & Raph attack»)
    (r"this land enters untapped", {"evento": "entra", "stappata": True}),                     # 603.6a: entra stappata
    (r"an? (?!creature |artifact |nontoken |land |plains |island |swamp |mountain |forest )([a-z]+) you control enters", "tipo_entra"),
    (r"(?:~|this creature|this enchantment|this artifact|this land|this vehicle) leaves the battlefield", {"evento": "lascia"}),   # 603.6c
    (r"you cast an instant or sorcery spell", {"evento": "lanci", "tipi": ["instant", "sorcery"]}),
    (r"you cast your second spell each turn", {"evento": "lanci", "n_del_turno": 2}),
    (r"you cast a spell during an opponent's turn", {"evento": "lanci", "nel_turno_di": "avversario"}),      # 14 nov 2026
    (r"you face a dilemma", {"evento": "dilemma"}),                                                          # 700.17
    (r"equipped creature deals combat damage to a player", {"evento": "attaccata_danno_giocatore"}),         # 510.3a, 301.5
    (r"this creature or another creature you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo"}}),
    (r"a creature you control deals combat damage to a player", {"evento": "tua_danno_giocatore"}),          # 510.3a
    (r"another nontoken creature you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo", "altre": True, "non_pedina": True}}),
    (r"(?:~|this creature) attacks while you control a creature with power (\d+) or greater", "attacca_forza"),
    (r"a creature you control attacks alone", {"evento": "una_attacca_sola", "qualsiasi": True}),           # 506.5
    (r"equipped creature attacks", {"evento": "attaccata_attacca"}),                                          # 301.5, 508.1m
    (r"one or more cards leave your graveyard", {"evento": "lasciano_cimitero", "una_per_azione": True}),
    (r"a creature you control with a \+1/\+1 counter on it dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo", "con_segnalino": "+1/+1"}}),
    (r"a creature you control with one or more counters on it dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo", "con_segnalini": True}}),
    (r"a creature you control with mana value (\d) or greater enters", "mv_entra"),
    (r"a creature you control with (deathtouch|flying) deals combat damage to a player", "danno_con_parola"),
    (r"a creature you control with a counter on it deals combat damage to a player", {"evento": "tua_danno_giocatore", "chi": {"con_segnalini": True}}),
    (r"you cast an? (artifact|enchantment|creature|instant|sorcery|planeswalker) spell", "lanci_tipo"),
    (r"you cast a multicolored spell", {"evento": "lanci", "multicolore": True}),                   # 105.2c
    (r"you cast a spell with \{x\} in its mana cost", {"evento": "lanci", "con_x": True}),             # 107.3
    (r"one or more cards leave your graveyard during your turn", {"evento": "lasciano_cimitero", "una_per_azione": True, "nel_tuo_turno": True}),
    (r"one or more creatures you control deal combat damage to a player", {"evento": "tua_danno_giocatore", "una_per_azione": True}),   # 510.3a
    (r"one or more creatures you control with flying deal combat damage to a player",
     {"evento": "tua_danno_giocatore", "una_per_azione": True, "chi": {"con_parola": "flying"}}),
    (r"one or more tokens you control enter", {"evento": "una_entra", "una_per_azione": True, "chi": {"pedina": True, "controllo": "tuo"}}),
    (r"one or more other creatures you control enter", {"evento": "una_entra", "una_per_azione": True,
                                                         "chi": {"tipi": ["creature"], "controllo": "tuo", "altre": True}}),
    (r"one or more other creatures die", {"evento": "una_muore", "una_per_azione": True, "chi": {"tipi": ["creature"], "altre": True}}),
    (r"you cycle this card", {"evento": "ciclata_questa"}),                                                   # 702.29c
    (r"you discard one or more cards", {"evento": "scarto", "di": "tu", "una_per_azione": True}),
    (r"you attack while creatures you control have total power (\d+) or greater", "attacchi_forza"),
    (r"another (?!creature |artifact |nontoken |land |plains |island |swamp |mountain |forest )([a-z]+) you control enters", "altro_tipo_entra"),
    (r"you cast an instant or sorcery spell that targets a creature", {"evento": "lanci", "tipi": ["instant", "sorcery"], "bersaglia_creatura": "qualsiasi"}),
    (r"you cast a spell that targets a creature you control", {"evento": "lanci", "bersaglia_creatura": "tua"}),
    (r"you cast a spell with mana value (\d+) or greater", "mv_min"),
    (r"you draw your second card each turn", {"evento": "pesca_n", "n": 2}),                        # 121.1, 504.1
    (r"(?:~|this creature|this land|this artifact) becomes tapped", {"evento": "diventa_tappata"}),    # 701.26a
    (r"you draw a card", {"evento": "pesca_n"}),
    (r"you discard a card", {"evento": "scarto", "di": "tu"}),                                      # 701.9a
    (r"a creature you control enters", {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo"}}),
    (r"an artifact you control enters", {"evento": "una_entra", "chi": {"tipi": ["artifact"], "controllo": "tuo"}}),
    (r"another artifact you control enters", {"evento": "una_entra", "chi": {"tipi": ["artifact"], "controllo": "tuo", "altre": True}}),
    (r"(?:~|this creature|this vehicle) dies", {"evento": "muore"}),
    (r"enchanted creature dies", {"evento": "attaccata_muore"}),
    (r"(?:~|this creature) is dealt damage", {"evento": "danno_ricevuto", "una_per_azione": True}),
    (r"the beginning of your first main phase", {"evento": "inizio_fase", "fase": "principale_1", "di": "tuo"}),
    (r"the beginning of each opponent's draw step", {"evento": "inizio_passo", "passo": "acquisizione", "di": "avversario"}),
    (r"an opponent casts a spell with mana value 2 or less", {"evento": "lanci", "di": "avversario", "mv_max": 2}),
    (r"a forest you control enters", {"evento": "una_entra", "chi": {"tipi": ["land"], "sottotipo": "Forest", "controllo": "tuo"}}),
    (r"an opponent is dealt noncombat damage", {"evento": "danno_non_combattimento", "una_per_azione": True}),
    (r"you cast a spell that targets an opponent or a creature an opponent controls", {"evento": "lanci", "bersaglia_avversario": True}),
    (r"you cast a prepared spell", {"evento": "lanci", "preparata": True}),
    (r"a creature an opponent controls enters", {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "avversario"}}),
    (r"an opponent activates a loyalty ability", {"evento": "attivi_fedelta", "di": "avversario"}),
    (r"the beginning of each upkeep", {"evento": "inizio_passo", "passo": "mantenimento"}),
    (r"one or more of your opponents are dealt combat damage during your turn", {"evento": "avversari_danno_combattimento", "una_per_azione": True}),
    (r"a creature an opponent controls with power or toughness 1 or less blocks", {"evento": "blocca", "di": "avversario", "fc_max": 1}),
    (r"you discard this card", {"evento": "scartata_questa"}),
    (r"(?:~|this creature|this vehicle) attacks", {"evento": "attacca"}),
    (r"you gain life", {"evento": "guadagni_vita"}),
    (r"the beginning of your upkeep", {"evento": "inizio_passo", "passo": "mantenimento", "di": "tuo"}),
    (r"the beginning of your end step", {"evento": "inizio_passo", "passo": "finale", "di": "tuo"}),
    (r"the beginning of each end step", {"evento": "inizio_passo", "passo": "finale"}),
    (r"the beginning of the end step", {"evento": "inizio_passo", "passo": "finale"}),
    (r"the beginning of combat on your turn", {"evento": "inizio_passo", "passo": "inizio", "di": "tuo"}),
    (r"the beginning of each player's upkeep", {"evento": "inizio_passo", "passo": "mantenimento"}),
    (r"~ becomes the target of a spell or ability an opponent controls", {"evento": "bersagliato"}),
    (r"you cast a noncreature spell", {"evento": "lanci", "non_tipi": ["creature"]}),
    (r"you cast your first noncreature spell each turn", {"evento": "lanci", "non_tipi": ["creature"], "primo_del_turno": True}),
    (r"you cast a creature spell", {"evento": "lanci", "tipi": ["creature"]}),
    (r"you cast an artifact or creature spell", {"evento": "lanci", "tipi": ["artifact", "creature"]}),
    (r"another creature you control enters", {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo", "altre": True}}),
    (r"another nontoken creature you control enters", {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo", "altre": True, "non_pedina": True}}),
    (r"(?:~|this creature) or another creature you control enters", {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo"}}),
    (r"another creature or planeswalker you control enters", {"evento": "una_entra", "chi": {"tipi": ["creature", "planeswalker"], "controllo": "tuo", "altre": True}}),
    (r"a land you control enters", {"evento": "una_entra", "chi": {"tipi": ["land"], "controllo": "tuo"}}),
    (r"another creature you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo", "altre": True}}),
    (r"a creature you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo"}}),
    (r"another creature or planeswalker you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature", "planeswalker"], "controllo": "tuo", "altre": True}}),
    (r"(?:~|this creature) deals combat damage to a player", {"evento": "danno_a_giocatore"}),
    (r"you scry or surveil", {"evento": "guarda"}),
    (r"you put one or more loyalty counters on a planeswalker", {"evento": "segnalini_fedelta", "una_per_azione": True}),
    (r"a player discards one or more cards", {"evento": "scarto", "una_per_azione": True}),
    (r"you activate a loyalty ability", {"evento": "attivi_fedelta"}),
    (r"one or more opponents are dealt noncombat damage", {"evento": "danno_non_combattimento", "una_per_azione": True}),
    (r"a creature you control attacks a player alone", {"evento": "una_attacca_sola"}),
    (r"you cast a spell", {"evento": "lanci"}),                                                  # 601.2i
    (r"you attack", {"evento": "attacchi_tu", "una_per_azione": True}),                          # 508.1m: una volta per dichiarazione
    (r"a creature you control attacks", {"evento": "una_attacca"}),
    (r"you cast an equipment spell or a spell that targets a creature you control", {"evento": "lanci", "equip_o_bersaglia_tua": True}),
    (r"a creature you control with power (\d+) or greater enters", "forza_min"),
    (r"a plains you control enters", {"evento": "una_entra", "chi": {"tipi": ["land"], "controllo": "tuo", "sottotipo": "Plains"}}),
    (r"(?:this aura) enters", {"evento": "entra"}),
    (r"you cast this spell", {"evento": "lanci_questa"}),                                       # 601.2i, 113.6k: dalla pila
    # 14 nov 2026: gli inneschi generici di morti, entrate, magie e vite
    (r"(?:~|this creature) or another creature or artifact you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature", "artifact"], "controllo": "tuo"}}),
    (r"a nontoken creature you control dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "tuo", "non_pedina": True}}),
    (r"a creature an opponent controls dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "controllo": "avversario"}}),
    (r"a creature dies", {"evento": "una_muore", "chi": {"tipi": ["creature"]}}),                # 700.4
    (r"another creature dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "altre": True}}),
    (r"a nontoken artifact you control enters", {"evento": "una_entra", "chi": {"tipi": ["artifact"], "controllo": "tuo", "non_pedina": True}}),
    (r"a player casts a spell", {"evento": "lanci", "di": "chiunque"}),                          # 601.2i
    (r"you gain life for the first time each turn", {"evento": "guadagni_vita", "primo_del_turno": True}),   # 119.9
    (r"a card leaves your graveyard", {"evento": "lasciano_cimitero"}),                          # 603.10a: una per carta
    (r"(?:~|this creature|this artifact|this enchantment) is put into a graveyard from the battlefield", {"evento": "muore"}),   # 603.6c
    (r"you sacrifice another permanent", {"evento": "sacrifichi", "altre": True}),               # 701.21a
    # 14 nov 2026: altri inneschi su eventi gia' noti
    (r"an opponent casts a spell", {"evento": "lanci", "di": "avversario"}),                       # 601.2i
    (r"an opponent discards a card", {"evento": "scarto", "di": "avversario"}),                     # 701.9a
    (r"another nontoken creature dies", {"evento": "una_muore", "chi": {"tipi": ["creature"], "altre": True, "non_pedina": True}}),
    (r"the beginning of each combat", {"evento": "inizio_passo", "passo": "inizio"}),             # 507.1
    (r"the beginning of each player's draw step", {"evento": "inizio_passo", "passo": "acquisizione"}),   # 504.1
    (r"enchanted creature attacks", {"evento": "attaccata_attacca"}),                               # 303.4, 508.1m
    (r"enchanted creature is dealt damage", {"evento": "attaccata_danno", "una_per_azione": True}),   # 303.4, 120.3
    (r"this spacecraft attacks", {"evento": "attacca"}),                                           # 508.1m
    (r"the (second|third|fourth|fifth|sixth|seventh) plan counter is put on this enchantment", "soglia_plan"),     # 122.1, 603.2
]


_TIPI_INNESCO = {"creature", "artifact", "enchantment", "land", "planeswalker"}


def _sel_innesco(x, plurale=False):
    """Il soggetto di un innesco («a nontoken Goblin creature you control», «another creature or artifact you control»,
    «Cats you control») -> selettore o None (15 nov 2026)."""
    sel = {}
    mp_ = re.search(r" with power (\d+) or less$", x)                                              # 208.1 (15 nov 2026)
    if mp_: sel["forza_max"], x = int(mp_.group(1)), x[:mp_.start()]
    for coda, v in ((" you control", "tuo"), (" an opponent controls", "avversario"), (" your opponents control", "avversario")):
        if x.endswith(coda): sel["controllo"], x = v, x[: -len(coda)]; break
    if x.startswith("nontoken "): sel["non_pedina"], x = True, x[9:]
    if x.startswith("token "): sel["pedina"], x = True, x[6:]
    if x in ("token", "tokens") and sel.get("controllo"):                                          # 111.1 (15 nov 2026): «a token you control»
        return dict(sel, pedina=True, tipi=["permanent"])
    mn_ = re.match(r"non-([a-z]+) ", x)                                                            # 205.4b (15 nov 2026): «non-Human»
    if mn_:
        if mn_.group(1) not in TIPI_CREATURA: return None
        sel["non_sottotipi"], x = [mn_.group(1).title()], x[mn_.end():]
    parti = re.split(r" and/or | or ", x)                                                          # giro 11: «creatures and/or artifacts»
    if len(parti) > 2: return None
    tipi, sotto, sotto_o = [], None, []
    for w in parti:
        ws = w.split()
        if plurale:
            if not ws: return None
            ultimo_ = singolare(ws[-1]) or (ws[-1][:-1] if ws[-1].endswith("s") and ws[-1][:-1] in _TIPI_INNESCO else None)
            if ultimo_ is None: return None
            ws[-1] = ultimo_
        if len(ws) == 1 and ws[0] in _TIPI_INNESCO: tipi.append(ws[0])
        elif len(ws) == 1 and ws[0] in TIPI_CREATURA and len(parti) == 1: sotto, tipi = ws[0], ["permanent"]   # 205.3m: «a Goblin»
        elif len(ws) == 2 and ws[0] in TIPI_CREATURA and ws[1] == "creature" and len(parti) == 1: sotto, tipi = ws[0], ["creature"]
        elif len(ws) == 2 and ws == ["artifact", "creature"] and len(parti) == 1: tipi, sel["anche_tipo"] = ["creature"], "artifact"
        elif len(ws) == 1 and ws[0] in TIPI_CREATURA and len(parti) == 2: sotto_o.append(ws[0])     # «a Villain or artifact» (205.3m)
        else: return None
    if sotto_o:
        if tipi and len(sotto_o) == 1: sel["o_sottotipo"] = sotto_o[0].title()
        elif not tipi: tipi, sel["sottotipi_o"] = ["permanent"], [s_.title() for s_ in sotto_o]
        else: return None
    sel["tipi"] = tipi
    if sotto: sel["sottotipo"] = sotto.title()
    return sel


def innesco_composto(cond):
    """603.2, 603.6a, 603.10a, 508.1m (15 nov 2026): l'ultimo tentativo per l'evento di un innesco, a pezzi:
    «[this creature or] another X enters/dies», «a/an X enters/dies/attacks», «one or more [other] Xs enter/die/attack», col
    soggetto letto da _sel_innesco. «This creature or another X»: due eventi, la fonte stessa e un'altra X (603.6a). Un attacco
    vuole «you control» (l'evento guarda le creature di chi controlla la fonte). Altro: None."""
    m = re.fullmatch(r"(?:(~|this creature|this artifact|this enchantment|this land) or )?(another |an? |one or more (?:other )?)(.+?) "
                     r"(enters|enter|dies|die|attacks|attack)( a player)?", cond)
    if not m: return None
    quale, art, x, verbo, gioc_ = m.groups()
    if gioc_ and verbo not in ("attacks", "attack"): return None
    plurale = art.startswith("one or more")
    if plurale != (verbo in ("enter", "die", "attack")): return None                                  # l'accordo del verbo
    sel = _sel_innesco(x, plurale)
    if sel is None: return None
    if art.startswith("another") or "other" in art: sel["altre"] = True
    if quale and not art.startswith("another"): return None
    ev = {"enter": "una_entra", "dies": "una_muore", "die": "una_muore", "attacks": "una_attacca", "attack": "una_attacca"}.get(verbo, "una_entra")
    if ev == "una_attacca" and (sel.get("controllo") != "tuo" or quale): return None
    if ev == "una_muore" and not set(sel["tipi"]) <= {"creature", "planeswalker", "permanent", "artifact", "enchantment", "land"}: return None   # 700.4
    q = {"evento": ev, "chi": sel}
    if gioc_: q["contro_giocatore"] = True                                                         # 506.4 (giro 11): «attack a player»
    if plurale: q["una_per_azione"] = True
    if quale: return [{"evento": "entra" if ev == "una_entra" else "muore"}, q]
    return [q]


def innesco_attacchi(cond):
    """508.1m (giro 11): «whenever you attack with two/three/... or more creatures»: una volta per dichiarazione, con almeno N
    attaccanti dichiarati. Altro: None."""
    m = re.fullmatch(r"you attack with (two|three|four|five) or more creatures", cond)
    if not m: return None
    return [{"evento": "attacchi_tu", "una_per_azione": True, "min_attaccanti": _NUM_PICCOLI[m.group(1)]}]


def innesco_sacrifichi(cond):
    """701.21a (giro 10): «whenever you sacrifice a/an/another X» col soggetto letto da _sel_innesco. Altro: None."""
    m = re.fullmatch(r"you sacrifice (an?|another) (.+)", cond)
    if not m: return None
    sel = _sel_innesco(m.group(2)) if m.group(2) not in ("token", "food") else (
        {"tipi": ["permanent"], "pedina": True} if m.group(2) == "token" else {"tipi": ["permanent"], "sottotipo": "Food"})
    if sel is None: return None
    q = {"evento": "sacrifichi", "chi": sel}
    if m.group(1) == "another": q["altre"] = True
    return [q]


def innesco_lanci(cond):
    """601.2i, 603.2 (giro 8, 15 nov 2026): l'ultimo tentativo per «you cast / an opponent casts a <descrizione> spell»: i colori
    in alternativa («a blue or black spell», 105.2), i tipi di carta in alternativa («instant or sorcery»), un sottotipo da solo
    («a Villain spell», «a Turtle spell»), insieme («a white or blue instant or sorcery spell»). Altro: None."""
    m = re.fullmatch(r"(you cast|an opponent casts|a player casts) an? (.+?) spell", cond)
    if not m: return None
    q = {"evento": "lanci"}
    if m.group(1) == "an opponent casts": q["di"] = "avversario"
    if m.group(1) == "a player casts": q["di"] = "chiunque"
    if m.group(2) == "colorless": return [dict(q, incolore=True)]                                 # 105.2c (giro 10)
    if m.group(2) == "legendary": return [dict(q, tipi=["legendary"])]                            # 205.4d
    ws = m.group(2).split()
    col = []
    while ws and (ws[0] in COLORI or (ws[0] == "or" and col)):
        if ws[0] in COLORI: col.append(COLORI[ws[0]])
        ws = ws[1:]
    resto = " ".join(ws)
    if col: q["colori"] = col
    if resto:
        tipi = [w for w in re.split(r",? or |, ", resto) if w]
        if all(w in _TIPI_CARTA for w in tipi): q["tipi"] = tipi
        elif len(tipi) == 1 and (tipi[0] in TIPI_CREATURA or tipi[0] in SOTTOTIPI_205): q["sottotipo"] = tipi[0].title()
        elif len(tipi) == 2 and tipi[0] in _TIPI_CARTA and (tipi[1] in TIPI_CREATURA or tipi[1] in SOTTOTIPI_205):   # «an artifact or Lesson spell»
            q["tipo_o_sottotipo"] = {"tipi": [tipi[0]], "sottotipo": tipi[1].title()}
        else: return None
    if len(q) == 1 + ("di" in q): return None
    return [q]


def innesco(p, ctx):
    m = re.fullmatch(r"(when|whenever|at) (.+?), (.+)", p)
    if not m: return None
    cond, resto = m.group(2), m.group(3)
    una = False
    if resto.endswith(" this ability triggers only once each turn."):
        resto, una = resto[: -len(" this ability triggers only once each turn.")], True
    o_muore = re.fullmatch(r"(~|this creature) enters or dies", cond)
    o_attacca = re.fullmatch(r"(~|this creature|this vehicle|this spacecraft|this permanent) enters? or attacks?", cond)   # 603.6a, 508.1m
    o_lascia = re.fullmatch(r"(~|this creature|this artifact|this enchantment) enters or leaves the battlefield", cond)   # 603.6a, 603.6c
    o_trasf = re.fullmatch(r"(~|this creature|this land|this artifact) enters or transforms into ~", cond)   # 603.6a, 701.27f
    trovati = []
    if o_muore: trovati = [{"evento": "entra"}, {"evento": "muore"}]
    elif o_lascia: trovati = [{"evento": "entra"}, {"evento": "lascia"}]
    elif o_trasf: trovati = [{"evento": "entra"}, {"evento": "trasforma_in"}]
    elif re.fullmatch(r"(~|this creature|this land|this artifact) transforms into ~", cond): trovati = [{"evento": "trasforma_in"}]   # 701.27f
    elif o_attacca: trovati = [{"evento": "entra"}, {"evento": "attacca"}]
    else:
        for rx, q in QUANDO:
            m3 = re.fullmatch(rx, cond)
            if m3:
                if q == "forza_min": q = {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo", "forza_min": int(m3.group(1))}}
                if q == "mv_entra": q = {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo", "mv_min": int(m3.group(1))}}
                if q == "danno_con_parola": q = {"evento": "tua_danno_giocatore", "chi": {"con_parola": m3.group(1)}}
                if q == "lanci_tipo": q = {"evento": "lanci", "tipi": [m3.group(1)]}
                if q == "mv_min": q = {"evento": "lanci", "mv_min": int(m3.group(1))}
                if q == "attacca_forza": q = {"evento": "attacca", "se_controlli": {"tipi": ["creature"], "forza_min": int(m3.group(1))}}
                if q == "attacchi_forza": q = {"evento": "attacchi_tu", "una_per_azione": True, "forza_totale_min": int(m3.group(1))}
                if q == "soglia_plan": q = {"evento": "soglia_segnalini", "tipo": "plan", "n": {"second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7}[m3.group(1)]}
                if q in ("tipo_entra", "altro_tipo_entra"):
                    st = singolare(m3.group(1))
                    w3 = m3.group(1)
                    if st: sel3 = {"tipi": ["creature"], "controllo": "tuo", "sottotipo": st.title()}
                    elif w3 in SOTTOTIPI_205 and w3 not in ("plains", "island", "swamp", "mountain", "forest"):   # 205.3g-i (14 nov 2026):
                        sel3 = {"tipi": ["permanent"], "controllo": "tuo", "sottotipo": w3.title()}                 # «a Gate», «a Shrine»
                    else: raise Mancante(f"innesco {cond!r}")
                    if q == "altro_tipo_entra": sel3["altre"] = True
                    q = {"evento": "una_entra", "chi": sel3}
                trovati = [q]; break
    if trovati and trovati[0]["evento"] == "attivi_fedelta" and resto.startswith("if you removed two or more loyalty counters to activate it, "):
        resto = resto[len("if you removed two or more loyalty counters to activate it, "):]
        trovati = [dict(trovati[0], tolti_almeno=2)]                                           # 603.4: e' un fatto passato
    if not trovati: trovati = innesco_composto(cond) or innesco_lanci(cond) or innesco_sacrifichi(cond) or innesco_attacchi(cond) or []   # 603.2: l'ultimo tentativo
    if not trovati: raise Mancante(f"innesco {cond!r}")
    se = None
    if resto.startswith("if you gained life this turn, "):                                      # 603.4: il «se» dell'innesco
        resto, se = resto[len("if you gained life this turn, "):], {"vita_guadagnata_turno": True}
    elif resto.startswith("if you control six or more lands, "):
        resto, se = resto[len("if you control six or more lands, "):], {"terre_almeno": 6}
    elif resto.startswith("if three or more creatures died this turn, "):
        resto, se = resto[len("if three or more creatures died this turn, "):], {"morte_turno_almeno": 3}
    elif resto.startswith("if two or more creatures died this turn, "):
        resto, se = resto[len("if two or more creatures died this turn, "):], {"morte_turno_almeno": 2}
    elif resto.startswith("if you control at least five other forests, "):
        resto, se = resto[len("if you control at least five other forests, "):], {"foreste_altre_almeno": 5}
    elif resto.startswith("if an opponent was dealt noncombat damage last turn, "):
        resto, se = resto[len("if an opponent was dealt noncombat damage last turn, "):], {"avversario_danno_nc_ultimo_turno": True}
    elif resto.startswith("if you've drawn three or more cards this turn, "):
        resto, se = resto[len("if you've drawn three or more cards this turn, "):], {"pescate_turno_almeno": 3}
    elif resto.startswith("if you didn't cast a spell this turn, "):
        resto, se = resto[len("if you didn't cast a spell this turn, "):], {"non_lanciato_turno": True}
    elif resto.startswith("if you've activated a loyalty ability this turn, "):
        resto, se = resto[len("if you've activated a loyalty ability this turn, "):], {"fedelta_attivata_turno": True}
    elif resto.startswith("if it isn't a token, ") and trovati[0]["evento"] == "muore":
        resto, se = resto[len("if it isn't a token, "):], {"fonte_non_pedina": True}
    elif re.match(r"if you cast (it|him|her), ", resto) and trovati[0]["evento"] == "entra":         # 603.4: «if you cast it»
        resto, se = re.sub(r"^if you cast (it|him|her), ", "", resto), {"lanciata_tu": True}
    elif re.match(r"if you control (.+?), ", resto) and cond_controlli(re.match(r"if you control (.+?), ", resto).group(1)) is not None             and "instead" not in resto:                                                          # 603.4: «if you control another Elf, ...»
        mm_ = re.match(r"if you control (.+?), ", resto)
        resto, se = resto[mm_.end():], {"controlli_cond": cond_controlli(mm_.group(1))}
    elif resto.startswith("if a creature died under your control this turn, "):                 # 700.4, 603.4 (14 nov 2026)
        resto, se = resto[len("if a creature died under your control this turn, "):], {"morta_tua_turno": True}
    elif resto.startswith("if you attacked this turn, "):                                       # raid (207.2c), 603.4
        resto, se = resto[len("if you attacked this turn, "):], {"attaccato_turno": True}
    elif resto.startswith("if you don't control a planeswalker, "):
        resto, se = resto[len("if you don't control a planeswalker, "):], {"senza_planeswalker": True}
    elif re.match(r"if (?:there are )?(three|four|five|six|seven|eight|ten) or more cards (?:are )?in your graveyard, ", resto):
        mm_ = re.match(r"if (?:there are )?(three|four|five|six|seven|eight|ten) or more cards (?:are )?in your graveyard, ", resto)   # 603.4
        resto, se = resto[mm_.end():], {"cimitero_almeno": {"ten": 10}.get(mm_.group(1)) or numero(mm_.group(1))}
    elif resto.startswith("if a creature died under an opponent's control this turn, "):        # 603.4, 700.4
        resto, se = resto[len("if a creature died under an opponent's control this turn, "):], {"morta_avversario_turno": True}
    elif re.match(r"if (?:this enchantment|this artifact|~) has (two|three|four|five|six|seven|eight) or more (quest|charge) counters on it, ", resto):
        mm_ = re.match(r"if (?:this enchantment|this artifact|~) has (two|three|four|five|six|seven|eight) or more (quest|charge) counters on it, ", resto)
        resto, se = resto[mm_.end():], {"segnalini_fonte_almeno": {"tipo": {"quest": "quest", "charge": "carica"}[mm_.group(2)],   # 603.4
                                                                   "n": numero(mm_.group(1))}}
    elif resto.startswith("if a permanent left the battlefield under your control this turn, "):   # 603.4 (14 nov 2026)
        resto, se = resto[len("if a permanent left the battlefield under your control this turn, "):], {"uscito_tuo_turno": True}
    elif re.match(r"if (it|~) was kicked, ", resto) and trovati[0]["evento"] == "entra":         # 603.4, 702.33d
        resto, se = re.sub(r"^if (it|~) was kicked, ", "", resto), {"facoltativo_pagato": True}
    elif re.match(r"if ((?:\{[wubrgc]\})+) was spent to cast it, ", resto) and trovati[0]["evento"] == "entra":
        mm_ = re.match(r"if ((?:\{[wubrgc]\})+) was spent to cast it, ", resto)               # 603.4, 601.2h: il mana di quei
        resto, se = resto[mm_.end():], {"mana_speso_simboli": mm_.group(1).upper()}             # colori speso per lanciarla
    elif re.match(r"if at least (four|five|six|seven|eight) mana was spent to cast it, ", resto) and trovati[0]["evento"] == "lanci":
        mm_ = re.match(r"if at least (four|five|six|seven|eight) mana was spent to cast it, ", resto)   # 603.4, 601.2h
        resto, se = resto[mm_.end():], {"mana_speso_almeno": numero(mm_.group(1))}
    elif resto.startswith("if ") and AGGANCIO_SE is not None and POSTO is not None and AGGANCIO_SE(POSTO, resto) is not None:
        resto, se = AGGANCIO_SE(POSTO, resto)                                                     # 603.4: il «se» di un set, nel suo posto
    out = []
    for q in trovati:
        c = Contesto(ctx.nome)
        c.evento = q["evento"]                                                                     # per «that many» (14 nov 2026)
        if q["evento"] == "soglia_segnalini": c.ultimo_chi = "fonte"                               # «sacrifice it»: la fonte
        if q["evento"] in ("attacca", "entra", "lascia", "danno_a_giocatore", "danno_ricevuto") and re.match(r"(~|this (creature|land|artifact|enchantment|equipment|vehicle|spacecraft|aura|saga))( |$)", cond):
            c.ultimo_chi = "fonte"                                                                 # «it» = la fonte
        if q["evento"] == "muore" and re.fullmatch(r".*create a token that's a copy of it\.", resto): c.ultimo_chi = "fonte_com_era"   # 603.10a, 608.2h
        if q["evento"] == "una_attacca_sola": c.ultimo_chi = "oggetto_evento"                    # «that creature»
        if q["evento"] == "una_entra" and c.ultimo_chi is None: c.ultimo_chi = "entrata_evento"     # «that creature» entrata (14 nov 2026)
        if q["evento"] == "una_entra" and (q.get("chi") or {}).get("controllo") == "avversario": c.giocatore = "controllore_entrato"
        if q["evento"] == "attivi_fedelta" and q.get("di") == "avversario": c.giocatore = "giocatore_evento"
        if q["evento"] == "una_muore" and (q.get("chi") or {}).get("controllo") == "avversario": c.giocatore = "controllore_morto"
        ab = {"tipo": "innescata", "quando": dict(q)}
        if se: ab["se"] = dict(se)
        if q["evento"] != "muore" and re.search(r"return this card from your graveyard", resto): ab["zona"] = "cimitero"   # 113.6m
        m2 = re.fullmatch(r"choose (one|two|one or both) —", resto.strip())
        if m2: ab["modi_da_leggere"] = "uno_o_piu" if m2.group(1) == "one or both" else numero(m2.group(1))
        else:
            ab["fa"] = frasi(resto, c)
            if c.reqs: ab["bersagli"] = c.reqs
        if una: ab["una_volta_per_turno"] = True
        out.append(ab)
    return out


def costo_attivato(c):
    """«{2}{U}, {T}» -> {"mana", "tappa"}; «Sacrifice this creature» -> sacrifica_se (701.21a)."""
    out, mana = {}, ""
    for parte in [x.strip() for x in c.split(",")]:
        if re.fullmatch(r"(\{[0-9WUBRGCX/]+\})+", parte): mana += parte
        elif parte == "{T}": out["tappa"] = True
        elif parte in ("Sacrifice this creature", "Sacrifice ~", "sacrifice this creature", "Sacrifice this land", "Sacrifice this artifact",
                       "Sacrifice this enchantment", "Sacrifice this token", "Sacrifice this Vehicle"): out["sacrifica_se"] = True   # 701.21a
        elif parte == "Exile this card from your graveyard": out["esilia_se"] = True; out["_zona"] = "cimitero"
        elif parte == "Discard a card": out["scarta_una"] = True
        elif re.fullmatch(r"Pay (\d+) life", parte): out["paga_vite"] = int(parte.split()[1])               # 119.4, 118.3
        elif parte == "Sacrifice another creature": out["sacrifica_altro"] = {"tipi": ["creature"]}            # 701.21a
        elif parte == "Sacrifice a creature": out["sacrifica_un"] = {"tipi": ["creature"]}                   # 701.21a
        elif parte in ("Remove a counter from this creature", "Remove a counter from this artifact"): out["togli_un_segnalino"] = True   # 122.8
        elif parte in ("Remove two counters from this creature", "Remove two counters from this artifact"): out["togli_un_segnalino"] = 2
        elif parte == "Sacrifice this Aura": out["sacrifica_se"] = True                                       # 701.21a
        elif parte == "Sacrifice another creature or artifact": out["sacrifica_altro"] = {"tipi": ["creature", "artifact"]}
        elif parte == "Exile a card from your graveyard":                                                     # 118.3
            out["esilia_altra"] = {"tipi": ["artifact", "battle", "creature", "enchantment", "instant", "kindred", "land", "planeswalker", "sorcery"]}
        elif parte == "Discard a legendary card": out["scarta_una"] = {"leggendaria": True}
        elif parte in ("Exile ~", "Exile this artifact", "Exile this enchantment", "Exile this creature"): out["esilia_questo"] = True
        elif parte == "Tap two untapped artifacts you control": out["tappa_altri"] = {"tipi": ["artifact"], "n": 2}
        elif parte == "Exile another creature card from your graveyard": out["esilia_altra"] = {"tipi": ["creature"]}; out["_zona"] = "cimitero"
        elif parte == "Sacrifice another artifact": out["sacrifica_altro"] = {"tipi": ["artifact"]}
        elif parte == "Sacrifice another creature or planeswalker": out["sacrifica_altro"] = {"tipi": ["creature", "planeswalker"]}
        elif parte == "Sacrifice an artifact or land": out["sacrifica_un"] = {"tipi": ["artifact", "land"]}
        elif parte == "Discard this card": out["scarta_se"] = True; out["_zona"] = "mano"
        elif parte == "Exile this card from your hand": out["esilia_dalla_mano"] = True; out["_zona"] = "mano"   # 113.6m, 118.3
        elif re.fullmatch(r"Sacrifice (a|an|another) (?:artifact|creature|land|enchantment|token|Vehicle)(?:,? or (?:artifact|creature|land|enchantment|token|Vehicle))*", parte):
            mm_ = re.fullmatch(r"Sacrifice (a|an|another) (.+)", parte)                          # 701.21a, 118.3 (14 nov 2026)
            ws_ = re.split(r",? or ", mm_.group(2))
            sel_ = {"tipi": [w for w in ws_ if w in ("artifact", "creature", "land", "enchantment")]}
            if "token" in ws_: sel_["pedina_ok"] = True
            if "Vehicle" in ws_: sel_["sottotipi"] = ["Vehicle"]
            out["sacrifica_altro" if mm_.group(1) == "another" else "sacrifica_un"] = sel_
        elif re.fullmatch(r"Tap (an|another) untapped (creature|artifact|permanent) you control", parte):   # 118.3 (14 nov 2026)
            mm_ = re.fullmatch(r"Tap (an|another) untapped (creature|artifact|permanent) you control", parte)
            tipi_ = ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"] if mm_.group(2) == "permanent" else [mm_.group(2)]
            out["tappa_altri"] = dict({"tipi": tipi_, "n": 1}, **({"altro": True} if mm_.group(1) == "another" else {}))
        elif re.fullmatch(r"Tap (two|three|four|five) (other )?untapped ([A-Za-z]+) you control", parte):   # 118.3, 302.6 (15 nov 2026)
            mm_ = re.fullmatch(r"Tap (two|three|four|five) (other )?untapped ([A-Za-z]+) you control", parte)
            w_ = mm_.group(3).lower()
            if w_ in ("creatures", "artifacts", "lands"): sel_ = {"tipi": [w_[:-1]]}
            elif w_ == "permanents": sel_ = {"tipi": ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"]}
            elif singolare(w_): sel_ = {"tipi": ["creature", "kindred"], "sottotipo": singolare(w_).title()}
            else: raise Mancante(f"costo {parte!r}")
            out["tappa_altri"] = dict(sel_, n=_NUM_PICCOLI[mm_.group(1)], **({"altro": True} if mm_.group(2) else {}))
        elif AGGANCIO_COSTO is not None and POSTO is not None and AGGANCIO_COSTO(POSTO, parte) is not None:
            out.update(AGGANCIO_COSTO(POSTO, parte))                                             # il costo di un set, nel suo posto
        elif re.fullmatch(r"Sacrifice (a|an|another) ([A-Z][a-z]+)", parte) and (parte.split()[-1].lower() in TIPI_CREATURA or parte.split()[-1].lower() in SOTTOTIPI_205):
            mm_ = re.fullmatch(r"Sacrifice (a|an|another) ([A-Z][a-z]+)", parte)                     # 118.3, 701.21a (giro 10): un sottotipo
            out["sacrifica_altro" if mm_.group(1) == "another" else "sacrifica_un"] = {"tipi": [], "sottotipi": [mm_.group(2)]}
        elif re.fullmatch(r"Discard an? (land|creature|artifact|enchantment|instant|sorcery) card", parte):   # 701.9a, 118.3 (giro 10)
            out["scarta_una"] = {"tipi": [re.fullmatch(r"Discard an? ([a-z]+) card", parte).group(1)]}
        elif re.fullmatch(r"Remove (a|an|one|two|three|four|five) (\+1/\+1|charge|wish|film|page|bait|oil|fire|incubation) counters? from (?:this artifact|this creature|~|[A-Z].*)", parte):
            mm_ = re.fullmatch(r"Remove (a|an|one|two|three|four|five) (\S+) counters? from (.+)", parte)   # 122.8, 118.3 (giro 10): un tipo solo
            if mm_.group(3) not in ("this artifact", "this creature", "~") and not mm_.group(3)[0].isupper(): raise Mancante(f"costo {parte!r}")
            out["togli_segnalini_tipo"] = {"tipo": "carica" if mm_.group(2) == "charge" else mm_.group(2), "n": numero(mm_.group(1))}
        elif re.fullmatch(r"Exile an? (artifact|creature|land|enchantment|instant or sorcery|instant|sorcery) card from your graveyard", parte):
            mm_ = re.fullmatch(r"Exile an? (.+) card from your graveyard", parte)                  # 118.3, 601.2h (15 nov 2026): un'altra
            out["esilia_altra"] = {"tipi": mm_.group(1).split(" or ")}                             # carta (la fonte e' in campo)
        else: raise Mancante(f"costo {parte!r}")
    if mana: out["mana"] = mana
    return out


def attivata(p_orig, p, ctx):
    m = re.fullmatch(r"([+-]?\d+|[+-]x): (.+)", p)
    solo_jace = None
    if m and m.group(2).endswith(" activate only if there are twenty-five or more loyalty counters among jaces you control."):
        solo_jace = 25                                                                           # 602.5b
        m = re.fullmatch(r"([+-]?\d+|[+-]x): (.+)", p[: -len(" activate only if there are twenty-five or more loyalty counters among jaces you control.")])
    if m:
        c = Contesto(ctx.nome)
        if "x" in m.group(1):
            if m.group(1) != "-x": raise Mancante("fedelta' +X")
            c.x_costo = True                                                                     # 107.3k: la X la sceglie chi attiva
            ab = {"tipo": "attivata", "fedelta": "-X", "fa": frasi(m.group(2), c)}
        else: ab = {"tipo": "attivata", "fedelta": int(m.group(1)), "fa": frasi(m.group(2), c)}
        if solo_jace: ab["solo_se"] = {"fedelta_jace_almeno": solo_jace}
        if c.reqs: ab["bersagli"] = c.reqs
        return [ab]
    m = re.fullmatch(r"((?:exhaust — )?\{[^:]+?|sacrifice this creature|sacrifice this enchantment|sacrifice this artifact|sacrifice another creature or planeswalker|"
                     r"tap two untapped artifacts you control): (.+)", p_orig_low(p_orig, p))                     # (14 nov 2026: «this enchantment/artifact»)
    if not m and AGGANCIO_COSTO is not None and POSTO is not None and ":" in p_orig:                # un costo di un set in testa
        primo = re.sub(r"^Exhaust — ", "", p_orig.split(":")[0]).split(", ")[0]                       # («Waterbend {3}: ...»)
        if AGGANCIO_COSTO(POSTO, primo) is not None: m = re.fullmatch(r"((?:exhaust — )?[^:]+?): (.+)", p)
    if not m and ":" in p_orig and not re.match(r"(when|whenever|at) ", p):                       # 602.1 (15 nov 2026): l'ultimo tentativo,
        try:                                                                                     # ogni costo che costo_attivato legge
            c_ = costo_attivato(p_orig.split(":")[0].replace(ctx.nome, "~"))
            if not c_.get("_zona"): m = re.fullmatch(r"([^:]+?): (.+)", p)
        except Mancante: pass
    if not m: return None
    costo_txt = p_orig.split(":")[0]
    esaurisci = costo_txt.startswith("Exhaust — ")                                                 # 702.177a
    if esaurisci: costo_txt = costo_txt[len("Exhaust — "):]
    costo_txt = re.sub(r"^[A-Z][a-z]+ — ", "", costo_txt)                                          # 207.2c: la parola d'abilita' («Threshold —»)
    m_n = re.match(r"^([A-Z][A-Za-z'’!,.-]*(?: [A-Za-z'’!,.-]+){0,4}) — (?=\{|[A-Z])", costo_txt)   # 207.2c-d (15 nov 2026): una parola
    if m_n and (m_n.group(1).lower() in PAROLE_ABILITA or m_n.group(1).lower() not in PAROLE_CHIAVE):    # d'abilita' di piu' parole o una
        costo_txt = costo_txt[m_n.end():]                                                          # flavor word davanti al costo
    eff = m.group(2)
    if eff in ("add {r} or {w}.", "add one mana of any color.") or re.fullmatch(r"add ((?:\{[wubrgc]\})+)( or (\{[wubrgc]\}))?\.", eff):
        return "mana"
    vel = "istantanea"
    solo_se = {}
    if eff.endswith(" activate only as a sorcery."): eff, vel = eff[: -len(" activate only as a sorcery.")], "stregoneria"
    una_per_turno = False                                                                        # 602.5b (14 nov 2026)
    for coda in (" activate only once each turn.", " activate only during your turn and only once each turn.",
                 " activate only as a sorcery and only once each turn."):
        if eff.endswith(coda):
            eff, una_per_turno = eff[: -len(coda)], True
            if "during your turn" in coda: solo_se["tuo_turno"] = True
            if "as a sorcery" in coda: vel = "stregoneria"
    if eff.endswith(" activate only if you've cast an instant or sorcery spell this turn."):
        eff = eff[: -len(" activate only if you've cast an instant or sorcery spell this turn.")]; solo_se["istantaneo_o_stregoneria_turno"] = True
    for coda, k_ in ((" activate only during your turn.", "tuo_turno"),
                     (" activate only if an opponent has been dealt noncombat damage this turn.", "avversario_danno_nc_turno"),
                     (" activate only if you've scried or surveilled this turn.", "guardato_turno"),
                     (" activate only if there are seven or more cards in your graveyard.", "cimitero_almeno")):
        if eff.endswith(coda): eff, solo_se[k_] = eff[: -len(coda)], (7 if k_ == "cimitero_almeno" else True)   # 602.5b
    una_sola = False
    if eff.endswith(" activate only once."): eff, una_sola = eff[: -len(" activate only once.")], True   # 602.5b (14 nov 2026)
    m_se = re.fullmatch(r"(.+?) activate only if ([^.]+)\.", eff)
    if m_se and "activate only" not in m_se.group(1):                                            # 602.5b, 611.3a (14 nov 2026): la
        cs_ = cond_statica(m_se.group(2))                                                         # condizione si guarda quando si attiva
        if cs_ is not None: eff, solo_se["statica"] = m_se.group(1), cs_
    rid_ = None                                                                                  # 601.2f, 602.2b, 118.7 (giro 13):
    m_r = re.fullmatch(r"(.+?) this ability costs \{(\d|x)\} less to activate(?:, where x is ([^.]+)| for each ([^.]+)| if ([^.]+))\.", eff)
    if m_r:                                                                                      # la riduzione si conta quando si attiva
        if m_r.group(2) == "x" and m_r.group(3):
            try: rid_ = {"quanto": quantita(m_r.group(3), Contesto(ctx.nome)), "n": 1}
            except Mancante: rid_ = None
        elif m_r.group(2) != "x" and m_r.group(4):
            q_ = conta_per_ogni(m_r.group(4).replace("this artifact", "~").replace("this creature", "~"), Contesto(ctx.nome))
            if q_ is None and re.fullmatch(r"(\w+) counter on (?:this artifact|this creature|~)", m_r.group(4)):
                q_ = {"tipo": "segnalini_fonte", "segnalino": m_r.group(4).split(" counter")[0]}
            if q_ is not None: rid_ = {"quanto": q_, "n": int(m_r.group(2))}
        elif m_r.group(2) != "x" and m_r.group(5):
            cs_ = cond_statica(m_r.group(5))
            if cs_ is not None: rid_ = {"se": cs_, "n": int(m_r.group(2))}
        if rid_ is not None: eff = m_r.group(1)
    if "activate only" in eff: raise Mancante("restrizione di attivazione")
    c = Contesto(ctx.nome)
    corto_ = ctx.nome.split(",")[0]
    costo_txt_ = costo_txt.replace(ctx.nome, "~")
    if corto_ != ctx.nome and len(corto_) > 2: costo_txt_ = re.sub(r"\bSacrifice " + re.escape(corto_) + r"\b", "Sacrifice ~", costo_txt_)   # il nome corto
    costo = costo_attivato(costo_txt_)
    lki_ = costo.get("sacrifica_se") and eff.startswith("it deals damage equal to its power to ")   # 113.7a, 608.2h (14 nov 2026):
    if lki_: eff = "~" + eff[2:]                                                                   # «it» e' la fonte sacrificata
    ab = {"tipo": "attivata", "costo": costo, "velocita": vel, "fa": frasi(eff, c)}
    if lki_: ab["fa"] = [dict(d, lki=True, chi=["fonte_com_era"] + list(d["chi"][1:])) if d.get("fa") == "danno_forza" and d["chi"][0] == "fonte" else d
                         for d in ab["fa"]]
    if rid_ is not None:
        if not costo.get("mana"): raise Mancante("riduzione senza costo di mana")
        ab["riduzione"] = rid_
    if esaurisci: ab["esaurisci"] = True
    if una_per_turno: ab["una_per_turno"] = True
    if una_sola: ab["una_sola_volta"] = True
    if solo_se: ab["solo_se"] = solo_se
    zona = costo.pop("_zona", None)
    if "from your graveyard to" in eff and "return this card" in eff: zona = "cimitero"            # «return this card from your graveyard»
    if zona: ab["zona"] = zona                                                                   # 113.6
    if c.reqs: ab["bersagli"] = c.reqs
    elif any(d.get("fa") == "aggiungi_mana" for d in ab["fa"]): ab["di_mana"] = True             # 605.1a: senza bersagli, non di fedelta' 
    return [ab]


def p_orig_low(p_orig, p):
    return p


COSTI = [
    (r"noncreature spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "non_tipi": ["creature"], "delta": -n}),
    (r"noncreature spells your opponents cast cost \{(\d)\} more to cast\.", lambda n: {"tipo": "costi", "di": "avversario", "non_tipi": ["creature"], "delta": n}),
    (r"planeswalker spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "tipi": ["planeswalker"], "delta": -n}),
    (r"instant and sorcery spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "tipi": ["instant", "sorcery"], "delta": -n}),
    (r"spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "delta": -n}),          # 601.2f (14 nov 2026)
    (r"creature spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "tipi": ["creature"], "delta": -n}),
    (r"artifact spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "tipi": ["artifact"], "delta": -n}),
    (r"enchantment spells you cast cost \{(\d)\} less to cast\.", lambda n: {"tipo": "costi", "di": "tuo", "tipi": ["enchantment"], "delta": -n}),
]


def _equipaggiata(p):
    """301.5, 613.4c, 613.1f: «Equipped creature gets +P/+T and has flying and ward {1}» (14 nov 2026)."""
    m = re.fullmatch(r"equipped creature gets " + PT + r" and has ([a-z ,]+?)(?:,? and ward \{(\d+)\})?\.", p)
    if not m: return None
    parole_ = parole_lista(m.group(3))
    if not all(x in PAROLE_SEMPLICI for x in parole_): return None
    sel = {"attaccata": True}
    eff = [{"livello": "7c", "chi": sel, "p": int(m.group(1)), "t": int(m.group(2))}, {"livello": "6", "chi": sel, "dai": parole_}]
    if m.group(4): return None                                                                   # ward dato: resta mancante
    return [{"tipo": "statica", "effetti": eff}]


def attaccata_generica(p):
    """301.5, 303.4b, 613.1d-f (14 nov 2026): «Equipped creature gets +P/+T, has K and "...", and is a T in addition to its
    other types.»: le parti in qualunque ordine; l'abilita' tra virgolette letta come il testo di una piccola carta
    («this creature» e' la creatura che la riceve, 113.1a)."""
    m = re.fullmatch(r"(equipped|enchanted) creature (.+)\.", p)
    if not m: return None
    citate = []
    def metti(mm): citate.append(mm.group(1).rstrip(",. ") + "."); return f"«{len(citate) - 1}»"
    resto = re.sub(r'"(.+?)"', metti, m.group(2))
    parti = re.findall(r"(gets|has|is an?) (.+?)(?=(?:,? and |, )(?:gets |has |is an? )|$)", resto)
    if not parti: return None
    ricostruito = re.sub(r"(?:,? and |, )(?=gets |has |is an? )", "|", resto)
    if ricostruito.split("|") != [a + " " + b for a, b in parti]: return None                  # nessun pezzo lasciato fuori
    sel, eff = {"attaccata": True}, []
    for verbo, x in parti:
        if verbo == "gets":
            mp = re.fullmatch(PT, x)
            if not mp or "X" in x: return None
            eff.append({"livello": "7c", "chi": sel, "p": int(mp.group(1)), "t": int(mp.group(2))})
        elif verbo == "has":
            voci = [v.strip() for v in re.split(r",? and |, ", x) if v.strip()]
            semplici = []
            for v in voci:
                if re.fullmatch(r"«\d+»", v): continue
                try: semplici += parole_lista(v)
                except Mancante: return None
            if not all(v in PAROLE_SEMPLICI for v in semplici): return None
            if semplici: eff.append({"livello": "6", "chi": sel, "dai": semplici})
            for v in voci:
                mq = re.fullmatch(r"«(\d+)»", v)
                if not mq: continue
                try: pz = abilita_pedina(citate[int(mq.group(1))], "Creature")
                except Mancante: return None
                if pz.get("car_extra"): return None
                if pz["abilita"]: eff.append({"livello": "6", "chi": sel, "dai_abilita": pz["abilita"]})
                if pz.get("parole_extra"): eff.append({"livello": "6", "chi": sel, "dai": pz["parole_extra"]})
        else:
            mt = re.fullmatch(r"([a-z]+) in addition to its other types", x)
            if not mt or mt.group(1) not in TIPI_CREATURA: return None
            eff.append({"livello": "4", "chi": sel, "sottotipi": [mt.group(1).capitalize()]})
    return [{"tipo": "statica", "effetti": eff}] if eff else None


SEGNALINI_PAROLA = ("flying", "first strike", "double strike", "deathtouch", "haste", "hexproof", "indestructible", "lifelink",
                    "menace", "reach", "trample", "vigilance")                                    # 122.1b (quelle che il motore conosce)


def kicker(p):
    """702.33a (14 nov 2026): «Kicker [cost]» = «You may pay an additional [cost] as you cast this spell.» -> il costo facoltativo.
    Anche «As an additional cost to cast this spell, you may [cost].» (601.2b): lo stesso costo facoltativo."""
    m = re.fullmatch(r"as an additional cost to cast this spell, you may (.+?)\.?", p)
    if m:
        ca = costo_aggiuntivo("as an additional cost to cast this spell, " + m.group(1) + ".")
        return dict(ca[0], nome="aggiuntivo") if ca and len(ca) == 1 else None
    m = re.fullmatch(r"kicker ((?:\{[0-9wubrgcx/]+\})+)", p)
    if m: return {"nome": "kicker", "mana": m.group(1).upper()}
    m = re.fullmatch(r"kicker—(.+?)\.?", p)
    if m:
        ca = costo_aggiuntivo("as an additional cost to cast this spell, " + m.group(1) + ".")
        if ca and len(ca) == 1: return dict(ca[0], nome="kicker")
    return None


def costo_aggiuntivo(p):
    """601.2b, 601.2f, 601.2h (14 nov 2026): «As an additional cost to cast this spell, A [or B].» -> la lista delle opzioni,
    o None. Un'opzione sola e' obbligatoria. Il mana colorato in piu' resta mancante (il nucleo somma solo il generico)."""
    m = re.fullmatch(r"as an additional cost to cast this spell, (.+?)\.", p)
    if not m: return None
    parti = re.split(r" or (?=sacrifice|discard|pay|behold|blight)", m.group(1))
    out = []
    for x in parti:
        mm = re.fullmatch(r"sacrifice an? (creature|artifact|artifact or creature|creature or planeswalker)", x)
        if mm: out.append({"sacrifica": mm.group(1).split(" or ")}); continue
        if x == "discard a card": out.append({"scarta": 1}); continue
        mm = re.fullmatch(r"pay (\d+) life", x)
        if mm: out.append({"vite": int(mm.group(1))}); continue
        mm = re.fullmatch(r"pay (\{\d+\})", x)
        if mm: out.append({"mana": mm.group(1)}); continue
        mm = re.fullmatch(r"behold an? ([a-z]+)", x)
        if mm and mm.group(1) in TIPI_CREATURA: out.append({"behold": mm.group(1).title()}); continue
        if AGGANCIO_COSTO is not None and POSTO is not None and AGGANCIO_COSTO(POSTO, x[:1].upper() + x[1:]) is not None:
            out.append(AGGANCIO_COSTO(POSTO, x[:1].upper() + x[1:])); continue                    # un costo di un set (701.68a: blight)
        return None
    return out or None


def cond_controlli(s):
    """«a creature with power 4 or greater», «two or more tapped creatures», «another Elf», «an artifact» -> {sel, n} o None."""
    quanti = {"a": 1, "an": 1, "another": 1, "two or more": 2, "three or more": 3, "four or more": 4, "five or more": 5,
              "six or more": 6, "seven or more": 7}
    m = re.fullmatch(r"(a|an|another|(?:two|three|four|five|six|seven) or more) (other )?(tapped )?([a-z]+?)(?:s)?( with power (\d+) or greater)?", s)
    if not m: return None
    w, sel = m.group(4), {}
    if m.group(1) == "another" or m.group(2): sel["altre"] = True
    if m.group(3): sel["tappata"] = True
    if w in ("creature", "artifact", "enchantment", "land", "planeswalker"): sel["tipi"] = [w]
    elif w in ("equipment", "vehicle", "treasure", "food", "clue") or w in TIPI_CREATURA or (w.endswith("e") and w[:-1] in TIPI_CREATURA): sel["sottotipo"] = w.title()
    else: return None
    if m.group(6): sel["forza_min"] = int(m.group(6)); sel.setdefault("tipi", ["creature"])
    return {"sel": sel, "n": quanti[m.group(1)]}


def cond_statica(s):
    """611.3a: la condizione di «as long as ...» di una statica -> dict per condizione_statica, o None (14 nov 2026)."""
    m = re.fullmatch(r"you control an? (artifact|creature|enchantment|land|planeswalker)", s)
    if m: return {"controlli": {"tipi": [m.group(1)]}}
    m = re.fullmatch(r"you control an? ([a-z]+)", s)
    if m and m.group(1) in TIPI_CREATURA: return {"controlli": {"sottotipo": m.group(1).title()}}
    m = re.fullmatch(r"you control (two|three|four|five|six|seven|eight) or more (artifacts|lands|creatures|enchantments)", s)
    if m:
        n = numero(m.group(1)) if m.group(1) in NUMERI else {"five": 5, "six": 6, "seven": 7, "eight": 8}[m.group(1)]
        return {"controlli_almeno": {"sel": {"tipi": [m.group(2)[:-1]]}, "n": n}}
    m = re.fullmatch(r"you've cast (two|three) or more spells this turn", s)
    if m: return {"lanciate_turno_almeno": numero(m.group(1))}
    m = re.fullmatch(r"you have (\d+) or more life", s)
    if m: return {"vite_almeno": int(m.group(1))}
    m = re.fullmatch(r"there are (two|three|four) or more (instant and/or sorcery|creature|land) cards in your graveyard", s)
    if m: return {"cimitero_tipi_almeno": {"tipi": m.group(2).split(" and/or "), "n": numero(m.group(1))}}
    m = re.fullmatch(r"you've drawn (two|three) or more cards this turn", s)
    if m: return {"pescate_turno_almeno": numero(m.group(1))}
    if s == "a creature died this turn": return {"morta_turno": True}                             # 700.4 (15 nov 2026)
    if s == "an opponent lost life this turn": return {"avversario_perso_turno": True}              # 119.3
    if s == "you gained life this turn": return {"guadagnato_turno": True}                         # 119.3
    if s == "you've cast a noncreature spell this turn": return {"noncreatura_turno": True}        # 601.2i
    if s == "you control a creature with a counter on it": return {"controlli": {"tipi": ["creature"], "con_segnalini": True}}   # 122.1
    if s == "you control a permanent with a counter on it": return {"controlli": {"tipi": ["permanent"], "con_segnalini": True}}
    m = re.fullmatch(r"you control an? ([a-z]+)", s)
    if m and m.group(1) in SOTTOTIPI_205: return {"controlli": {"tipi": ["permanent"], "sottotipo": m.group(1).title()}}   # 205.3g-k
    m = re.fullmatch(r"you control an? (creature|artifact creature) with (power|toughness) (\d+) or greater", s)   # 208.1 (14 nov 2026)
    if m: return {"controlli": {"tipi": ["creature"], ("forza_min" if m.group(2) == "power" else "costituzione_min"): int(m.group(3)),
                                **({"anche_tipo": "artifact"} if m.group(1) == "artifact creature" else {})}}
    m = re.fullmatch(r"you have (two|three|four|five|six|seven|eight) or more cards in (?:your )?hand", s)
    if m: return {"mano_almeno": {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}[m.group(1)]}   # 402.1
    m = re.fullmatch(r"you control (two|three|four|five|six|seven|eight) or more differently named lands", s)
    if m: return {"terre_nomi_almeno": {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}[m.group(1)]}   # 201.2
    m = re.fullmatch(r"there is an? ([a-z]+) card in your graveyard", s)
    if m and (m.group(1) in TIPI_FILTRO - {"permanent"}): return {"cimitero_tipi_almeno": {"tipi": [m.group(1)], "n": 1}}
    if m and m.group(1) in TIPI_CREATURA: return {"cimitero_tipi_almeno": {"tipi": ["creature", "kindred"], "sottotipo": m.group(1).title(), "n": 1}}
    # 15 nov 2026: le condizioni generali dell'ultimo giro delle statiche
    m = re.fullmatch(r"there(?:'s| is) an? ([a-z]+) card in your graveyard", s)
    if m and m.group(1) in SOTTOTIPI_205 and m.group(1) not in TIPI_FILTRO:                         # 205.3k: «a Lesson card»
        return {"cimitero_tipi_almeno": {"tipi": list(TIPI_CARTA_TUTTI), "sottotipo": m.group(1).title(), "n": 1}}
    if m: return cond_statica("there is a " + m.group(1) + " card in your graveyard") if s.startswith("there's") else None
    m = re.fullmatch(r"there are (two|three|four|five|six|seven) or more ([a-z]+) cards in your graveyard", s)
    if m and m.group(2) in SOTTOTIPI_205 and m.group(2) not in TIPI_FILTRO:
        return {"cimitero_tipi_almeno": {"tipi": list(TIPI_CARTA_TUTTI), "sottotipo": m.group(2).title(), "n": _NUM_PICCOLI[m.group(1)]}}
    m = re.fullmatch(r"there are (two|three|four|five|six|seven) or more cards in your graveyard", s)
    if m: return {"cimitero_almeno": _NUM_PICCOLI[m.group(1)]}                                     # 404.1
    m = re.fullmatch(r"an opponent has (\d+) or less life", s)
    if m: return {"avversario_vite_max": int(m.group(1))}                                           # 119.1
    m = re.fullmatch(r"you have (no|one or fewer|two or fewer) cards in hand", s)
    if m: return {"mano_max": {"no": 0, "one or fewer": 1, "two or fewer": 2}[m.group(1)]}            # 402.1
    if s in ("~ is attacking", "this creature is attacking"): return {"fonte_attacca": True}   # 506.4
    if s in ("~ is equipped", "this creature is equipped"): return {"fonte_equipaggiata": True}   # 301.5
    if s in ("~ is modified", "this creature is modified"): return {"fonte_modificata": True}     # 700.9
    if s in ("this creature has a counter on it", "~ has a counter on it"): return {"fonte_con_segnalini": True}   # 122.1
    m = re.fullmatch(r"(?:this creature|~) has (one|two|three|four|five) or more \+1/\+1 counters on it", s)
    if m: return {"segnalini_almeno": {"tipo": "+1/+1", "n": _NUM_PICCOLI[m.group(1)]}}           # 122.1a
    if s in ("~ attacked this turn", "this creature attacked this turn"): return {"fonte_ha_attaccato": True}   # 508.1
    if s in ("~ hasn't dealt damage yet", "this creature hasn't dealt damage yet"):
        return {"senza_danno": True}                                                               # 120.1
    m = re.fullmatch(r"you control another ([a-z]+)", s)
    if m and m.group(1) in TIPI_CREATURA: return {"controlli": {"sottotipo": m.group(1).title(), "altre": True}}
    if m and m.group(1) in ("creature", "artifact", "enchantment", "land", "planeswalker"):
        return {"controlli": {"tipi": [m.group(1)], "altre": True}}
    m = re.fullmatch(r"(another|an?) (creature|artifact|land|enchantment) entered the battlefield under your control this turn", s)
    if m: return {"entrata_tua_turno": {"tipi": [m.group(2)], "altra": m.group(1) == "another"}}   # 603.6a, 110.2
    if s == "an opponent controls more lands than you": return {"avversario_piu_terre": True}      # 305 (15 nov 2026)
    if s == "you attacked this turn": return {"attaccato_turno": True}                             # 508.1 (giro 8)
    if s in ("it's your turn",): return {"tuo_turno": True}                                         # 500.1 (giro 9)
    m = re.fullmatch(r"you control (two|three|four|five|six|seven|eight) or more creatures", s)
    if m: return {"controlli_almeno": {"sel": {"tipi": ["creature"]}, "n": _NUM_PICCOLI.get(m.group(1)) or {"eight": 8}[m.group(1)]}}
    if s == "a permanent left the battlefield under your control this turn": return {"lasciato_tuo_turno": True}   # 603.6c
    m = re.fullmatch(r"creatures you control have total (power|toughness) (\d+) or greater", s)       # 208.1 (15 nov 2026)
    if m: return {"totale_fc_almeno": {"quale": "forza" if m.group(1) == "power" else "costituzione", "n": int(m.group(2))}}
    m = re.fullmatch(r"(two|three|four) or more (creatures|artifacts|lands) entered the battlefield under your control this turn", s)
    if m: return {"entrate_tue_turno_almeno": {"tipi": [m.group(2)[:-1]], "n": _NUM_PICCOLI[m.group(1)]}}   # 603.6a, 110.2 (giro 7)
    if s == "you've cast another instant or sorcery spell this turn":                              # 601.2i: questa compresa
        return {"lanciate_tipo_turno_almeno": {"tipi": ["instant", "sorcery"], "n": 2}}
    m = re.fullmatch(r"you've gained (\d+) or more life this turn", s)
    if m: return {"guadagnato_turno_almeno": int(m.group(1))}                                      # 119.3
    m = re.fullmatch(r"you've cast a spell with mana value (\d+) or greater this turn", s)
    if m: return {"lanciata_mv_turno": int(m.group(1))}                                            # 601.2i, 202.3
    m = re.fullmatch(r"you control (two|three|four|five) or more other ([a-z]+)", s)                 # 205.3m (giro 11)
    if m and singolare(m.group(2)) and singolare(m.group(2)) in TIPI_CREATURA:
        return {"controlli_almeno": {"sel": {"sottotipo": singolare(m.group(2)).title(), "altre": True}, "n": _NUM_PICCOLI[m.group(1)]}}
    m = re.fullmatch(r"you control (two|three|four|five) or more attacking creatures", s)
    if m: return {"controlli_almeno": {"sel": {"tipi": ["creature"], "attaccante": True}, "n": _NUM_PICCOLI[m.group(1)]}}   # 506.4
    if AGGANCIO_SE_STATICA is not None and POSTO is not None: return AGGANCIO_SE_STATICA(POSTO, s)   # la condizione di un set
    return None


_N_MANO = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM_PICCOLI = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
TIPI_CARTA_TUTTI = ("artifact", "battle", "creature", "enchantment", "instant", "kindred", "land", "planeswalker", "sorcery")   # 205.2a


def _statica_condizionata(p):
    """611.3a: «As long as COND, this creature gets +P/+T and has KW» e «This creature gets +P/+T as long as COND»."""
    corpo = r"(?:~|this creature) (?:gets \+(\d+)/\+(\d+)(?: and has ([a-z ,]+?))?|has ([a-z ,]+?))"
    m = re.fullmatch(r"as long as (.+?), " + corpo + r"\.", p)
    if m: cond_txt, gp, gt, kw1, kw2 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    else:
        m = re.fullmatch(corpo + r" as long as (.+?)\.", p)
        if not m: return None
        gp, gt, kw1, kw2, cond_txt = m.groups()
    se = cond_statica(cond_txt)
    if se is None: return None
    kw = kw1 or kw2
    if kw and not all(x in PAROLE_SEMPLICI for x in parole_lista(kw)): return None
    sel, eff = {"se_stessa": True}, []
    if gp is not None: eff.append({"livello": "7c", "chi": sel, "p": int(gp), "t": int(gt), "se": se})
    if kw: eff.append({"livello": "6", "chi": sel, "dai": parole_lista(kw), "se": se})
    return [{"tipo": "statica", "effetti": eff}]


def _soggetto_statica(s):
    """Il soggetto di un'abilita' statica (613.1, 611.3) -> (selettore, plurale) o None (15 nov 2026)."""
    if s in ("~", "this creature"): return {"se_stessa": True}, False
    if s in ("equipped creature", "enchanted creature", "enchanted permanent", "enchanted land", "enchanted artifact"):
        return {"attaccata": True}, False                                                          # 301.5, 303.4b
    m = re.fullmatch(r"(other )?(tapped |untapped )?(attacking )?(artifact )?(creatures|permanents|creature tokens|tokens)"
                     r" you control( with \+1/\+1 counters on them)?", s)
    if m and m.group(2) != "untapped ":
        sel = {"tipi": ["permanent" if m.group(5) in ("permanents", "tokens") else "creature"], "controllo": "tuo"}
        if m.group(1): sel["altre"] = True
        if m.group(2): sel["tappata"] = True
        if m.group(3): sel["attaccante"] = True                                                    # 506.4
        if m.group(4): sel["anche_tipo"] = "artifact"
        if "tokens" in m.group(5): sel["pedina"] = True                                            # 111.1
        if m.group(6): sel["con_segnalino"] = "+1/+1"                                              # 122.1a
        return sel, True
    m = re.fullmatch(r"(other )?([a-z]+?)(?: creatures)? you control", s)
    if m and singolare(m.group(2)):                                                              # 205.3m
        sel = {"tipi": ["creature"], "controllo": "tuo", "sottotipo": singolare(m.group(2)).title()}
        if m.group(1): sel["altre"] = True
        return sel, True
    if s == "all creatures": return {"tipi": ["creature"]}, True                                   # 611.3a (giro 8): tutte, di tutti
    m = re.fullmatch(r"(other )?land creatures you control", s)                                    # «land creatures»: creature che sono terre
    if m: return dict({"tipi": ["creature"], "controllo": "tuo", "anche_tipo": "land"}, **({"altre": True} if m.group(1) else {})), True
    m = re.fullmatch(r"(other )?([a-z]+)s you control", s)                                         # «Vehicles you control»: un sottotipo di
    if m and m.group(2) in SOTTOTIPI_205 and m.group(2) not in TIPI_CREATURA:                       # artefatto, incantesimo o terra (205.3g-i)
        return dict({"tipi": ["permanent"], "controllo": "tuo", "sottotipo": m.group(2).title()}, **({"altre": True} if m.group(1) else {})), True
    if re.search(r"\b(?:you control|your opponents control)(?: with (?:one or more )?counters on them)?$", s) and not re.match(r"(?:each|all) ", s):   # 15 nov 2026: i gruppi
        sel = selettore_esteso(s)                                                                   # che selettore_esteso legge («nonland
        if sel is not None and "creature" in sel.get("tipi", []) + ["creature"]: return sel, True   # permanents», «attacking Elves»...)
    return None


def statica_generica(p):
    """611.3a, 613.4c, 613.1f, 613.11 (15 nov 2026): l'ultimo tentativo per un'abilita' statica, a pezzi: la condizione
    («during your turn, X», «as long as COND, X», «X as long as COND», letta con cond_statica), il soggetto (questa creatura,
    la creatura equipaggiata o incantata, le creature che controlli coi loro filtri) e i predicati in qualunque ordine
    («gets +P/+T», «has K», «can't block», «can't attack [or block]», «loses all abilities»). Un pezzo che non si legge:
    None (resta mancante). Solo come ultimo tentativo: una lettura gia' fatta non cambia. I cambi di tipo (livello 4) con
    una condizione o su un insieme non sono coperti dal motore (613.1d): qui non entrano."""
    s = p.rstrip(".")
    se = {}
    m = re.fullmatch(r"during your turn, (.+)", s)
    if m: se["tuo_turno"], s = True, m.group(1)
    def cond_(c):                                                                                # «it» nella condizione di una statica
        if re.search(r"(?:^|, )(?:~|this creature) (?:gets|has|can't|loses) ", s): c = re.sub(r"^it's ", "this creature is ", re.sub(r"^it (?=has |attacked |hasn't )", "this creature ", c))
        return cond_statica(c)
    m = re.fullmatch(r"as long as ([^,]+), (.+)", s)
    if m:
        c_ = cond_(m.group(1))
        if c_ is None: return None
        se.update(c_); s = m.group(2)
    else:
        m = re.fullmatch(r"(.+?) as long as (.+)", s)
        if m:
            s = m.group(1)
            c_ = cond_(m.group(2))
            if c_ is None: return None
            se.update(c_)
        else:
            m = re.fullmatch(r"(.+? can't be blocked) if (.+)", s)                               # 611.3a (giro 8): «can't be blocked if
            if m:                                                                                  # you've cast two or more spells this turn»
                c_ = cond_(m.group(2))
                if c_ is None: return None
                se.update(c_); s = m.group(1)
    m = re.fullmatch(r"(.+?) (gets|get|has|have|can't|loses|lose|is) (.+)", s)
    if not m: return None
    sog = _soggetto_statica(m.group(1))
    if sog is None: return None
    sel, plur = sog
    resto = m.group(2) + " " + m.group(3)
    V = r"(?:gets|get|has|have|can't|loses|lose|is) "
    parti = re.findall(r"(gets|get|has|have|can't|loses|lose|is) (.+?)(?=(?:,? and |, )" + V + r"|$)", resto)
    if not parti: return None
    if re.sub(r"(?:,? and |, )(?=" + V + ")", "|", resto).split("|") != [a + " " + b for a, b in parti]: return None
    eff = []
    for verbo, x in parti:
        if verbo in ("gets", "has", "loses", "is") and plur: return None                              # l'accordo del verbo
        if verbo == "is":                                                                          # 205.1b, 613.1d (giro 11): il tipo
            if se or set(sel) - {"attaccata", "se_stessa"}: return None                             # aggiunto, solo alla creatura stessa o a
            if x == "all creature types": eff.append({"livello": "4", "chi": sel, "tutti_tipi": True}); continue   # quella attaccata (205.3m)
            mt = re.fullmatch(r"an? ([a-z ]+?) in addition to its other types", x)
            if not mt or not all(w in TIPI_CREATURA for w in mt.group(1).split()): return None
            eff.append({"livello": "4", "chi": sel, "sottotipi": [w.capitalize() for w in mt.group(1).split()]})
            continue
        if verbo in ("get", "have", "lose") and not plur: return None
        if verbo in ("gets", "get"):
            mf = re.fullmatch(r"\+(\d+)/\+(\d+) for each (.+)", x)                                  # 611.3a (15 nov 2026): «gets +1/+1 for
            if mf:                                                                                 # each Forest you control», contata ogni volta
                sp_ = conta_per_ogni(mf.group(3), Contesto("~"))
                if sp_ and sp_["tipo"] == "campo_sel" and sp_["sel"].get("controllo") == "tuo": sp_ = {"tipo": "controlli", "sel": sp_["sel"]}
                if not sp_ or sp_["tipo"] != "controlli" or set(sp_["sel"]) - {"controllo", "tipi", "sottotipo"} or sp_["sel"].get("controllo") != "tuo":
                    return None
                eff.append({"livello": "7c", "chi": sel, "p": {"conta": sp_, "molt": int(mf.group(1))} if int(mf.group(1)) else 0,
                            "t": {"conta": sp_, "molt": int(mf.group(2))} if int(mf.group(2)) else 0})
                continue
            mp = re.fullmatch(PT, x)
            if not mp or "X" in x: return None
            eff.append({"livello": "7c", "chi": sel, "p": int(mp.group(1)), "t": int(mp.group(2))})
        elif verbo in ("has", "have"):
            try: kw = parole_lista(x)
            except Mancante: return None
            eff.append({"livello": "6", "chi": sel, "dai": kw})
        elif verbo in ("loses", "lose"):
            if x != "all abilities": return None
            eff.append({"livello": "6", "chi": sel, "toglie": "tutte"})                           # 613.1f
        elif x == "be blocked":                                                                   # 509.1b, 613.11 (giro 8)
            eff.append({"livello": "regola", "chi": sel, "non_bloccabile": True})
        elif x == "be blocked by more than one creature":                                         # 509.1b (giro 11)
            eff.append({"livello": "regola", "chi": sel, "max_un_bloccante": True})
        elif re.fullmatch(r"be blocked except by (two|three|four) or more creatures", x):          # 509.1b
            eff.append({"livello": "regola", "chi": sel, "min_bloccanti": _NUM_PICCOLI[x.split()[4]]})
        elif x == "be blocked by tokens":                                                         # 509.1b, 111.1
            eff.append({"livello": "regola", "chi": sel, "non_bloccata_da_pedine": True})
        elif x == "be blocked by creatures with greater power":                                   # 509.1b, 208.1
            eff.append({"livello": "regola", "chi": sel, "non_bloccata_da_piu_forti": True})
        elif re.fullmatch(r"be blocked by creatures with power (\d+) or less", x):
            eff.append({"livello": "regola", "chi": sel, "non_bloccata_da_forza_max": int(x.split()[-3])})
        elif x == "attack alone":                                                                 # 506.5, 508.1c
            eff.append({"livello": "regola", "chi": sel, "non_attacca_da_sola": True})
        elif re.fullmatch(r"(attack or block|attack|block) unless (.+)", x):                       # 508.1c, 509.1b: «unless COND»
            mu_ = re.fullmatch(r"(attack or block|attack|block) unless (.+)", x)
            c_ = cond_(mu_.group(2))
            if c_ is None: return None
            d = {"livello": "regola", "chi": sel, "se": {"non": c_}}
            if "attack" in mu_.group(1): d["non_attacca"] = True
            if "block" in mu_.group(1): d["non_blocca"] = True
            eff.append(d)
        else:
            if x not in ("block", "attack", "attack or block"): return None
            d = {"livello": "regola", "chi": sel}                                                  # 508.1c, 509.1b
            if "attack" in x: d["non_attacca"] = True
            if "block" in x: d["non_blocca"] = True
            eff.append(d)
    if se: eff = [dict(d, se=dict(se, **(d.get("se") or {}))) for d in eff]
    return [{"tipo": "statica", "effetti": eff}]
COSTI_PROPRI = [
    (r"this spell costs \{(\d)\} less to cast if you control a legendary creature\.", lambda n: {"delta": -n, "se": "leggendaria_tua"}),
    (r"this spell costs \{(\d)\} less to cast if you've cast a noncreature spell this turn\.", lambda n: {"delta": -n, "se": "noncreatura_lanciata"}),
    (r"this spell costs \{x\} less to cast, where x is the greatest power among creatures you control\.", lambda n: {"meno": "forza_max"}),
    (r"this spell costs \{x\} less to cast, where x is the greatest toughness among creatures you control\.", lambda n: {"meno": "costituzione_max"}),
    # 601.2f, 118.7 (14 nov 2026): le condizioni sullo stato della partita (non sui bersagli: quelle restano mancanti)
    (r"this spell costs \{(\d)\} less to cast during your turn\.", lambda n: {"delta": -n, "cond": {"tuo_turno": True}}),
    (r"this spell costs \{(\d)\} less to cast if a creature is attacking you\.", lambda n: {"delta": -n, "cond": {"attaccato_ora": True}}),
    (r"this spell costs \{(\d)\} less to cast if you've cast another spell this turn\.", lambda n: {"delta": -n, "cond": {"lanciate_turno_almeno": 1}}),
    (r"this spell costs \{(\d)\} less to cast if your opponents control three or more creatures\.", lambda n: {"delta": -n, "cond": {"creature_avversari_almeno": 3}}),
    (r"this spell costs \{(\d)\} less to cast if you've gained 3 or more life this turn\.", lambda n: {"delta": -n, "cond": {"vita_guadagnata_turno_almeno": 3}}),
    (r"this spell costs \{(\d)\} less to cast if a creature died this turn\.", lambda n: {"delta": -n, "cond": {"morte_turno_almeno": 1}}),
    (r"this spell costs \{(\d)\} less to cast if one or more cards left your graveyard this turn\.", lambda n: {"delta": -n, "cond": {"lasciato_cimitero_turno": True}}),
    (r"this spell costs \{(\d)\} less to cast if creatures you control have total toughness 10 or greater\.", lambda n: {"delta": -n, "cond": {"costituzione_totale_almeno": 10}}),
    (r"this spell costs \{(\d)\} less to cast for each artifact and/or creature card in your graveyard\.", lambda n: {"per": "cimitero", "n": n, "tipi": ["artifact", "creature"]}),
    (r"this spell costs \{(\d)\} less to cast for each instant and sorcery card in your graveyard\.", lambda n: {"per": "cimitero", "n": n, "tipi": ["instant", "sorcery"]}),
    (r"this spell costs \{(\d)\} less to cast for each noncreature, nonland card in your graveyard\.", lambda n: {"per": "cimitero", "n": n, "non_tipi": ["creature", "land"]}),
    (r"this spell costs \{(\d)\} less to cast for each attacking creature\.", lambda n: {"per": "attaccanti", "n": n}),
    (r"this spell costs \{x\} less to cast, where x is the number of differently named lands you control\.", lambda n: {"meno": "terre_nomi"}),
    (r"this spell costs \{x\} less to cast, where x is the total power of creatures you control\.", lambda n: {"meno": "forza_totale"}),
    (r"this spell costs \{x\} less to cast, where x is the total power of creatures you control with flying\.", lambda n: {"meno": "forza_totale", "volanti": True}),
]
_BERSAGLI_COSTO = {"a tapped creature": {"tipi": ["creature"], "tappato": True}, "a tapped permanent": {"tappato": True},
                   "an attacking creature": {"tipi": ["creature"], "attaccante": True},
                   "an attacking nontoken creature": {"tipi": ["creature"], "attaccante": True, "non_pedina": True},
                   "a blocking creature": {"tipi": ["creature"], "bloccante": True},
                   "a creature with flying": {"tipi": ["creature"], "parola": "flying"}}
_COSTO_BERSAGLIO = r"this spell costs \{(\d)\} (less|more) to cast if it targets (a [a-z]+|an? [a-z ]+?)\."   # 601.2c-f
_COSTO_SOTTOTIPO = r"this spell costs \{(\d)\} less to cast if you control an? ([a-z]+)\."   # «if you control a Kithkin» (205.3)


def statica(p, ctx):
    m = re.fullmatch(r"(other )?creatures you control of the chosen type get \+(\d+)/\+(\d+)(?: and have ([a-z ,]+))?\.", p)
    if m:                                                                                        # 613.4c, 613.1f, 614.12 (14 nov 2026)
        sel = dict({"tipi": ["creature"], "controllo": "tuo", "tipo_scelto": True}, **({"altre": True} if m.group(1) else {}))
        eff = [{"livello": "7c", "chi": sel, "p": int(m.group(2)), "t": int(m.group(3))}]
        if m.group(4): eff.append({"livello": "6", "chi": sel, "dai": parole_lista(m.group(4))})
        return [{"tipo": "statica", "effetti": eff}]
    m = re.fullmatch(r'planeswalkers you control have "\[([+-]?\d+)\]: (.+)"\.?', p)
    if m:                                                                                        # 613.1f: un potere dato
        dato = attivata(f"{m.group(1)}: {m.group(2)}", f"{m.group(1)}: {m.group(2)}", ctx)
        if not dato or dato == "mana": raise Mancante("potere dato non letto")
        dato[0] = dict(dato[0], fa=[dict(d, chi="fonte") if d.get("chi") == "questa_planeswalker" else d for d in dato[0]["fa"]])
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"tipi": ["planeswalker"], "controllo": "tuo"}, "dai_abilita": dato}]}]
    if p == "planeswalkers you control aren't put into their owners' graveyards for having 0 loyalty.":
        return [{"tipo": "eccezione", "di": "pw_fedelta_zero"}]                                    # 704.5i
    m = re.fullmatch(r"each (other )?creature you control with a \+1/\+1 counter on it has (.+)\.", p)
    if m:
        sel = {"tipi": ["creature"], "controllo": "tuo", "con_segnalino": "+1/+1"}
        if m.group(1): sel["altre"] = True
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": sel, "dai": parole_lista(m.group(2))}]}]
    m = re.fullmatch(r"this creature gets " + PT + r"(?: and has ([a-z ,]+?))? as long as there are seven or more cards in your graveyard\.", p)
    if m:                                                                                        # «Threshold»: 611.3a
        se, sel = {"cimitero_almeno": 7}, {"se_stessa": True}
        eff = [{"livello": "7c", "chi": sel, "p": int(m.group(1)), "t": int(m.group(2)), "se": se}]
        if m.group(3): eff.append({"livello": "6", "chi": sel, "dai": parole_lista(m.group(3)), "se": se})
        return [{"tipo": "statica", "effetti": eff}]
    m = re.fullmatch(r"during your turn, this creature has (.+)\.", p)
    if m:
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"se_stessa": True}, "dai": parole_lista(m.group(1)), "se": {"tuo_turno": True}}]}]
    m = re.fullmatch(r"as long as an opponent was dealt noncombat damage this turn, this creature has (.+)\.", p)
    if m:
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"se_stessa": True}, "dai": parole_lista(m.group(1)),
                                                 "se": {"avversario_danno_nc_turno": True}}]}]
    for rx, fa in COSTI:                                                                           # 601.2f
        m = re.fullmatch(rx, p)
        if m: return [fa(int(m.group(1)))]
    m = re.fullmatch(r"([a-z]+) spells (?:and ([a-z]+) spells )?you cast cost \{(\d)\} less to cast\.", p)   # 601.2f, 205.3m (giro 8)
    if m and m.group(1) in COLORI and not m.group(2):                                              # 105.2 (giro 8): «Red spells»
        return [{"tipo": "costi", "di": "tuo", "colori": [COLORI[m.group(1)]], "delta": -int(m.group(3))}]
    if m and all(w is None or singolare(w) or w in TIPI_CREATURA or w in SOTTOTIPI_205 for w in (m.group(1), m.group(2))) and m.group(1) not in _TIPI_CARTA:
        st_ = [(singolare(w) or w).title() for w in (m.group(1), m.group(2)) if w]
        return [{"tipo": "costi", "di": "tuo", "sottotipi": st_, "delta": -int(m.group(3))}]
    for rx, fa in COSTI_PROPRI:
        m = re.fullmatch(rx, p)
        if m: return ("costo_mod", fa(int(m.group(1)) if m.groups() else 0))
    m = re.fullmatch(_COSTO_BERSAGLIO, p)
    if m:                                                                                        # 601.2f: dopo i bersagli (601.2c)
        b_ = _BERSAGLI_COSTO.get(m.group(3))
        if b_ is None and m.group(3).split()[-1] in TIPI_CREATURA: b_ = {"sottotipo": m.group(3).split()[-1].title()}   # «a Spider», «a Dragon»
        if b_ is not None:
            return ("costo_mod", {"delta": (-1 if m.group(2) == "less" else 1) * int(m.group(1)), "bersaglio": b_})
    m = re.fullmatch(_COSTO_SOTTOTIPO, p)
    if m and m.group(2) in TIPI_CREATURA | {"vehicle", "equipment", "aura"}:
        return ("costo_mod", {"delta": -int(m.group(1)), "cond": {"controlli_sottotipo": m.group(2).capitalize()}})
    if p == "~ doesn't untap during your untap step.": return "non_stappa"                          # 502.3
    if p == "~ has hexproof as long as they haven't dealt combat damage yet.":                       # 611.3a
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"se_stessa": True}, "dai": ["hexproof"], "se": {"senza_danno_combattimento": True}}]}]
    if p == "if ~'s power is negative, he assigns combat damage as though his power were positive.":
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "danno_assoluto": True}]}]   # 510.1a
    if p == "if one or more artifact tokens would be created under your control, that many 5/5 red dragon creature tokens with flying are created instead.":
        return [{"tipo": "sostituzione", "di": "draghi"}]                                          # 614.1a
    if p == "if a creature an opponent controls would die, exile it instead.":
        return [{"tipo": "sostituzione", "di": "muore_esilio_avversari"}]                           # 614.1a, 700.4
    if p == ("as long as there are seven or more cards in your graveyard, you may cast the exiled card, and mana of any type can be "
             "spent to cast that spell."):                                                       # «Threshold»: 611.3a, 607.2a, 601.3, 609.4b
        return [{"tipo": "lancia_collegata", "se": {"cimitero_almeno": 7}, "mana_qualsiasi": True}]
    if p == ("you may cast spells with mana value less than or equal to the number of creatures you control from your hand without "
             "paying their mana costs."):                                                        # 118.9, 601.2b, 107.3b
        return [{"tipo": "lancio_gratis", "da": "mano", "mv_max": "creature_tue"}]
    if p == "artifacts and creatures entering the battlefield don't cause abilities to trigger.":
        return [{"tipo": "divieto", "di": "inneschi_entrata"}]                                      # 101.2
    if p == "instant and sorcery spells you control have split second.":
        return [{"tipo": "sostituzione", "di": "split_second"}]                                    # 702.61a (613.1f)
    if p == "during combat, players can't cast spells or activate abilities that aren't mana abilities.":
        return [{"tipo": "divieto", "di": "combattimento"}]                                         # 101.2
    if p == "you can't cast this spell unless there are seven or more cards in your graveyard.":     # 601.3
        return ("lancio_solo_se", {"cimitero_almeno": 7})
    if p == 'planeswalkers you control have "no more than one creature can attack this planeswalker each combat."':
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"tipi": ["planeswalker"], "controllo": "tuo"}, "max_un_attaccante": True}]}]   # 508.1c
    if p == "creatures you control can attack as though they didn't have defender.":                 # 702.3b, 613.11
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"tipi": ["creature"], "controllo": "tuo"}, "attacca_con_difensore": True}]}]
    if p == "each creature you control with toughness greater than its power assigns combat damage equal to its toughness rather than its power.":
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"tipi": ["creature"], "controllo": "tuo"},
                                                 "filtri": {"costituzione_oltre_forza": True}, "danno_costituzione": True}]}]   # 510.1a
    if p == "if one or more +1/+1 counters would be put on a creature you control, that many plus one +1/+1 counters are put on it instead.":
        return [{"tipo": "sostituzione", "di": "segnalini_piu_uno"}]                                # 614.1a
    if p == "if a source you control would deal noncombat damage to an opponent or a permanent an opponent controls, it deals that much damage plus 1 instead.":
        return [{"tipo": "sostituzione", "di": "danno_piu_uno_nc"}]                                 # 614.1a
    m = re.fullmatch(r"creatures you control with power or toughness (\d+) or less can't be blocked\.", p)
    if m:                                                                                        # 509.1b, 613.11
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"tipi": ["creature"], "controllo": "tuo"},
                                                 "filtri": {"fc_max": int(m.group(1))}, "non_bloccabile": True}]}]
    m = re.fullmatch(r"(?:~|this creature) gets \+(\d+)/\+(\d+) for each ([a-z]+(?: and [a-z]+)?) card in your graveyard\.", p)
    if m:                                                                                        # 611.3a: si conta adesso
        spec = {"tipo": "cimitero_tipi", "tipi": m.group(3).split(" and ")}
        if not set(spec["tipi"]) <= {"creature", "planeswalker", "land", "artifact", "instant", "sorcery", "enchantment"}: raise Mancante("tipi")
        pt = {k: ({"conta": spec, "molt": int(v)} if int(v) else 0) for k, v in (("p", m.group(1)), ("t", m.group(2)))}
        return [{"tipo": "statica", "effetti": [dict({"livello": "7c", "chi": {"se_stessa": True}}, **pt)]}]
    sc_ = _statica_condizionata(p)
    if sc_ is not None: return sc_
    sc_ = _equipaggiata(p)
    if sc_ is not None: return sc_
    m = re.fullmatch(r"(?:~|this creature) gets \+(\d+)/\+(\d+) for each (artifact|creature|enchantment|land|other [a-z]+) you control\.", p)
    if m:                                                                                        # 611.3a: si conta adesso
        x = m.group(3)
        if x.startswith("other "):
            if x[6:] not in TIPI_CREATURA: raise Mancante("sottotipo")
            sel = {"sottotipo": x[6:].title(), "altre": True}
        else: sel = {"tipi": [x]}
        spec = {"tipo": "controlli", "sel": sel}
        pt = {k: ({"conta": spec, "molt": int(v)} if int(v) else 0) for k, v in (("p", m.group(1)), ("t", m.group(2)))}
        return [{"tipo": "statica", "effetti": [dict({"livello": "7c", "chi": {"se_stessa": True}}, **pt)]}]
    m = re.fullmatch(r"attacking creatures you control (?:get " + PT + r"|have ([a-z ,]+))\.", p)
    if m:                                                                                        # 506.4, 613.4c
        sel = {"tipi": ["creature"], "controllo": "tuo", "attaccante": True}
        if m.group(1): return [{"tipo": "statica", "effetti": [{"livello": "7c", "chi": sel, "p": int(m.group(1)), "t": int(m.group(2))}]}]
        if not all(x in PAROLE_SEMPLICI for x in parole_lista(m.group(3))): raise Mancante("parole")
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": sel, "dai": parole_lista(m.group(3))}]}]
    m = re.fullmatch(r"creatures you control with \+1/\+1 counters on them have ([a-z ,]+)\.", p)
    if m:                                                                                        # 122.1a
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"tipi": ["creature"], "controllo": "tuo", "con_segnalino": "+1/+1"},
                                                 "dai": parole_lista(m.group(1))}]}]
    m = re.fullmatch(r"(?:~|this creature) gets \+(\d+)/\+(\d+) for every (seven|two|three|four|five|six) cards in your graveyard\.", p)
    if m:                                                                                        # 107.1a: per ogni gruppo intero
        spec = {"tipo": "cimitero_ogni", "ogni": numero(m.group(3)) if m.group(3) in NUMERI else {"five": 5, "six": 6}[m.group(3)]}
        pt = {k: ({"conta": spec, "molt": int(v)} if int(v) else 0) for k, v in (("p", m.group(1)), ("t", m.group(2)))}
        return [{"tipo": "statica", "effetti": [dict({"livello": "7c", "chi": {"se_stessa": True}}, **pt)]}]
    m = re.fullmatch(r"(?:~|this creature) has ([a-z ,]+) as long as you control an? ([a-z]+) planeswalker\.", p)
    if m:                                                                                        # 611.3a
        se = {"controlli": {"tipi": ["planeswalker"], "sottotipo": m.group(2).title(), "controllo": "tuo"}}
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"se_stessa": True}, "dai": parole_lista(m.group(1)), "se": se}]}]
    if p == "as long as you've scried or surveilled this turn, this creature can attack as though it didn't have defender.":
        return "attacca_se_guardato"
    if p in ("this creature can't be blocked by more than one creature.", "~ can't be blocked by more than one creature."):   # 509.1b
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "max_un_bloccante": True}]}]
    if p in ("enchanted creature doesn't untap during its controller's untap step.",
             "enchanted permanent doesn't untap during its controller's untap step."): return ["blocca_stap"]   # 502.3 (14 nov 2026)
    if p == "enchanted permanent doesn't untap during its controller's untap step and its activated abilities can't be activated.":
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"attaccata": True}, "non_attivabili": True}]},   # 602.5
                "blocca_stap"]
    if p in ("enchanted creature loses all abilities and doesn't untap during its controller's untap step.",
             "enchanted permanent loses all abilities and doesn't untap during its controller's untap step.",
             "enchanted creature loses all abilities and can't become untapped."):                    # 502.3; «can't become untapped»: mai
        out_ = [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"attaccata": True}, "toglie": "tutte"}]}, "blocca_stap"]
        return out_ + (["mai_stappa"] if "can't become" in p else [])
    m = re.fullmatch(r"([a-z]+)s you control have (.+)\.", p)
    if m and m.group(1) in SOTTOTIPI:
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"controllo": "tuo", "sottotipo": m.group(1).title()}, "dai": parole_lista(m.group(2))}]}]
    m = re.fullmatch(r"artifact creatures you control have (.+)\.", p)
    if m: return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"tipi": ["creature"], "anche_tipo": "artifact", "controllo": "tuo"}, "dai": parole_lista(m.group(1))}]}]
    m = re.fullmatch(r"lands you control have (.+)\.", p)
    if m: return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": {"tipi": ["land"], "controllo": "tuo"}, "dai": parole_lista(m.group(1))}]}]
    m = re.fullmatch(r"creature tokens you control get " + PT + r" and have (.+)\.", p)
    if m:
        sel = {"tipi": ["creature"], "controllo": "tuo", "pedina": True}
        return [{"tipo": "statica", "effetti": [{"livello": "7c", "chi": sel, "p": int(m.group(1)), "t": int(m.group(2))},
                                                 {"livello": "6", "chi": sel, "dai": parole_lista(m.group(3))}]}]
    m = re.fullmatch(r"(other )?creatures you control have (.+)\.", p)
    if m:
        sel = {"tipi": ["creature"], "controllo": "tuo"}
        if m.group(1): sel["altre"] = True
        return [{"tipo": "statica", "effetti": [{"livello": "6", "chi": sel, "dai": parole_lista(m.group(2))}]}]
    m = re.fullmatch(r"(other )?creatures you control get " + PT + r"\.", p)
    if m:
        sel = {"tipi": ["creature"], "controllo": "tuo"}
        if m.group(1): sel["altre"] = True
        return [{"tipo": "statica", "effetti": [{"livello": "7c", "chi": sel, "p": int(m.group(2)), "t": int(m.group(3))}]}]
    # 14 nov 2026: i signori di un tipo, gli artefatti creatura, le restrizioni, la terra in piu', la cima visibile
    m = re.fullmatch(r"(other )?([a-z]+?)(?: creatures)? you control get " + PT + r"(?: and have ([a-z ,]+))?\.", p)
    if m and (singolare(m.group(2)) or m.group(2) == "artifact"):                                  # 613.4c, 205.3m
        sel = {"tipi": ["creature"], "controllo": "tuo"}
        if m.group(2) == "artifact": sel["anche_tipo"] = "artifact"
        else: sel["sottotipo"] = singolare(m.group(2)).title()
        if m.group(1): sel["altre"] = True
        eff = [{"livello": "7c", "chi": sel, "p": int(m.group(3)), "t": int(m.group(4))}]
        if m.group(5): eff.append({"livello": "6", "chi": sel, "dai": parole_lista(m.group(5))})
        return [{"tipo": "statica", "effetti": eff}]
    m = re.fullmatch(r"enchanted creature can't (attack or block|block|attack)\.", p)
    if m:                                                                                        # 508.1c, 509.1b, 613.11
        d = {"livello": "regola", "chi": {"attaccata": True}}
        if "attack" in m.group(1): d["non_attacca"] = True
        if "block" in m.group(1): d["non_blocca"] = True
        return [{"tipo": "statica", "effetti": [d]}]
    m = re.fullmatch(r"(?:~|this creature) can't be blocked by creatures with power (\d+) or less\.", p)
    if m:                                                                                        # 509.1b
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "non_bloccata_da_forza_max": int(m.group(1))}]}]
    if p in ("this creature can block only creatures with flying.", "~ can block only creatures with flying."):   # 509.1b (14 nov 2026)
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "blocca_solo_volanti": True}]}]
    m = re.fullmatch(r"(?:~|this creature) can't block or be blocked by non-([a-z]+) creatures\.", p)
    if m and m.group(1) in TIPI_CREATURA:                                                        # 509.1b (14 nov 2026)
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "blocca_solo_tipo": m.group(1).title(),
                                                 "non_bloccata_da_non_tipo": m.group(1).title()}]}]
    m = re.fullmatch(r"(?:~|this creature) can't be blocked by ([a-z]+)\.", p)
    if m and singolare(m.group(1)):                                                              # 509.1b (14 nov 2026): «by Humans»
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "non_bloccata_da_tipo": singolare(m.group(1)).title()}]}]
    if p == "you may play an additional land on each of your turns.":                              # 305.2
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "terra_extra": 1}]}]
    if p == "you may look at the top card of your library any time.":                              # 401.3 (solo informazione)
        return [{"tipo": "statica", "effetti": [{"livello": "regola", "chi": {"se_stessa": True}, "vede_cima": True}]}]
    return None


def leggi_magia(faccia, nome):
    """Una magia (istantaneo o stregoneria): le istruzioni, i bersagli, i modi. -> car, o Mancante."""
    corto = nome.split(",")[0]
    car = {"costo": faccia["mana_cost"] or None}
    par = [normalizza(x.strip(), nome, corto) for x in pulisci(faccia["oracle"]).split("\n") if x.strip()]
    ctx = Contesto(nome)
    fa = []
    k = 0
    while k < len(par):
        if AGGANCIO_MAGIA is not None and POSTO is not None:                                      # una parola di un set (14 nov 2026)
            k2 = AGGANCIO_MAGIA(POSTO, par, k, car, nome)
            if k2 is not None: k = k2; continue
        m = re.fullmatch(r"choose (one|two|one or more) —", par[k])
        if m:
            mm, k = [], k + 1
            while k < len(par) and par[k].startswith("•"):
                cm = Contesto(nome)
                mm.append({"fa": frasi(senza_nome_modo(par[k][1:].strip()), cm), "bersagli": cm.reqs}); k += 1
            if fa: raise Mancante("testo prima dei modi")
            car["modi"], car["scegli"] = mm, {"one": 1, "two": 2, "one or more": "uno_o_piu"}[m.group(1)]
            continue
        m = re.fullmatch(r"as an additional cost to cast this spell, sacrifice a creature or planeswalker or pay (\{\d+\})\.", par[k])
        if m:                                                                                    # 601.2b, 601.2f, 601.2h
            car["costo_aggiuntivo"] = [{"sacrifica": ["creature", "planeswalker"]}, {"mana": m.group(1)}]; k += 1; continue
        ca_ = costo_aggiuntivo(par[k])
        if ca_ is not None: car["costo_aggiuntivo"] = ca_; k += 1; continue
        kk_ = kicker(par[k])
        if kk_ is not None: car["facoltativo"] = kk_; k += 1; continue                            # 702.33a
        fa += frasi(par[k], ctx); k += 1
    if not car.get("modi"):
        car["fa"] = fa
        if ctx.reqs: car["bersagli"] = ctx.reqs
    return car


# ====================================================================== la carta
class Traduzione:
    def __init__(self, nome, voce, mancanti, scheda):
        self.nome, self.voce, self.mancanti, self.scheda = nome, voce, mancanti, scheda

    @property
    def intera(self): return not self.mancanti


def _mana_terra(p):
    if p == "{t}: add one mana of any color.": return ["{W}", "{U}", "{B}", "{R}", "{G}"]             # 106.1a, 605
    m = re.fullmatch(r"\{t\}: add (\{[wubrgc]\}), (\{[wubrgc]\}), or (\{[wubrgc]\})\.", p)           # le terre a tre colori
    if m: return [x.upper() for x in m.groups()]
    m = re.fullmatch(r"\{t\}: add (\{[wubrgc]\})(?: or (\{[wubrgc]\}))?\.", p)
    if m: return [x.upper() for x in m.groups() if x]
    return None


def traduci(c):
    """Una carta di fra_carte_complete.json -> Traduzione (nome, (nome, tipo, car) per il Tavolo, mancanti)."""
    global POSTO
    prima, POSTO = POSTO, c.get("_posto")
    try: return _traduci(c)
    finally: POSTO = prima


_FACCE = None


def facce_colori():
    """{nome della faccia: colori} (Motore_Partita/facce_colori.json, da carte_set.py --facce)."""
    global _FACCE
    if _FACCE is None:
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facce_colori.json")
        _FACCE = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    return _FACCE


def _traduci(c):
    f0 = c["faces"][0]
    nome = f0["name"]
    corto = nome.split(",")[0]
    if corto == nome and "Legendary" in f0["type"]: corto = nome.split(" ")[0]                     # «Kiora» per Kiora of Fire and Ashes
    car = {"costo": f0["mana_cost"] or None, "parole": [], "abilita": []}
    if f0.get("p") is not None:                                                                    # «*»: la definisce un'abilita' (604.3)
        car["forza"], car["costituzione"] = [int(v) if re.fullmatch(r"-?\d+", v) else v for v in (f0["p"], f0["t"])]
    if f0.get("loyalty") is not None: car["fedelta"] = int(f0["loyalty"])
    if not car["costo"]: car.pop("costo")
    tipo = f0["type"]
    mancanti = []
    if len(c["faces"]) > 1 and c.get("layout", "prepare") == "prepare":
        f1 = c["faces"][1]
        try:
            car["prepara"] = (f1["name"], f1["type"], leggi_magia(f1, f1["name"]))                  # 723.2, 723.3c
        except Mancante as e:
            mancanti.append((f1["name"], f"723.3c: la magia preparata non si legge: {e}"))
    elif len(c["faces"]) > 1 and c.get("layout") == "adventure":                                  # 716.2: le caratteristiche alternative
        f1 = c["faces"][1]
        try:
            car["avventura"] = (f1["name"], f1["type"], leggi_magia(f1, f1["name"]))
        except Mancante as e:
            mancanti.append((f1["name"], f"716.2, 721.2: l'avventura o l'Omen non si legge: {e}"))
    elif len(c["faces"]) > 1 and c.get("layout") in ("transform", "modal_dfc"):                  # 712.2, 712.6d (14 nov 2026): la
        f1 = c["faces"][1]                                                                       # faccia dietro, letta come una carta
        tr_ = _traduci({"faces": [f1], "_posto": POSTO, "layout": "normal", "name": f1["name"]})
        if tr_.mancanti: mancanti += [(p_ or f1["name"], f"712: la faccia dietro: {m_}") for p_, m_ in tr_.mancanti]
        else:
            car_r = dict(tr_.voce[2])
            col_ = facce_colori().get(f1["name"])
            if col_ is None: mancanti.append((f1["name"], "204: il colore della faccia dietro non si conosce"))
            else: car_r["colori"] = col_                                                         # 204, 202.2: l'indicatore di colore
            car["retro"] = (f1["name"], f1["type"], car_r)
            if c.get("layout") == "modal_dfc": car["mdfc"] = True                                 # 712.3, 712.8b: si lancia da tutte e due
    elif len(c["faces"]) > 1:                                                                    # gli altri set (14 nov 2026)
        f1 = c["faces"][1]
        regola = SECONDE_FACCE.get(c.get("layout"), "nessuna regola letta")
        mancanti.append((f1["name"], f"{regola}: la seconda faccia ({c.get('layout')}) non e' ancora nel motore"))
    testo = pulisci(f0["oracle"])
    ctx = Contesto(nome)
    paragrafi = [x.strip() for x in testo.split("\n") if x.strip()]
    spell = bool({"Instant", "Sorcery"} & set(tipo.split()))
    i = 0
    prog_spell = {"fa": [], "bersagli": []}
    ctx_spell = Contesto(nome)
    ctx_spell.x_magia = spell and "{X}" in (f0.get("mana_cost") or "")                           # 107.3a: la X del costo della magia
    while i < len(paragrafi):
        orig = paragrafi[i]
        low = normalizza(orig, nome, corto)
        p = low
        modi = []
        j = i + 1
        while j < len(paragrafi) and paragrafi[j].startswith("•"): modi.append(paragrafi[j][1:].strip()); j += 1
        try:
            if AGGANCIO is not None and AGGANCIO(c, low, orig, car, ctx, {"modi": modi, "spell": spell, "nome": nome, "corto": corto,
                                                                          "prog_spell": prog_spell, "ctx_spell": ctx_spell}):
                i = j; continue                                                                  # il posto del set (carte_set.py)
            m = re.fullmatch(r"((?:iv|v|vi|i{1,3})(?:, (?:iv|v|vi|i{1,3}))*) — (.+)", low)
            if m and "Saga" in tipo.split("—")[-1].split():                                       # 715.2a-c: i capitoli (14 nov 2026)
                cx = Contesto(nome)
                corpo = re.sub(r"^[a-z][a-z'’!,-]*(?: [a-z'’!,-]+){0,3} — ", "", m.group(2))               # 207.2d: la parola di sapore
                fa = frasi(corpo, cx)
                for r_ in m.group(1).split(", "):
                    ab = {"tipo": "innescata", "quando": {"evento": "capitolo", "n": ROMANI[r_]}, "fa": fa}
                    if cx.reqs: ab["bersagli"] = cx.reqs
                    car["abilita"].append(ab)
                    car["capitoli"] = max(car.get("capitoli", 0), ROMANI[r_])                     # 715.2d
                i = j; continue
            # le parole chiave (702)
            if low in ("convoke", "convoke."): car["convoke"] = True; i = j; continue              # 702.51a
            if low in ("improvise", "improvise."): car["improvise"] = True; i = j; continue        # 702.126a (14 nov 2026)
            if low == "this spell can't be countered.": car["incontrastabile"] = True; i = j; continue   # 113.6g
            if low == "affinity for artifacts":                                                     # 702.41a (14 nov 2026)
                car.setdefault("costo_mod", []).append({"meno": "per_artefatto"}); i = j; continue
            m = re.fullmatch(r"affinity for ([a-z]+)", low)                                          # 702.41a (giro 8): «affinity for Forests,
            if m:                                                                                  # Elves, creatures, planeswalkers, Gates»
                w_ = m.group(1)
                if w_ in ("creatures", "planeswalkers", "lands", "enchantments"): sel_ = {"tipi": [w_[:-1]]}
                elif singolare(w_): sel_ = {"tipi": ["permanent"], "sottotipo": singolare(w_).title()}
                elif w_.endswith("s") and w_[:-1] in SOTTOTIPI_205: sel_ = {"tipi": ["permanent"], "sottotipo": w_[:-1].title()}
                else: sel_ = None
                if sel_ is not None:
                    car.setdefault("costo_mod", []).append({"meno": "per_sel", "sel": sel_}); i = j; continue
            m = re.fullmatch(r"crew (\d+)", low)
            if m and "Vehicle" in tipo.split("—")[-1].split():                                       # 702.122a, 301.7 (14 nov 2026)
                car["parole"].append("crew")                                                     # 702.122: una parola chiave
                car["abilita"].append({"tipo": "attivata", "da_parola": "crew", "costo": {"equipaggia": int(m.group(1))},
                                       "velocita": "istantanea", "fa": [{"fa": "diventa_tipo", "chi": "fonte", "tipi": ["artifact", "creature"],
                                                                         "durata": "fine_turno"}]})
                i = j; continue
            if low == "~'s power is equal to the number of card types among cards in all graveyards and its toughness is equal to that number plus 1.":
                car["cda"] = "tipi_cimiteri"; i = j; continue                                     # 604.3, 613.4a
            m = re.fullmatch(r"(?:~|this creature)'s (power|power and toughness) (?:is|are each) equal to the number of ([a-z]+) you control\.", low)
            if m:                                                                                # 604.3, 613.4a (14 nov 2026): la forza
                w = m.group(2)                                                                    # definita da un conteggio
                sel = ({"tipi": [w[:-1]]} if w in ("creatures", "lands", "artifacts", "enchantments") else
                       {"sottotipo": singolare(w).title()} if singolare(w) else None)
                if sel is None: raise Mancante(f"604.3: {w!r}")
                if m.group(1) == "power" and not isinstance(car.get("costituzione"), int): raise Mancante("604.3: costituzione")
                car["cda"] = {"controlli": sel, "anche_costituzione": m.group(1) != "power"}; i = j; continue
            if low == "~'s power is equal to the number of basic land types among lands you control.":   # «Domain»: 207.2c, 604.3,
                if car.get("costituzione") is None or not isinstance(car["costituzione"], int): raise Mancante("604.3: costituzione")
                car["cda"] = "dominio"; i = j; continue                                           # 613.4a, 205.3i, 305.6, 109.5
            m = re.fullmatch(r"as an additional cost to cast this spell, behold a jace or pay (\{\d+\})\.", low)
            if m and spell:                                                                      # 601.2b, 701.4a
                car["costo_aggiuntivo"] = [{"behold": "Jace"}, {"mana": m.group(1)}]; i = j; continue
            if low == "as this land enters, you may behold a jace. if you don't, this land enters tapped.":
                car.setdefault("entra", {})["tappata"] = "senza_jace"; i = j; continue              # 701.4a, 614.1d
            if low == "ward—discard a card.":                                                  # 702.21a con un costo non di mana
                car["parole"].append("ward")
                car["abilita"].append({"tipo": "innescata", "da_parola": "ward", "quando": {"evento": "bersagliato"},
                                       "fa": [{"fa": "contrasta_salvo", "chi": "evento", "costo": {"scarta": 1}}]})
                i = j; continue
            m = re.fullmatch(r"ward—sacrifice (two|three|four) permanents\.", low)
            if m:                                                                                # 702.21a, 701.21a, 118.3
                car["parole"].append("ward")
                car["abilita"].append({"tipo": "innescata", "da_parola": "ward", "quando": {"evento": "bersagliato"},
                                       "fa": [{"fa": "contrasta_salvo", "chi": "evento", "costo": {"sacrifica": numero(m.group(1))}}]})
                i = j; continue
            pk = [x.strip().lower() for x in re.split(r",\s*", p.rstrip("."))]
            if all(x in PAROLE_SEMPLICI or x == "prowess" or re.fullmatch(r"ward \{\d+\}", x) for x in pk):
                for x in pk:
                    if x == "prowess":
                        car["parole"].append("prowess")
                        car["abilita"].append({"tipo": "innescata", "da_parola": "prowess", "quando": {"evento": "lanci", "non_tipi": ["creature"]},
                                               "fa": [{"fa": "pompa", "chi": "fonte", "p": 1, "t": 1, "durata": "fine_turno"}]})   # 702.108a
                    elif x.startswith("ward"):
                        costo = x[5:].upper()
                        car["parole"].append("ward")
                        car["abilita"].append({"tipo": "innescata", "da_parola": "ward", "quando": {"evento": "bersagliato"},
                                               "fa": [{"fa": "contrasta_salvo", "chi": "evento", "costo": costo}]})        # 702.21a
                    else: car["parole"].append(x)
                i = j; continue
            if spell and not re.match(r"(when|whenever|at) ", low) and not re.match(r"(flashback|basic landcycling|[a-z]*cycling \{|this spell costs|a deck can have)", low):
                m = re.fullmatch(r"as an additional cost to cast this spell, sacrifice a creature or planeswalker or pay (\{\d+\})\.", low)
                if m:                                                                            # 601.2b, 601.2f, 601.2h
                    car["costo_aggiuntivo"] = [{"sacrifica": ["creature", "planeswalker"]}, {"mana": m.group(1)}]; i = j; continue
                ca_ = costo_aggiuntivo(low)
                if ca_ is not None: car["costo_aggiuntivo"] = ca_; i = j; continue
                kk_ = kicker(low.rstrip("."))
                if kk_ is not None: car["facoltativo"] = kk_; i = j; continue                     # 702.33a (14 nov 2026)
                if re.fullmatch(r"choose (one|two|one or more|one or both) —", low):                    # 700.2 («one or both»: uno o piu')
                    n = {"one": 1, "two": 2, "one or more": "uno_o_piu", "one or both": "uno_o_piu"}[re.fullmatch(r"choose (one|two|one or more|one or both) —", low).group(1)]
                    mm = []
                    for t in modi:
                        cm = Contesto(nome)
                        t2 = senza_nome_modo(normalizza(t, nome, corto))
                        mm.append({"fa": frasi(t2, cm), "bersagli": cm.reqs})
                    if prog_spell["fa"]: raise Mancante("testo prima dei modi")
                    car["modi"], car["scegli"] = mm, n
                    i = j; continue
                prog_spell["fa"] += frasi(low, ctx_spell)
                prog_spell["bersagli"] = ctx_spell.reqs
                i = j; continue
            mt = _mana_terra(low)
            if mt:
                car["mana"] = mt; i = j; continue
            m = re.fullmatch(r"(\{t\}: add .+?\.) activate only if (this land entered this turn or if you control a basic land|"
                             r"you control an? (plains|island|swamp|mountain|forest) or an? (plains|island|swamp|mountain|forest))\.", low)
            if m and _mana_terra(m.group(1)):                                                     # 605.1a, 602.5b: il mana condizionato,
                car.setdefault("mana_cond", []).append({"mana": _mana_terra(m.group(1)),             # a parte da quello senza condizioni
                    "se": {"entrata_turno_o_base": True} if m.group(3) is None else {"controlli_sottotipo": [m.group(3).title(), m.group(4).title()]}})
                i = j; continue
            if low in ("this land enters tapped.",): car.setdefault("entra", {})["tappata"] = "sempre"; i = j; continue
            if re.fullmatch(r"as (?:~|this [a-z]+) enters, choose a creature type\.", low):           # 614.12, 205.3m (14 nov 2026)
                car.setdefault("entra", {})["sceglie_tipo"] = True; i = j; continue
            if low == "this land enters tapped. as it enters, choose a color.":                    # 614.1c-d, 614.12a
                car.setdefault("entra", {}).update(tappata="sempre", sceglie_colore=True); i = j; continue
            if low == "{t}: add one mana of the chosen color.": car["mana_colore_scelto"] = True; i = j; continue
            if low == "{t}: choose a color. add one mana of that color for each different power among creatures you control.":
                car["mana_poteri_diversi"] = True; i = j; continue                                 # 605.1a, 105.4
            if low == "this land enters tapped unless you control a planeswalker.":
                car.setdefault("entra", {})["tappata"] = "senza_planeswalker"; i = j; continue
            m = re.fullmatch(r"as this land enters, you may pay (\d+) life\. if you don't, it enters tapped\.", low)
            if m:                                                                                # 614.1d, 614.12, 119.4 (14 nov 2026)
                car.setdefault("entra", {})["tappata"] = f"senza_pagare_vite:{m.group(1)}"; i = j; continue
            if low == "this land enters tapped unless you control a basic land.":                   # 614.1d, 205.4c
                car.setdefault("entra", {})["tappata"] = "senza_terra_base"; i = j; continue
            if low == "this creature can't block.":                                                 # 509.1b: una restrizione
                car["non_blocca"] = True; i = j; continue
            if low == "enchant creature you control":                                               # 303.4a, 702.5
                car["incanta"] = {"chi": ["creature"], "controllo": "tuo"}; i = j; continue
            m = re.fullmatch(r"ward—pay (\d+) life\.", low)
            if m:                                                                                # 702.21a, 119.4
                car["parole"].append("ward")
                car["abilita"].append({"tipo": "innescata", "da_parola": "ward", "quando": {"evento": "bersagliato"},
                                       "fa": [{"fa": "contrasta_salvo", "chi": "evento", "costo": {"vite": int(m.group(1))}}]})
                i = j; continue
            m = re.fullmatch(r"this land enters tapped unless you control an? (plains|island|swamp|mountain|forest) or an? (plains|island|swamp|mountain|forest)\.", low)
            if m:                                                                                # 614.1d, 305.6: i tipi di terra
                car.setdefault("entra", {})["tappata"] = "senza_sottotipi:" + m.group(1).title() + "," + m.group(2).title(); i = j; continue
            if low == "this land enters tapped unless you control two or more other lands.":
                car.setdefault("entra", {})["tappata"] = "meno_di_due_altre_terre"; i = j; continue
            m = re.fullmatch(r"(?:this creature|~) enters with (a|x|two|three|four|five|six) \+1/\+1 counters? on it\.", low)
            if m: car.setdefault("entra", {})["segnalini"] = {"+1/+1": numero(m.group(1))}; i = j; continue
            m = re.fullmatch(r"(?:this creature|~) enters with (a|two|three|four) \+1/\+1 counters? on it if (.+)\.", low)
            if m and cond_statica(m.group(2)) is not None:                                         # 614.1c, 611.3a (giro 8): la condizione
                car.setdefault("entra", {})["segnalini_se"] = {"se": cond_statica(m.group(2)), "segnalini": {"+1/+1": numero(m.group(1))}}   # mentre entra
                i = j; continue
            m = re.fullmatch(r"(?:this creature|~) enters with (a|two|three|four) -1/-1 counters? on it\.", low)
            if m: car.setdefault("entra", {})["segnalini"] = {"-1/-1": numero(m.group(1))}; i = j; continue   # 614.1c, 122.6 (14 nov 2026)
            m = re.fullmatch(r"(?:this creature|this artifact|this land|this enchantment|~) enters with (a|an|two|three|four|five|six|seven|eight) "
                             r"(-1/-1|\+1/\+1|[a-z]+) counters? on (?:it|him|her|them)\.", low)
            if m and (m.group(2) in ("-1/-1", "+1/+1") or (m.group(2) in PAROLE_SEMPLICI)
                      or m.group(2) in ("wish", "film", "fire", "fellowship", "growth", "charge", "oil", "page", "bait", "incubation")):
                tipo_ = "carica" if m.group(2) == "charge" else m.group(2)                            # 614.1c, 122.1 (giro 8): ogni segnalino
                if not car.get("entra", {}).get("segnalini"):                                       # che e' solo un segno, o una parola
                    car.setdefault("entra", {})["segnalini"] = {tipo_: numero(m.group(1))}; i = j; continue   # chiave (122.1b)
            if low == "~ enters tapped.":                                                           # 614.1c (giro 8)
                car.setdefault("entra", {})["tappata"] = "sempre"; i = j; continue
            if low in ("this creature enters tapped.", "this artifact enters tapped."):            # 614.1c
                car.setdefault("entra", {})["tappata"] = "sempre"; i = j; continue
            if low == "~ enters prepared.": low = "this creature enters prepared."                      # 723 (14 nov 2026): il nome
            if low == "this creature enters prepared.":
                if "prepara" not in car: raise Mancante("723.3a: senza la magia preparata")
                car.setdefault("entra", {})["preparato"] = True; i = j; continue                        # 723.3a
            m = re.fullmatch(r"at the beginning of your upkeep, if this creature isn't prepared, it becomes prepared\.", low)
            if m:
                car["abilita"].append({"tipo": "innescata", "quando": {"evento": "inizio_passo", "passo": "mantenimento", "di": "tuo"},
                                       "se": {"non_preparato": True}, "fa": [{"fa": "prepara", "chi": "fonte"}]})   # 603.4
                i = j; continue
            if low == "enchant creature": car["incanta"] = {"chi": ["creature"]}; i = j; continue        # 303.4a, 702.5
            if low == "enchant land": car["incanta"] = {"chi": ["land"]}; i = j; continue                # 303.4a, 702.5 (14 nov 2026)
            if low == "enchant artifact or creature": car["incanta"] = {"chi": ["artifact", "creature"]}; i = j; continue   # 303.4a
            if low == "enchant creature or vehicle":                                                # 303.4a, 301.7 (14 nov 2026)
                car["incanta"] = {"chi": ["creature", "artifact"], "o_sottotipo": "Vehicle"}; i = j; continue
            m = re.fullmatch(r"this land enters tapped unless you control an? ([a-z]+) or (?:an? )?([a-z]+)\.", low)
            if m and m.group(1) not in ("plains", "island", "swamp", "mountain", "forest"):           # 614.1d: un permanente di quei
                car.setdefault("entra", {})["tappata"] = "senza_permanenti:" + m.group(1).title() + "," + m.group(2).title()   # sottotipi
                i = j; continue
            if low == "enchant artifact or non-aura enchantment":                                   # 303.4a, 702.5
                car["incanta"] = {"chi": ["artifact", "enchantment"], "non_sottotipi": ["Aura"]}; i = j; continue
            m = re.fullmatch(r"enchanted permanent is an? ([a-z]+) creature with base power and toughness (\d+)/(\d+) in addition to its other types\.", low)
            if m:                                                                                # 613.1d, 205.1b; 613.4b; 613.6
                sel = {"attaccata": True}
                car["abilita"].append({"tipo": "statica", "effetti": [
                    {"livello": "4", "chi": sel, "tipi": ["creature"], "sottotipi": [m.group(1).capitalize()]},
                    {"livello": "7b", "chi": sel, "p": int(m.group(2)), "t": int(m.group(3)), "segue": "4"}]})
                i = j; continue
            m = re.fullmatch(r'(equipped|enchanted) creature gets ' + PT + r' and has "(whenever this creature attacks, .+?)\.?"\.?', low)
            if m:                                                                                # 613.1f: solo l'abilita' innescata data
                sel = {"attaccata": True}
                data = innesco(m.group(4).replace("this creature", "~") + ".", ctx)
                if not data: raise Mancante("abilita' data non letta")
                eff = [{"livello": "7c", "chi": sel, "p": int(m.group(2)), "t": int(m.group(3))},
                       {"livello": "6", "chi": sel, "dai_abilita": data}]
                car["abilita"].append({"tipo": "statica", "effetti": eff}); i = j; continue
            m = re.fullmatch(r'(equipped|enchanted) creature gets ' + PT + r' and has ([a-z ,]+?) and "(whenever this creature attacks, .+?)\.?"\.?', low)
            if m:                                                                                # 613.1f: anche un'abilita' innescata data
                sel = {"attaccata": True}
                data = innesco(m.group(5).replace("this creature", "~"), ctx)
                if not data: raise Mancante("abilita' data non letta")
                eff = [{"livello": "7c", "chi": sel, "p": int(m.group(2)), "t": int(m.group(3))},
                       {"livello": "6", "chi": sel, "dai": parole_lista(m.group(4))},
                       {"livello": "6", "chi": sel, "dai_abilita": data}]
                car["abilita"].append({"tipo": "statica", "effetti": eff}); i = j; continue
            m2_ = re.fullmatch(r"(equipped|enchanted) creature has ([a-z ,]+)\.", low)
            if m2_ and all(x in PAROLE_SEMPLICI for x in parole_lista(m2_.group(2))):             # 613.1f, 301.5 (14 nov 2026)
                car["abilita"].append({"tipo": "statica", "effetti": [{"livello": "6", "chi": {"attaccata": True}, "dai": parole_lista(m2_.group(2))}]})
                i = j; continue
            m = re.fullmatch(r"(equipped|enchanted) creature gets " + PT + r"(?: and has ([a-z ,]+))?\.", low)
            if m:
                sel = {"attaccata": True}
                eff = [{"livello": "7c", "chi": sel, "p": int(m.group(2)), "t": int(m.group(3))}]
                if m.group(4): eff.append({"livello": "6", "chi": sel, "dai": parole_lista(m.group(4))})
                car["abilita"].append({"tipo": "statica", "effetti": eff}); i = j; continue           # 301.5, 303.4b
            ab_ = attaccata_generica(low)
            if ab_ is not None: car["abilita"] += ab_; i = j; continue
            m = re.fullmatch(r"equip (\{[^}]+\}(?:\{[^}]+\})*)\. this ability costs \{(\d)\} less to activate for each \+1/\+1 counter "
                             r"on the creature it targets\.", low)
            if m:                                                                                # 702.6a, 602.2b, 601.2c-f, 118.7a
                car["abilita"].append({"tipo": "attivata", "costo": {"mana": m.group(1).upper()}, "velocita": "stregoneria",
                                       "bersagli": [{"chi": ["creature"], "controllo": "tuo"}],
                                       "riduzione": {"per_segnalino": "+1/+1", "bersaglio": 0, "n": int(m.group(2))},
                                       "fa": [{"fa": "attacca", "chi": "bersaglio:0"}]})
                i = j; continue
            m = re.fullmatch(r"(?:[a-z'’ ]+ — )?equip (\{[^}]+\}(?:\{[^}]+\})*)", low)                 # 207.2c: un nome davanti
            if m:                                                                                # 702.6a
                car["abilita"].append({"tipo": "attivata", "costo": {"mana": m.group(1).upper()}, "velocita": "stregoneria",
                                       "bersagli": [{"chi": ["creature"], "controllo": "tuo"}],
                                       "fa": [{"fa": "attacca", "chi": "bersaglio:0"}]})
                i = j; continue
            ab = innesco(low, ctx)
            if ab is not None:
                for a in ab:
                    quanti_modi = a.pop("modi_da_leggere", None)
                    if quanti_modi:
                        mm = []
                        for t in modi:
                            cm = Contesto(nome)
                            t2 = senza_nome_modo(normalizza(t, nome, corto))
                            mm.append({"fa": frasi(t2, cm), "bersagli": cm.reqs})
                        a["modi"], a["scegli"] = mm, quanti_modi
                car["abilita"] += ab
                i = j; continue
            m = re.fullmatch(r"\{t\}: add (\{c\}|one mana of any color)\. (this mana can't be spent to cast spells from your hand|"
                             r"spend this mana only to cast a planeswalker spell)\.", low)
            if m:                                                                                # 106.6: il mana vincolato
                car["mana"] = ["{C}"] if m.group(1) == "{c}" else ["{W}", "{U}", "{B}", "{R}", "{G}"]
                car["mana_vincolo"] = "non_dalla_mano" if "from your hand" in m.group(2) else "solo_planeswalker"
                i = j; continue
            m = re.fullmatch(r"\{t\}: add (\{[wubrgc]\}|one mana of any color)\. spend this mana only to cast an artifact spell"
                             r"( or (?:to )?activate an ability( of an artifact source)?)?\.", low)
            if m:                                                                                # 106.6 (14 nov 2026)
                car["mana"] = [m.group(1).upper()] if m.group(1).startswith("{") else ["{W}", "{U}", "{B}", "{R}", "{G}"]
                car["mana_vincolo"] = "artefatto_o_abilita_artefatto" if m.group(3) else "artefatto_o_abilita" if m.group(2) else "artefatto"
                i = j; continue
            m = re.fullmatch(r"\{t\}: add ((?:\{[wubrgc]\})+|one mana of any color)\. spend this mana only to (cast an instant or sorcery spell|"
                             r"activate abilities|activate abilities of artifact sources|activate abilities of creature sources)\.", low)
            if m:                                                                                # 106.6 (14 nov 2026)
                car["mana"] = [m.group(1).upper()] if m.group(1).startswith("{") else ["{W}", "{U}", "{B}", "{R}", "{G}"]
                car["mana_vincolo"] = {"cast an instant or sorcery spell": "istantaneo_stregoneria", "activate abilities": "solo_abilita",
                                       "activate abilities of artifact sources": "abilita_artefatto",
                                       "activate abilities of creature sources": "abilita_creatura"}[m.group(2)]
                i = j; continue
            m = re.fullmatch(r"\{t\}: add ((?:\{[wubrgc]\})+|one mana of any color)\. spend this mana only to ([^.]+)\.", low)
            if m and vincolo_mana(m.group(2)) is not None:                                       # 106.6 (15 nov 2026): ogni vincolo letto
                car["mana"] = [m.group(1).upper()] if m.group(1).startswith("{") else ["{W}", "{U}", "{B}", "{R}", "{G}"]
                car["mana_vincolo"] = vincolo_mana(m.group(2))
                i = j; continue
            m = re.fullmatch(r"\{t\}: add (one mana of any color|(?:\{[wubrgc]\})+)\. activate only if ([^.]+)\.", low)
            if m and cond_statica(m.group(2)) is not None:                                         # 605.1a, 602.5b, 611.3a (14 nov 2026):
                car.setdefault("mana_cond", []).append({                                           # il mana con una condizione qualsiasi
                    "mana": ["{W}", "{U}", "{B}", "{R}", "{G}"] if m.group(1).startswith("one") else [m.group(1).upper()],
                    "se": {"statica": cond_statica(m.group(2))}})
                i = j; continue
            ab = attivata(orig, low, ctx)
            if ab == "mana" and low.split(":")[0].strip() != "{t}":                                # 605.1a: con altri costi
                eff_ = low.split(":", 1)[1].strip()
                mq = re.fullmatch(r"add (one mana of any color|(?:\{[wubrgc]\})+)\.", eff_)
                if not mq or low.startswith("exhaust"): raise Mancante("abilita' di mana con altri costi")
                costo_ = costo_attivato(orig.split(":")[0].replace(ctx.nome, "~"))
                if costo_.pop("_zona", None): raise Mancante("abilita' di mana da un'altra zona")
                car["abilita"].append({"tipo": "attivata", "costo": costo_, "velocita": "istantanea", "di_mana": True,
                                       "fa": [{"fa": "aggiungi_mana", "mana": "qualsiasi" if mq.group(1).startswith("one") else mq.group(1).upper()}]})
                i = j; continue
            if ab == "mana":
                mt = re.findall(r"\{[wubrgc]\}", low.split(":", 1)[1])
                if "{t}" not in low.split(":")[0] or low.split(":")[0].strip() != "{t}": raise Mancante("abilita' di mana con altri costi")
                car["mana"] = [x.upper() for x in mt] if " or " in low else ["".join(x.upper() for x in mt)]
                i = j; continue
            if ab is not None:
                car["abilita"] += ab; i = j; continue
            ab = statica(low, ctx)
            if isinstance(ab, tuple) and ab[0] == "costo_mod":
                car.setdefault("costo_mod", []).append(ab[1]); i = j; continue
            if isinstance(ab, tuple) and ab[0] == "lancio_solo_se":
                car["lancio_solo_se"] = ab[1]; i = j; continue
            if ab in ("non_stappa", "attacca_se_guardato"):
                car[ab] = True; i = j; continue
            if isinstance(ab, list) and "blocca_stap" in ab:
                car["blocca_stap"] = True; ab = [x for x in ab if x != "blocca_stap"]
            if isinstance(ab, list) and "mai_stappa" in ab:
                car["mai_stappa"] = True; ab = [x for x in ab if x != "mai_stappa"]
            if ab is not None:
                car["abilita"] += ab; i = j; continue
            if low == "a deck can have any number of cards named ~.":
                car["copie_libere"] = True; i = j; continue                                          # 100.2a: solo la costruzione del mazzo
            kk_ = kicker(low)
            if kk_ is not None: car["facoltativo"] = kk_; i = j; continue                         # 702.33a (14 nov 2026)
            ca_ = costo_aggiuntivo(low)
            if ca_ is not None and not spell: car["costo_aggiuntivo"] = ca_; i = j; continue       # 601.2b: anche un permanente
            m = re.fullmatch(r"if (?:this creature|~) was kicked, it enters with (a|two|three) \+1/\+1 counters? on it\.", low)
            if m: car.setdefault("entra", {})["segnalini_se_facoltativo"] = {"+1/+1": numero(m.group(1))}; i = j; continue   # 702.33d, 614.1c
            m = re.fullmatch(r"cycling (\{[^}]+\}(?:\{[^}]+\})*)", low)
            if m:                                                                                # 702.29a (14 nov 2026)
                car["abilita"].append({"tipo": "attivata", "zona": "mano", "costo": {"mana": m.group(1).upper(), "scarta_se": True},
                                       "velocita": "istantanea", "fa": [{"fa": "pesca", "n": 1}]})
                i = j; continue
            m = re.fullmatch(r"(plains|island|swamp|mountain|forest)cycling (\{[^}]+\}(?:\{[^}]+\})*)", low)
            if m:                                                                                # 702.29e: typecycling
                car["abilita"].append({"tipo": "attivata", "zona": "mano", "costo": {"mana": m.group(2).upper(), "scarta_se": True},
                                       "velocita": "istantanea", "fa": [{"fa": "cerca", "tipo": [m.group(1).capitalize()], "dove": "mano"}]})
                i = j; continue
            m = re.fullmatch(r"basic landcycling (\{[^}]+\}(?:\{[^}]+\})*)", low)
            if m:                                                                                # 702.29e
                car["abilita"].append({"tipo": "attivata", "zona": "mano", "costo": {"mana": m.group(1).upper(), "scarta_se": True},
                                       "velocita": "istantanea", "fa": [{"fa": "cerca", "tipo": ["Basic", "Land"], "dove": "mano"}]})
                i = j; continue
            m = re.fullmatch(r"flashback[ —](\{[^}]+\}(?:\{[^}]+\})*)(, discard a card\.)?", low)
            if m and spell:                                                                      # 702.34a
                car["flashback"] = m.group(1).upper()
                if m.group(2): car["flashback_scarta"] = True
                i = j; continue
            sg_ = statica_generica(low)                                                            # 611.3a (15 nov 2026): l'ultimo tentativo
            if sg_ is not None: car["abilita"] += sg_; i = j; continue
            raise Mancante("nessun modello")
        except Mancante as e:
            mancanti.append((orig, str(e)))
            i = j
    if spell:
        if prog_spell["fa"]: car["fa"], car["bersagli"] = prog_spell["fa"], prog_spell["bersagli"]
        if not car.get("fa") and not car.get("modi"): car["fa"] = []
        if not car.get("bersagli"): car.pop("bersagli", None)
    if car.get("capitoli") and "read ahead" not in car["parole"]:                               # 715.3a: entra con un segnalino lore
        car.setdefault("entra", {}).setdefault("segnalini", {})["lore"] = 1
    if AGGANCIO_FINE is not None and POSTO is not None:                                            # il set rifinisce la carta (14 nov 2026)
        motivo_ = AGGANCIO_FINE(POSTO, car)
        if motivo_: mancanti.append(("", motivo_))
    if not car["abilita"]: car.pop("abilita")
    tipo_riga = tipo.replace("Basic Land", "Basic Land")
    if tipo.startswith("Basic Land"):
        car.pop("mana", None)                                        # 305.6: la terra base da' il suo colore
    return Traduzione(nome, (nome, tipo_riga, car), mancanti, c)


_TUTTE = None


def tutte():
    global _TUTTE
    if _TUTTE is None:
        _TUTTE = {}
        for c in json.load(open(FONTE, encoding="utf-8")):
            t = traduci(c)
            _TUTTE[t.nome] = t
            if c["name"] != t.nome: _TUTTE[c["name"]] = t                                          # «Nome // Magia preparata»
    return _TUTTE


def mazzo(nomi, rifiuta_mancanti=True):
    """Una lista di nomi -> il mazzo per il Tavolo. Una carta con abilita' mancanti esce NonCoperto."""
    T = tutte()
    out = []
    for n in nomi:
        if n not in T: raise NonCoperto(f"{n}: non e' fra le carte di FRA")
        t = T[n]
        if t.mancanti and rifiuta_mancanti: raise NonCoperto(f"{n}: {t.mancanti[0][1]} ({t.mancanti[0][0][:60]})")
        out.append(t.voce)
    return out


def copertura(stampa=True, solo=None):
    T = tutte()
    nomi = sorted({T[n].nome for n in T if solo is None or n in solo})
    intere = [n for n in nomi if T[n].intera]
    motivi = Counter(m.split(" ")[0] if not m.startswith("723") else "723.3c" for n in nomi for _, m in T[n].mancanti)
    if stampa:
        print(f"{len(intere)} carte su {len(nomi)} intere")
        for k, v in motivi.most_common(15): print(f"  {v:4} {k}")
    return intere, nomi


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv:
        import prove_carte_fra
        sys.exit(prove_carte_fra.prova())
    nomi = [a for a in sys.argv[1:] if not a.startswith("--")]
    if nomi:
        for n in nomi:
            t = tutte().get(n)
            if t is None: print(f"{n}: non trovata"); continue
            print(json.dumps(t.voce, ensure_ascii=False, indent=1))
            for p, m in t.mancanti: print(f"MANCA: {m} | {p}")
    else:
        copertura()
