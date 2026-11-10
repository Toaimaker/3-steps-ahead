"""Il profilo e gli amici della colonna a destra (Autore, 6 nov 2026: «possiamo costruire sulla destra un impianto social col profilo giocatore immagine profilo e amici da aggiungere?»).

Arena non scrive gli amici nel Player.log, quindi un amico si aggiunge col link del suo profilo pubblico di Untapped: mtga.untapped.gg/profile/<utente>/<giocatore>. Si leggono solo le sue
partite (API pubblica, la stessa di partite_untapped.py, gli ultimi 2 periodi di set), mai la collezione, che ha anche oro e gemme. Le partite di Untapped non dicono il nome del giocatore:
lo scrive chi aggiunge l'amico. Nessuno dei due sa dell'altro: e' un «segui», non una richiesta di amicizia. Online non si sa: «recente» vuol dire una partita nelle ultime 24 ore.

Sta tutto in Log_Arena (fuori da git): profilo.json, amici.json, profilo_avatar.png.

    py -I -X utf8 Companion/App/Schede/Social/social.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json, re, time, urllib.request

LOGDIR = os.path.join(percorsi.ROOT, "Log_Arena")
import account as _ACC  # noqa: E402
for _n in ("profilo.json", "amici.json", "profilo_avatar.png"):         # nell'app pubblica il profilo e gli amici sono dell'account (10 nov 2026, Magic 12)
    _ACC.lega({}, "_", _n)


def cartella():
    """Dove stanno profilo e amici: Log_Arena nell'app di Autore; nell'app pubblica la cartella dell'account mostrato (con All accounts, dell'ultimo entrato
    in Arena)."""
    if not _ACC.PUBBLICA:
        return LOGDIR
    return _ACC.cartella(_ACC.attivo() or _ACC.leggi().get("ultimo"))
VECCHIO = 6 * 3600       # i dati di un giocatore si rileggono dopo 6 ore
RECENTE = 24 * 3600
LINK = re.compile(r"^\s*(?:https?://)?(?:www\.)?mtga\.untapped\.gg/profile/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/([A-Z0-9]{8,64})/?(?:[?#]\S*)?\s*$", re.I)
LIMITED = re.compile(r"Draft|Sealed|Cube", re.I)


def leggi_link(testo):
    """(utente, giocatore) da un link di profilo di Untapped, o None: nient'altro entra nelle richieste."""
    m = LINK.match(testo or "")
    return (m.group(1).lower(), m.group(2).upper()) if m else None


def url_profilo(v):
    return f"https://mtga.untapped.gg/profile/{v['user']}/{v['player']}"


def partite_di(user, player, n_set=2):
    """Le partite pubbliche degli ultimi n periodi di set. Un profilo privato o sparito solleva l'errore della richiesta."""
    from partite_untapped import CTX, ultimi_set      # qui e non in testa: all'import legge i certificati, 150 ms sull'avvio della finestra
    visti, out = set(), []
    for s in ultimi_set(n_set):
        u = f"https://api.mtga.untapped.gg/api/v1/games/users/{user}/players/{player}/?card_set={s}"
        j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "CompanionMagicArena/1.0", "Accept": "application/json"}), timeout=30, context=CTX))
        for g in (j if isinstance(j, list) else j.get("results") or j.get("games") or []):
            k = g.get("short_id") or (g.get("match_start"), g.get("friendly_deck_id"))
            if k not in visti:
                visti.add(k); out.append(g)
    return sorted(out, key=lambda g: g.get("match_start") or 0)


def rango(g):
    c = g.get("friendly_ranking_class_after")
    if not c or c == "None":
        return None
    return c if c == "Mythic" or not g.get("friendly_ranking_tier_after") else f"{c} {g['friendly_ranking_tier_after']}"


