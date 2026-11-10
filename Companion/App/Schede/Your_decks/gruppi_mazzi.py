"""I gruppi a tendina di Your decks: i nomi dei formati, l'ordine, i gruppi chiusi (Log_Arena/mazzi_gruppi.json)."""
import json
import os

from ambiente import LOGDIR


NOMI_FORMATO = {"TraditionalStandard": "Standard Bo3", "TraditionalExplorer": "Explorer Bo3", "TraditionalHistoric": "Historic Bo3", "TraditionalAlchemy": "Alchemy Bo3",
                "TraditionalTimeless": "Timeless Bo3", "HistoricBrawl": "Brawl", "StandardBrawl": "Standard Brawl", "DirectGameLimited": "Limited", "": "Other"}
ORDINE_FORMATI = ("Standard", "Standard Bo3", "Alchemy", "Alchemy Bo3", "Explorer", "Explorer Bo3", "Historic", "Historic Bo3", "Timeless", "Timeless Bo3", "Brawl", "Standard Brawl",
                  "Gladiator", "Pioneer", "Modern", "Legacy", "Vintage", "Pauper")
GRUPPI_FILE = os.path.join(LOGDIR, "mazzi_gruppi.json")
GRUPPI_CHIUSI = set()
try:
    with open(GRUPPI_FILE, encoding="utf-8") as _f:
        GRUPPI_CHIUSI.update(json.load(_f))
except (OSError, ValueError):
    pass


def salva_gruppi():
    """I gruppi chiusi, per questo PC (fuori da git): una comodita', se il file manca si riparte coi gruppi aperti."""
    try:
        with open(GRUPPI_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(GRUPPI_CHIUSI), f)
    except OSError:
        pass


def nome_formato(f):
    """Il formato di Arena (TraditionalStandard, HistoricBrawl...) col nome che si legge."""
    f = (f or "").strip()
    return NOMI_FORMATO.get(f, f or "Other")


def ordine_formato(g):
    if g == "Arena decks":         # prima della wishlist (9 nov 2026)
        return (2, -1, "")
    if g == "Wishlist":
        return (2, 0, "")
    if g == "Deck building":       # sotto la wishlist (9 nov 2026)
        return (2, 1, "")
    return (0, ORDINE_FORMATI.index(g), "") if g in ORDINE_FORMATI else (1, 0, g)


def MS_dict(m):
    """Il mazzo salvato come lo vuole la finestra: i campi del file, senza quelli della scheda."""
    return {k: v for k, v in m.items() if k not in ("main", "tot", "own", "manca", "eur", "cambio", "arte", "salvato", "_sez", "_gruppo", "n", "w", "prima", "ultima")}
