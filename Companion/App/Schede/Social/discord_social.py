"""Sign in with Discord e gli amici online, nella colonna social (10 nov 2026, sessione Magic 12; Autore: «fai in modo che la barra social sia collegata agli
account discord in modo che chi e' loggato possa vedere amici loggati e raggiungerli su discord / in testa a tutto metti il discord con pulsante di accesso», poi
«vai con la 1»: il server vero).

Il server e' Distribuzione/server_social (Cloudflare Worker con un database D1): tiene il segreto dell'applicazione Discord, che non puo' stare in un'app che si
scarica. Il suo indirizzo sta in discord.json («server»); vuoto, l'accesso non c'e' e la colonna lo dice. Il giro:
1. accedi: l'app sceglie uno «state» casuale e apre nel browser <server>/login?state=..., che rimanda all'autorizzazione di Discord (scope identify: id, nome,
   avatar; niente email, niente amici, niente server);
2. Discord rimanda al server, che scambia il codice col segreto, legge chi sei e prepara una sessione sotto quello state;
3. l'app chiede <server>/session?state=... ogni 2 s finche' la sessione c'e' (al massimo 3 minuti), e la tiene in discord_sessione.json, uno per account di Arena
   (account.lega: due persone sullo stesso PC hanno ognuna il suo Discord);
4. collega l'account di Arena mostrato: manda lo SHA-256 del suo id, e il server lo tiene come HMAC col suo segreto; un account di Arena va a un Discord solo
   (Distribuzione/LEGGIMI.md, «Sign in with Discord: lo schema»);
5. ogni 2 minuti un battito (sei online finche' l'app e' aperta, il server conta 5 minuti) e la lista degli amici.
Gli amici si aggiungono col nome utente di Discord, e solo chi ha gia' fatto l'accesso dall'app. Online si vede solo fra amici reciproci: se aggiungi qualcuno
che non ti ha aggiunto, aspetti che lo faccia. «Message» apre il suo profilo su Discord (discord.com/users/<id>), da cui gli scrivi.

    py -I -X utf8 Companion/App/Schede/Social/discord_social.py --prova     un server finto in locale: accesso, Arena, amici, online, uscita, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import hashlib  # noqa: E402
import json  # noqa: E402
import secrets  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402

import account as _ACC  # noqa: E402

QUI = os.path.dirname(os.path.abspath(__file__))
CONF = [os.path.join(QUI, "discord.json")]
SESSIONE = _ACC.lega(globals(), "SESSIONE", "discord_sessione.json")     # la sessione di Discord dell'account di Arena mostrato
AGENTE = "3-steps-ahead/1.0"


def conf():
    try:
        with open(CONF[0], encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def server():
    """L'indirizzo del server, o "" se non c'e' ancora (solo https, o http su questo PC per le prove)."""
    s = (conf().get("server") or "").strip().rstrip("/")
    return s if s.startswith("https://") or s.startswith("http://127.0.0.1") else ""


def invito():
    return conf().get("invito") or ""