def riassumi(partite):
    """-> dict(costruito, limited, wr, partite, ultima): ultima in secondi, wr in % o None."""
    vinte = sum(1 for g in partite if g.get("winning_team_id") == g.get("friendly_team_id"))
    ultimo = lambda prova: next((rango(g) for g in reversed(partite) if prova(g.get("event_name") or "") and rango(g)), None)
    return dict(costruito=ultimo(lambda e: "Ladder" in e), limited=ultimo(lambda e: bool(LIMITED.search(e))), wr=round(100 * vinte / len(partite)) if partite else None,
                partite=len(partite), ultima=(partite[-1].get("match_start") or 0) / 1000 if partite else 0)


def aggiorna(v):
    """Rilegge un giocatore. Una richiesta fallita lascia i dati di prima e segna errore: la colonna lo dice."""
    try:
        v.update(riassumi(partite_di(v["user"], v["player"])), agg=time.time(), errore=False)
    except Exception:
        v.update(agg=time.time(), errore=True)
    return v


def recente(v, ora=None):
    return bool(v.get("ultima")) and (ora or time.time()) - v["ultima"] < RECENTE


def quanto_fa(ts, ora=None):
    """«3h ago», come i tracker. "" senza partite."""
    if not ts:
        return ""
    d = max(0, (ora or time.time()) - ts)
    for sec, s in ((86400 * 30, "mo"), (86400, "d"), (3600, "h"), (60, "m")):
        if d >= sec:
            return f"{int(d // sec)}{s} ago"
    return "now"


def riga_sotto(v):
    """La seconda riga di un amico nell'elenco."""
    if v.get("errore") and not v.get("partite"):
        return "Private or unreachable"
    if not v.get("agg"):
        return "Loading..."
    pezzi = [v.get("costruito") or v.get("limited"), quanto_fa(v.get("ultima"))]      # niente win rate (Autore, 10 nov 2026: «dalla barra social togli il % win rate»)
    return " · ".join(x for x in pezzi if x) or "No recent games"


