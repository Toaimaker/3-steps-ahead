"""I testi di Arena che servono al replayer (14 nov 2026, il censimento: «le scelte fatte», «le abilita' date che non sono parole chiave»): il testo di
un'abilita' dal suo grpId, i nomi dei sottotipi (tipi di creatura e di terra) e dei colori, una stringa per LocId. Letti in sola lettura dal database
delle carte di Arena (Raw_CardDatabase_*.mtga, trovato da primo_avvio.db_locale), una volta per processo; senza database ogni funzione da' None.

  py -I -X utf8 Companion/App/Schede/Performance/testi_arena.py --prova"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import re  # noqa: E402
import sqlite3  # noqa: E402
import threading  # noqa: E402

_CON, _LOCK, _CACHE = [None], threading.Lock(), {}

# le scelte di Arena (ChoiceResult): il dominio dice cosa e' Choice_Value, dedotto dalle carte che le fanno (14 nov 2026): 5 tipo di creatura (Cavern of
# Souls), 9 tipo di terra base (Multiversal Passage), 6 colore (Loot, the Nexus), 11 e 13 un testo (Sorcerous Spyglass: il nome di una carta), senza
# dominio un testo quando il valore e' un LocId (la modalita' di Windcrag Siege: «Jeskai»)
DOMINI = {5: "SubType", 9: "SubType", 6: "Color"}


def _con():
    if _CON[0] is None:
        try:
            import primo_avvio
            f = primo_avvio.db_locale()
            _CON[0] = sqlite3.connect(f"file:{f}?mode=ro", uri=True, check_same_thread=False) if f else False
        except Exception:      # noqa: BLE001 - senza database niente testi
            _CON[0] = False
    return _CON[0] or None


def _uno(sql, args):
    k = (sql, args)
    if k not in _CACHE:
        con = _con()
        r = None
        if con is not None:
            with _LOCK:
                try:
                    r = con.execute(sql, args).fetchone()
                except sqlite3.Error:
                    r = None
        _CACHE[k] = r
    return _CACHE[k]


def loc(i):
    """La stringa inglese di un LocId, senza i segni di formato di Arena."""
    if not isinstance(i, int) or i <= 0:
        return None
    r = _uno("select Loc from Localizations_enUS where LocId=?", (i,))
    return pulisci(r[0]) if r and r[0] else None


def pulisci(t):
    """{oR} -> {R}, CARDNAME -> it, i tag <...> via."""
    t = re.sub(r"\{o([^}]*)\}", r"{\1}", t)
    t = re.sub(r"<[^>]+>", "", t)
    return t.replace("CARDNAME", "it").strip()


def abilita(g):
    """Il testo di un'abilita' dal suo grpId (Abilities.TextId)."""
    r = _uno("select TextId from Abilities where Id=?", (g,))
    return loc(r[0]) if r else None


def enum(tipo, v):
    r = _uno("select LocId from Enums where Type=? and Value=?", (tipo, v))
    return loc(r[0]) if r else None


def scelta(dominio, valore):
    """Il testo di una scelta (ChoiceResult): il tipo, il colore o il testo; None se non si sa leggere (una scelta di oggetti, -1)."""
    if valore is None or valore < 0:
        return None
    if dominio in DOMINI:
        return enum(DOMINI[dominio], valore)
    if dominio in (11, 13) or (dominio is None and valore >= 1000):
        return loc(valore)
    return None


def prova():
    casi = []
    if _con() is None:
        print("SALTATA: il database di Arena non c'e' su questo PC")
        return True
    casi.append(("il tipo di creatura (Cavern of Souls)", scelta(5, 34) == "Goblin"))
    casi.append(("il tipo di terra (Multiversal Passage)", scelta(9, 49) == "Mountain"))
    casi.append(("il colore", scelta(6, 4) == "Red"))
    casi.append(("la modalita' (Windcrag Siege)", scelta(None, 927587) == "Jeskai"))
    casi.append(("il testo di un'abilita', coi simboli puliti", abilita(208385) == "Add {R}."))
    casi.append(("negativa: una scelta di oggetti (-1) e un valore piccolo senza dominio non si leggono", scelta(None, -1) is None and scelta(None, 394) is None))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(ok for _, ok in casi)}/{len(casi)}")
    return all(ok for _, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