def sessione():
    try:
        with open(SESSIONE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("token") else {}
    except (OSError, ValueError):
        return {}


def _salva(d):
    if _ACC.sola_lettura():       # All accounts: niente accessi, si sceglie un account
        return
    os.makedirs(os.path.dirname(SESSIONE), exist_ok=True)
    with open(SESSIONE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(SESSIONE + ".tmp", SESSIONE)


def _cancella():
    try:
        os.remove(SESSIONE)
    except OSError:
        pass


def chiama(percorso, corpo=None, metodo="POST", token=None, timeout=15):
    """-> (codice HTTP, dict). Un errore di rete -> (0, {"error": ...})."""
    s = server()
    if not s:
        return 0, {"error": "no server"}
    dati = json.dumps(corpo or {}).encode() if metodo == "POST" else None
    req = urllib.request.Request(s + percorso, data=dati, method=metodo, headers={"User-Agent": AGENTE, "Content-Type": "application/json", "Accept": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}
    except (OSError, ValueError) as e:
        return 0, {"error": str(e)}


def inizia():
    """-> (state, indirizzo da aprire nel browser), o (None, None) senza server o con All accounts."""
    if not server() or _ACC.sola_lettura():
        return None, None
    st = secrets.token_hex(16)
    return st, server() + "/login?" + urllib.parse.urlencode({"state": st})


def attendi(state, timeout=180, ogni=2.0, fermo=lambda: False):
    """Aspetta che l'accesso nel browser finisca. -> la sessione {token, user}, o None (scaduto, annullato)."""
    fine = time.time() + timeout
    while time.time() < fine and not fermo():
        c, d = chiama("/session?" + urllib.parse.urlencode({"state": state}), metodo="GET")
        if c == 200 and d.get("token"):
            s = dict(token=d["token"], user=d.get("user") or {}, quando=int(time.time()))
            _salva(s)
            return s
        time.sleep(ogni)
    return None


def codice_arena(i=None):
    """Lo SHA-256 dell'id dell'account di Arena (il server lo rifa' HMAC col suo segreto): l'id non esce dal PC."""
    i = i or _ACC.attivo()
    return hashlib.sha256(i.encode()).hexdigest() if i else None


def collega_arena():
    """Collega l'account di Arena mostrato al Discord della sessione. -> (ok, messaggio)."""
    s, a = sessione(), codice_arena()
    if not s or not a:
        return False, "Choose one Arena account first" if not a else "Sign in first"
    c, d = chiama("/arena", {"arena": a}, token=s["token"])
    if c == 401:
        _cancella()
    if c == 409:
        return False, "This Arena account is linked to another Discord"
    return c == 200, "" if c == 200 else (d.get("error") or "Server not reachable")


def esci():
    """Scollega l'account di Arena, chiude la sessione sul server e la dimentica qui."""
    s, a = sessione(), codice_arena()
    if s:
        if a:
            chiama("/arena/remove", {"arena": a}, token=s["token"])
        chiama("/logout", token=s["token"])
    _cancella()


def battito():
    """Sei online. -> il tuo profilo, o None (fuori; una sessione che il server non conosce piu' si dimentica)."""
    s = sessione()
    if not s:
        return None
    c, d = chiama("/heartbeat", token=s["token"])
    if c == 401:
        _cancella()
        return None
    if c == 200 and d.get("user"):
        s["user"] = d["user"]
        _salva(s)
        return d["user"]
    return s.get("user")


def amici():
    """-> [dict(id, username, name, avatar, online, mutual)], o None se non si sa (fuori, server che non risponde)."""
    s = sessione()
    if not s:
        return None
    c, d = chiama("/friends", token=s["token"])
    if c == 401:
        _cancella()
    return d.get("friends") if c == 200 else None


def aggiungi(nome):
    """Un amico col nome utente di Discord. -> (ok, messaggio)."""
    s = sessione()
    nome = (nome or "").strip().lstrip("@")
    if not s or not nome:
        return False, "Write a Discord username" if s else "Sign in first"
    c, d = chiama("/friends/add", {"username": nome}, token=s["token"])
    if c == 200:
        return True, ""
    return False, {404: f"{nome} hasn't signed in from the app yet", 400: d.get("error") or "Not valid", 0: "Server not reachable"}.get(c, d.get("error") or "Not added")


def togli(id_):
    s = sessione()
    if s:
        chiama("/friends/remove", {"id": id_}, token=s["token"])


def profilo_url(id_):
    """Il profilo Discord di un amico: da li' gli scrivi (siete tutti nel server 3StepAhead)."""
    return f"https://discord.com/users/{id_}"


# ------------------------------------------------------------------ la prova: un server finto che fa quello che fa il Worker
def server_finto():
    """Il protocollo di Distribuzione/server_social/worker.js, in memoria, con Discord finto: /login fa subito l'accesso dell'utente scritto in UTENTI[state]."""
    import http.server
    import threading
    stato = dict(utenti={}, sessioni={}, attese={}, arena={}, amici=set(), visto={}, prossimo={})
    ONLINE = 300

    def pubblico(uid):
        u = stato["utenti"][uid]
        return dict(id=uid, username=u["username"], name=u["username"], avatar=None, online=time.time() - stato["visto"].get(uid, 0) < ONLINE, seen=stato["visto"].get(uid, 0))

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def manda(self, codice, d):
            b = json.dumps(d).encode()
            self.send_response(codice); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            if u.path == "/login":        # Discord finto: accede subito chi la prova ha messo in «prossimo»
                uid, nome = stato["prossimo"].pop("x")
                stato["utenti"][uid] = dict(username=nome); stato["visto"][uid] = time.time()
                t = secrets.token_hex(16)
                stato["sessioni"][t] = uid; stato["attese"][q["state"]] = t
                return self.manda(200, {"page": "signed in"})
            if u.path == "/session":
                t = stato["attese"].pop(q.get("state"), None)
                return self.manda(200, dict(token=t, user=pubblico(stato["sessioni"][t]))) if t else self.manda(404, {"pending": True})
            return self.manda(404, {})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            corpo = json.loads(self.rfile.read(n) or b"{}")
            t = (self.headers.get("Authorization") or "")[7:]
            uid = stato["sessioni"].get(t)
            if not uid:
                return self.manda(401, {"error": "signed out"})
            p = self.path
            if p == "/heartbeat":
                stato["visto"][uid] = time.time(); return self.manda(200, dict(user=pubblico(uid)))
            if p == "/arena":
                h = hashlib.sha256(("sale|" + corpo["arena"]).encode()).hexdigest()
                if stato["arena"].get(h, uid) != uid:
                    return self.manda(409, {"error": "linked to another Discord"})
                stato["arena"][h] = uid; return self.manda(200, {"ok": True})
            if p == "/arena/remove":
                h = hashlib.sha256(("sale|" + corpo["arena"]).encode()).hexdigest()
                if stato["arena"].get(h) == uid:
                    del stato["arena"][h]
                return self.manda(200, {"ok": True})
            if p == "/friends":
                out = []
                for a, b in sorted(stato["amici"]):
                    if a == uid:
                        f = pubblico(b); f["mutual"] = (b, a) in stato["amici"]; f["online"] = f["online"] and f["mutual"]
                        out.append(f)
                return self.manda(200, {"friends": out})
            if p == "/friends/add":
                f = next((i for i, x in stato["utenti"].items() if x["username"].lower() == corpo.get("username", "").lower()), None)
                if not f:
                    return self.manda(404, {"error": "not using the app yet"})
                if f == uid:
                    return self.manda(400, {"error": "that's you"})
                stato["amici"].add((uid, f)); return self.manda(200, {"friend": pubblico(f)})
            if p == "/friends/remove":
                stato["amici"].discard((uid, corpo.get("id"))); return self.manda(200, {"ok": True})
            if p == "/logout":
                stato["sessioni"].pop(t, None); return self.manda(200, {"ok": True})
            return self.manda(404, {})

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, stato


def prova():
    import tempfile
    d = tempfile.mkdtemp()
    srv, stato = server_finto()
    vero = (CONF[0], globals()["SESSIONE"], _ACC.PUBBLICA, _ACC.FILE[0], _ACC.CONTI[0], _ACC.LOGDIR, list(_ACC.VIVI), list(_ACC._LEGATI))
    casi = []
    A, B = "AAAA1111BBBB2222CCCC3333DD", "ZZZZ1111BBBB2222CCCC3333DD"
    try:
        CONF[0] = os.path.join(d, "discord.json")
        json.dump({"server": ""}, open(CONF[0], "w"))
        globals()["SESSIONE"] = os.path.join(d, "sessione_a.json")
        casi.append(("senza server l'accesso non c'e'", inizia() == (None, None) and not sessione()))
        json.dump({"server": f"http://127.0.0.1:{srv.server_port}"}, open(CONF[0], "w"))
        ora_a = lambda: _ACC.attivo()
        # l'app pubblica con l'account A di Arena (tutto in d, mai Log_Arena)
        _ACC.PUBBLICA, _ACC.LOGDIR = True, d
        _ACC.FILE[0], _ACC.CONTI[0] = os.path.join(d, "utente.json"), os.path.join(d, "conti")
        vivo = os.path.join(d, "Player.log")
        open(vivo, "w").write('{ "authenticateResponse": { "clientId": "%s", "sessionId": "s", "screenName":"Prima" } }\n' % A)
        _ACC.VIVI[:] = [vivo]; _ACC._LEGATI[:] = [(globals(), "SESSIONE", "discord_sessione.json", None)]
        _ACC._C.clear(); _ACC._L.clear(); _ACC.aggiorna(); _ACC.applica()

        def entra(uid, nome):
            stato["prossimo"]["x"] = (uid, nome)
            st, url = inizia()
            urllib.request.urlopen(url).read()          # il browser: Discord finto accede subito
            return attendi(st, timeout=5, ogni=0.1)
        s = entra("111", "autore")
        casi.append(("l'accesso: la sessione e l'utente, nella cartella dell'account di Arena", s and s["user"]["username"] == "autore"
                     and sessione()["token"] == s["token"] and SESSIONE.endswith(os.path.join(A, "discord_sessione.json")) and ora_a() == A))
        casi.append(("l'account di Arena si collega, e l'id non esce dal PC", collega_arena()[0] and len(stato["arena"]) == 1 and A not in json.dumps(stato["arena"])))
        casi.append(("negativa: un amico che non ha fatto l'accesso non si aggiunge", aggiungi("marco") == (False, "marco hasn't signed in from the app yet")))
        # la seconda persona sullo stesso PC: l'account B di Arena, il suo Discord
        open(vivo, "a").write('{ "authenticateResponse": { "clientId": "%s", "sessionId": "s", "screenName":"Seconda" } }\n' % B)
        _ACC.aggiorna(); _ACC.applica()
        casi.append(("l'altro account di Arena non ha la sessione del primo", not sessione() and ora_a() == B))
        entra("222", "marco")
        collega_arena()
        casi.append(("e si collega col suo Discord", sessione()["user"]["username"] == "marco" and len(stato["arena"]) == 2))
        ok_m, _ = aggiungi("autore")
        a_m = amici()
        casi.append(("marco aggiunge autore: non reciproco, quindi non si vede online", ok_m and len(a_m) == 1 and a_m[0]["online"] is False and a_m[0]["mutual"] is False))
        # di nuovo A: autore aggiunge marco, ora sono reciproci
        _ACC.scegli(A)
        aggiungi("marco"); battito()
        a_f = amici()
        casi.append(("reciproci: marco e' online (ha fatto il battito da poco)", a_f[0]["username"] == "marco" and a_f[0]["online"] is True and a_f[0]["mutual"] is True))
        casi.append(("Message apre il profilo Discord", profilo_url(a_f[0]["id"]) == "https://discord.com/users/222"))
        # negativa: l'account A di Arena non si collega a un secondo Discord
        tok_f = sessione()["token"]
        entra("333", "intruso")
        casi.append(("negativa: un account di Arena gia' collegato non va a un altro Discord", collega_arena() == (False, "This Arena account is linked to another Discord")))
        _salva(dict(token=tok_f, user={"username": "autore"}))
        stato["sessioni"].pop(tok_f)
        casi.append(("una sessione che il server non conosce piu' si dimentica", battito() is None and not sessione()))
        entra("111", "autore"); collega_arena()
        esci()
        casi.append(("Sign out: sessione chiusa e account di Arena scollegato", not sessione() and len(stato["arena"]) == 1))
        _ACC.scegli(_ACC.TUTTI)
        casi.append(("All accounts: niente accesso", inizia() == (None, None)))
    finally:
        CONF[0], globals()["SESSIONE"] = vero[0], vero[1]
        _ACC.PUBBLICA, _ACC.FILE[0], _ACC.CONTI[0], _ACC.LOGDIR = vero[2], vero[3], vero[4], vero[5]
        _ACC.VIVI[:], _ACC._LEGATI[:] = vero[6], vero[7]
        _ACC._C.clear(); _ACC._L.clear()
        srv.shutdown()
    for n, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + n)
    n = sum(1 for _n, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return n == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print("server:", server() or "-", "| sessione:", (sessione().get("user") or {}).get("username", "-"))