class Dati:
    """Il profilo e gli amici su disco. cartella: il collaudo ne usa una sua."""

    def __init__(self, cartella=None):
        cartella = cartella or globals()["cartella"]()
        self.f_p, self.f_a = os.path.join(cartella, "profilo.json"), os.path.join(cartella, "amici.json")
        self.avatar = os.path.join(cartella, "profilo_avatar.png")
        self.profilo = self.leggi(self.f_p, None) or self.profilo_nuovo()
        self.amici = self.leggi(self.f_a, [])

    @staticmethod
    def profilo_nuovo():
        import account
        a = account.account()       # Autore, o chi usa l'app pubblica (account.py)
        return dict(nome=a["nome"] or "You", user=a["untapped_user"] or "", player=a["untapped_player"] or "")

    @staticmethod
    def leggi(f, vuoto):
        try:
            return json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            return vuoto

    def salva(self):
        for f, d in ((self.f_p, self.profilo), (self.f_a, self.amici)):
            os.makedirs(os.path.dirname(f), exist_ok=True)      # la cartella di un account nuovo
            t = f + ".tmp"
            json.dump(d, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(t, f)

    def aggiungi(self, nome, link):
        """-> la voce nuova, o il testo dell'errore."""
        nome, ids = (nome or "").strip(), leggi_link(link)
        if not nome:
            return "Write a name"
        if not ids:
            return "Paste a profile link from mtga.untapped.gg"
        if ids == (self.profilo["user"], self.profilo["player"]) or any((v["user"], v["player"]) == ids for v in self.amici):
            return "Already in your list"
        v = dict(nome=nome[:24], user=ids[0], player=ids[1])
        self.amici.append(v)
        self.salva()
        return v

    def togli(self, v):
        self.amici = [x for x in self.amici if x is not v]
        self.salva()

    def da_rileggere(self, ora=None):
        return [v for v in [self.profilo] + self.amici if (ora or time.time()) - v.get("agg", 0) > VECCHIO]


def prova():
    import tempfile
    u, p = "00000000-0000-0000-0000-000000000000", "AAAAAAAAAAAAAAAAAAAAAAAAAA"
    g = lambda ev, c, t, win, ms: dict(event_name=ev, friendly_ranking_class_after=c, friendly_ranking_tier_after=t, winning_team_id=1 if win else 2, friendly_team_id=1, match_start=ms)
    r = riassumi([g("Ladder", "Gold", 2, True, 1000), g("QuickDraft_FRA_1", "Silver", 4, False, 2000), g("Play", None, None, True, 3000)])
    casi = [("un link vero", leggi_link(f"https://mtga.untapped.gg/profile/{u}/{p}") == (u, p)),
            ("anche senza https e con la barra", leggi_link(f" mtga.untapped.gg/profile/{u}/{p}/ ") == (u, p)),
            ("un altro sito no", leggi_link(f"https://evil.example/profile/{u}/{p}") is None and leggi_link(f"https://mtga.untapped.gg.evil.example/profile/{u}/{p}") is None),
            ("niente roba in piu' nel percorso", leggi_link(f"https://mtga.untapped.gg/profile/{u}/{p}/../../x") is None),
            ("un testo qualsiasi no", leggi_link("ciao") is None and leggi_link("") is None and leggi_link(None) is None),
            ("il rango di costruito", r["costruito"] == "Gold 2"), ("il rango di limited", r["limited"] == "Silver 4"),
            ("win rate e partite", r["wr"] == 67 and r["partite"] == 3 and r["ultima"] == 3),
            ("senza partite", riassumi([]) == dict(costruito=None, limited=None, wr=None, partite=0, ultima=0)),
            ("Mythic senza tier", rango(g("Ladder", "Mythic", 0, True, 1)) == "Mythic"),
            ("quanto fa", (quanto_fa(1000, 1000 + 7200), quanto_fa(1000, 1000 + 90000), quanto_fa(1000, 1010), quanto_fa(0)) == ("2h ago", "1d ago", "now", "")),
            ("recente: 24 ore", recente(dict(ultima=1000), 1000 + 3600) and not recente(dict(ultima=1000), 1000 + 90000) and not recente({})),
            ("la riga di un profilo privato", riga_sotto(dict(errore=True, agg=1)) == "Private or unreachable"),
            ("la riga mentre carica", riga_sotto({}) == "Loading..."),
            ("la riga dell'amico, senza win rate", riga_sotto(dict(agg=1, costruito="Gold 2", wr=54, ultima=time.time() - 7200)) == "Gold 2 · 2h ago")]
    with tempfile.TemporaryDirectory() as c:
        d = Dati(c)
        amico = "11111111-2222-3333-4444-555555555555"
        casi.append(("senza nome no", d.aggiungi("", f"mtga.untapped.gg/profile/{amico}/ABCDEFGHIJ") == "Write a name"))
        casi.append(("senza link buono no", "link" in d.aggiungi("Tizio", "http://altro.it")))
        v = d.aggiungi("Tizio", f"mtga.untapped.gg/profile/{amico}/ABCDEFGHIJ")
        casi.append(("si aggiunge", isinstance(v, dict) and Dati(c).amici[0]["nome"] == "Tizio"))
        casi.append(("due volte no", isinstance(d.aggiungi("Caio", f"mtga.untapped.gg/profile/{amico}/ABCDEFGHIJ"), str)))
        casi.append(("se stessi no", isinstance(d.aggiungi("Io", f"mtga.untapped.gg/profile/{u}/{p}"), str)))
        casi.append(("va riletto", len(d.da_rileggere()) == 2))
        aggiorna(v)
        casi.append(("un profilo che non esiste si dice", v["errore"] and riga_sotto(v) == "Private or unreachable" and len(d.da_rileggere()) == 1))
        d.togli(v)
        casi.append(("si toglie", Dati(c).amici == []))
    io = aggiorna(Dati.profilo_nuovo())
    casi.append(("il profilo vero si legge", not io["errore"] and io["partite"] > 0 and io["wr"] is not None))
    print("  profilo:", {k: io.get(k) for k in ("costruito", "limited", "wr", "partite")}, quanto_fa(io.get("ultima")))
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    sys.exit(prova() if "--prova" in sys.argv else 0)
