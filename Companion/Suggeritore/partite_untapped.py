"""Le partite da Untapped, nell'app pubblica: solo se l'utente ha collegato il suo profilo pubblico (account.py). Sostituisce
Companion/Suggeritore/partite_untapped.py del progetto di Autore, che ha i suoi id scritti dentro. Stesse funzioni e stesse costanti."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import percorsi  # noqa: E401,E702
import json, re, ssl, urllib.request  # noqa: E401
import account

ROOT = percorsi.ROOT
USER = PLAYER = ""


def _rinfresca():
    """Il profilo di Untapped dell'account mostrato: si rifa' quando cambia l'account (account.al_cambio, 10 nov 2026)."""
    global USER, PLAYER
    a = account.account()
    USER, PLAYER = a.get("untapped_user") or "", a.get("untapped_player") or ""


_rinfresca()
account.al_cambio(_rinfresca)
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = None


def ultimi_set(n=4):
    import datetime
    entro = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
    try:
        testo = open(os.path.join(ROOT, "Regole", "Set_Legali.md"), encoding="utf-8").read()
    except OSError:
        return []
    righe = re.findall(r"^\| [^|]+ \| ([A-Z0-9]+) \| (\d{4}-\d{2}-\d{2}) \| (\d+) \|", testo, re.M)
    return [c for c, d, k in sorted(righe, key=lambda r: r[1]) if int(k) >= 100 and d <= entro][-n:]


def partite(n_set=4):
    if not (USER and PLAYER):
        return []
    visti, out = set(), []
    for s in ultimi_set(n_set):
        u = f"https://api.mtga.untapped.gg/api/v1/games/users/{USER}/players/{PLAYER}/?card_set={s}"
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "companion-magic-arena/1.0", "Accept": "application/json"}), timeout=60, context=CTX))
        except Exception:
            continue
        for g in (j if isinstance(j, list) else (j.get("results") or j.get("games") or []) if isinstance(j, dict) else []):
            k = g.get("short_id") or (g.get("match_start"), g.get("friendly_deck_id"))
            if k not in visti:
                visti.add(k); out.append(g)
    return sorted(out, key=lambda g: g.get("match_start") or 0)
