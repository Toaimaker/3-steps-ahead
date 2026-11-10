"""La chat della partita e dei pick: ogni riga del diario diventa un messaggio."""
import collections
import re
import sys

import ambiente      # NOME_PLAYER si legge a ogni uso: cambia con l'account (10 nov 2026)
from dati_drafter import _PRINCIPALI, _TIPI, voti_carte


SOLO_CLAUDE = "--solo-claude" in sys.argv   # 13 ott 2026 sera: in chat solo le righe CLAUDE, niente consigli automatici


# ---------------------------------------------------------------- il diario del companion -> messaggi

class Partita:
    """Lo stato della partita ricostruito dalle righe del companion. Ogni messaggio e' un dict:
    {tipo: 'sep'|'msg', lato: 'tu'|'lui'|'info', testo, id, barrato, nota}."""

    def __init__(self):
        self.reset("")

    def reset(self, evento):
        self.evento = evento
        self.pack = None
        self.ultimo_pick = None
        self.avversario = ""
        self.vite = None
        self.msg = []
        self.miei_turni = 0
        self.turno = 0          # il turno di Arena, scritto su ogni riga della chat (Autore, 12 ott 2026)
        self.ultimo_lato = None
        self.gioca_id = None
        self.piano = None
        self.esito = None
        self.sue_carte = {}
        self.io = {"mano": {}, "fase": "", "passo": "", "turno": 0, "pw": {}}
        self.suo = {"mano": None, "terre": None, "libere": None, "creature": [], "cimitero": 0, "pronte": [], "viste": [], "kw": {}, "in_mano": []}

    def _sep(self, lato, testo, nome=""):
        self.msg.append(dict(tipo="sep", lato=lato, testo=testo, nome=nome, t=self.turno))
        self.ultimo_lato = lato

    def _m(self, lato, testo, nota="", ico="gioca", lista=None, nel_tuo_turno=False, passo=None):
        if ico == "attacca" and testo.startswith("Attacca con ") and not lista:
            lista = self.con_bersaglio(self.creature(testo[len("Attacca con "):])); testo = "Attacca con"
        if lato == "lui" and self.ultimo_lato != "lui" and not nel_tuo_turno:
            self.turno = (self.turno or 0) + 1            # il suo turno viene dopo il tuo (TURNO e ATTACCO SUO lo correggono)
            self._sep("lui", "Opponent", nome=self.avversario)
        fase_io = self.io.get("fase") if self.io.get("turno") == self.turno else None
        m = dict(tipo="msg", lato=lato, testo=testo, id=len(self.msg), barrato=False, nota=nota, ico=ico, lista=lista or [], t=self.turno, fase_io=fase_io,
                 passo=passo, fatto=False, fase0=None, mano0=None, fed0=None, prep="(preparata)" in testo)
        # il riferimento della carta si prende adesso: la mano dello stato se e' gia' di questo turno, se no quella scritta
        # in TURNO (12 ott 2026, contro merfolkkm: preso dopo la Forest giocata, il passo aspettava una seconda Forest)
        if passo and passo[0] == "carta" and not m["prep"]:
            if self.io["turno"] == self.turno and self.io["mano"]: m["mano0"] = self.io["mano"].get(passo[1], 0)
            else: m["mano0"] = len(re.findall(r"(?:^|, )" + re.escape(passo[1]) + r"(?=,|$)", getattr(self, "mano_turno", "") or ""))
            m["fase0"] = "Main1"
            if not m["mano0"]: m["fatto"] = True
        self.msg.append(m)
        return m["id"]

    def con_bersaglio(self, nomi):
        if not self.bers:
            return nomi
        resto = list(self.bers); out = []
        for n in nomi:
            k = next((i for i, (a, _) in enumerate(resto) if a == n), None)
            out.append(f"{n}  →  {resto.pop(k)[1]}" if k is not None else n)
        return out

    TERRE_BASE = ("Plains", "Island", "Swamp", "Mountain", "Forest")

    def passo_piano(self, x, dopo=False):
        """Un passo del piano del turno -> (testo, nota, ico, passo). Autore, 13 ott 2026: «ogni azione deve avere una
        riga»; 8-9 ott: un gesto per riga col nome della carta, niente perche'."""
        x = x.strip()
        if x.startswith("attacca con "):
            return f"Attacca con {x[12:]}", "", "attacca", ("attacco",)
        if x in ("nessun attacco", "niente attacco"):
            return "Non attaccare", "", "difendi", None
        m = re.match(r"(.+?) \[([+−-]\d+)\]: (.+)", x)                        # Jace [-1]: Surveil 1
        if m:
            nome = m.group(1).replace(" (pedina)", "").strip()
            return f"{nome} {m.group(2).replace('-', '−')}: {m.group(3)}", "", "pw", ("pw", nome)
        m = re.match(r"attiva (.+?) (\{[^}]*\}(?:\{[^}]*\})*)\s*:?\s*(.*)", x)  # attiva Inspired Tethermage {6}: effetto
        if m:
            costo = len(re.findall(r"\{", m.group(2))) and sum(int(c) if c.isdigit() else 1 for c in re.findall(r"\{([^}]*)\}", m.group(2)))
            return f"Attiva {m.group(1)} ({costo} mana)", m.group(3), "mana", ("fase",)
        eff = ""
        mm = re.match(r"(.+?) \((.*)\)$", x)
        if mm:
            x, eff = mm.group(1).strip(), mm.group(2)
        base = re.sub(r" \d+/\d+$", "", re.split(r" su | dalla mano", x)[0]).strip()
        terra = base in self.TERRE_BASE or "Land" in _TIPI.get(base, "")
        quando = "dopo l'attacco" if dopo else ""
        if terra:
            return f"Gioca la terra: {x}", quando, "gioca", ("carta", base)
        verbo = "Gioca" if re.search(r" \d+/\d+$", x) else "Lancia"
        return f"{verbo} {x}", ", ".join(y for y in (eff, quando) if y), "gioca", ("carta", base)

    def piano_turno(self, corpo, vinci, cambio=False):
        """«1) Plains | 2) Surgical Precision (peschi 1, +2 vite) | 3) attacca con A, B | 4) dopo l'attacco: C | vinci 85% ...»
        -> una riga per azione, nell'ordine (13 ott 2026). Le righe gia' scritte in questo turno da GIOCA, PW TUO, ATTACCO
        (EV) e MANA AVANZATO spariscono: dicevano le stesse cose in un altro ordine, e l'attacco era quello della vigilanza,
        non quello scelto in P. Con «ORA» (dopo una pescata o un surveil) i passi non ancora fatti del piano di prima si
        barrano."""
        for x in self.msg:
            if x.get("t") != self.turno or x["lato"] != "tu" or x["tipo"] != "msg":
                continue
            if x.get("cercatore"):
                continue
            if x.get("dal_piano"):
                if cambio and not x["fatto"]:
                    x["barrato"] = True
            elif x.get("passo") or x.get("ico") in ("gioca", "mana", "pw", "attacca", "difendi"):
                x["nascosto"] = True
        self.piano_t = self.turno
        passi = [re.sub(r"^\d+\) ", "", y.strip()) for y in corpo.split(" | ") if y.strip()]
        nasce = {re.sub(r" \(pedina\)", "", a).strip(): int(b) for a, b in re.findall(r"([A-Z][\w' -]*?) nasce a (\d+)", corpo)}
        ultimo = None
        for y in passi:
            if y.startswith("dopo l'attacco: "):
                for z in self.creature(y[len("dopo l'attacco: "):]):
                    testo, nota, ico, passo = self.passo_piano(z, dopo=True)
                    ultimo = self._m("tu", testo, nota=nota, ico=ico, passo=passo)
                    self.msg[ultimo]["dal_piano"] = True
                continue
            testo, nota, ico, passo = self.passo_piano(y)
            ultimo = self._m("tu", testo, nota=nota, ico=ico, passo=passo)
            self.msg[ultimo]["dal_piano"] = True
            if passo and passo[0] == "pw" and passo[1] in nasce: self.msg[ultimo]["nasce"] = nasce[passo[1]]
            if ico in ("attacca", "difendi"):
                self.msg[ultimo]["nota"] = f"vinci {vinci}%"
                self.attacco_id = ultimo
        if not any(self.msg[i].get("ico") in ("attacca", "difendi") for i in range(len(self.msg)) if self.msg[i].get("dal_piano") and self.msg[i].get("t") == self.turno and not self.msg[i]["barrato"]):
            if ultimo is not None:
                self.msg[ultimo]["nota"] = ", ".join(z for z in (self.msg[ultimo]["nota"], f"vinci {vinci}%") if z)
            self.attacco_id = None

    def cercatore(self, t):
        """«CERCATORE T10: attacca con A | vinci 25% contro 0% della proposta» (Motore_Partita/cercatore_vivo.scrivi_riga): la mossa
        che batte la proposta della spalla. Sta nel turno e nella fase in corso, in cima e in evidenza; la proposta resta
        sotto. Non ha un passo: «un passo alla volta» la nasconderebbe dietro la proposta. Una riga che non si legge esce com'e'."""
        m = re.match(r"CERCATORE T(\d+):\s*([^|]+?)\s*(?:\|\s*(.*))?$", t)
        if not m:
            j = self._m("info", t, ico="occhio", nel_tuo_turno=True)
            self.msg[j]["cercatore"] = True; return True
        n, mossa, dati = int(m.group(1)), m.group(2), m.group(3) or ""
        blocco = mossa.startswith(("blocca", "non bloccare"))
        # con --solo-claude le righe del suo turno non passano: il turno lo dice la riga stessa
        if n != self.turno or (blocco and self.ultimo_lato != "lui"):
            self.turno = n
            if blocco: self._sep("lui", "Opponent", nome=self.avversario)
            else: self._sep("tu", "", nome=ambiente.NOME_PLAYER)
        lista = []
        if mossa == "non attaccare":
            testo, ico = "Non attaccare", "difendi"
        elif mossa == "non bloccare":
            testo, ico = "Non bloccare", "scoperto"
        elif mossa.startswith("attacca con "):
            testo, ico = "Attacca con " + mossa[12:], "attacca"
        elif mossa.startswith("blocca "):
            testo, ico = "Blocca", "difendi"
            # «blocca Beast con Cadet, Arni, Humble Scribe con Goblin»: chi blocca  →  chi attacca; le virgole stanno anche dentro i nomi
            pezzi = mossa[7:].split(" con ")
            att = pezzi[0]
            for mezzo in pezzi[1:-1]:
                nomi = self.creature(mezzo)
                lista.append(f"{nomi[0]}  →  {att}"); att = ", ".join(nomi[1:])
            lista.append(f"{pezzi[-1]}  →  {att}" if len(pezzi) > 1 else att)
        else:
            testo, ico = mossa[:1].upper() + mossa[1:], "attacca"
        j = self._m("tu", testo, nota=dati, ico=ico, lista=lista)
        self.msg[j]["cercatore"] = True
        return True

    def attacco_in_p(self, cosa, vinci):
        """«ATTACCO SCELTO IN P (segui questo): attacchi con A, B | vinci 78% ...»: l'attacco del piano diventa questo."""
        testo = "Non attaccare" if cosa.startswith("nessun attacco") else "Attacca con " + cosa.replace("attacchi con ", "")
        i = getattr(self, "attacco_id", None)
        if i is None or i >= len(self.msg) or self.msg[i].get("t") != self.turno:      # i >= len: il messaggio di una partita finita, la chat e' ripartita
            # senza piano: la riga d'attacco della vigilanza di questo turno (ATTACCO (EV), «lui non ha creature»)
            i = next((x["id"] for x in reversed(self.msg) if x["tipo"] == "msg" and x.get("t") == self.turno and x["lato"] == "tu"
                      and x.get("ico") in ("attacca", "difendi") and not x["fatto"] and not x.get("nascosto") and not x.get("cercatore")), None)
        if i is not None and self.msg[i].get("t") == self.turno and not self.msg[i]["fatto"]:
            self.msg[i]["testo"] = testo; self.msg[i]["nota"] = f"vinci {vinci}%"; self.msg[i]["lista"] = []
            if testo.startswith("Attacca con "):
                self.msg[i]["lista"] = self.con_bersaglio(self.creature(testo[len("Attacca con "):])); self.msg[i]["testo"] = "Attacca con"
            self.msg[i]["ico"] = "difendi" if testo == "Non attaccare" else "attacca"
            self.msg[i]["passo"] = None if testo == "Non attaccare" else ("attacco",)
        else:
            j = self._m("tu", testo, nota=f"vinci {vinci}%", ico="difendi" if testo == "Non attaccare" else "attacca",
                        passo=None if testo == "Non attaccare" else ("attacco",))
            self.msg[j]["dal_piano"] = True; self.attacco_id = j

    def gioca(self, corpo, cambio=False, dopo_attacco=False):
        """«GIOCA: Forest, Ghalta 8/8 (forza in campo +8) | le creature dopo l'attacco | tieni Surgical Precision»
        -> un titolo che dice quando, una carta per riga, «Tieni in mano» a parte (Autore, 12 ott: «questi testi non
        sono chiari»)."""
        pezzi = [x.strip() for x in re.sub(r" \(forza in campo [^)]*\)", "", corpo).split(" | ")]
        rimanda = "creature: dopo l'attacco" in pezzi
        subito = "niente attacco: le creature adesso" in pezzi
        if subito: cambio = False
        pezzi = [x for x in pezzi if x not in ("creature: dopo l'attacco", "niente prima dell'attacco", "niente da giocare", "niente attacco: le creature adesso")]
        dopo = dopo_attacco
        tieni = [x[6:] for x in pezzi if x.startswith("tieni ")]
        # le carte che la proposta non conosce (fuori dal set): non sono un ordine, restano fuori dalla riga (bot Sparky, 13 ott)
        pezzi = [x for x in pezzi if not x.startswith("fuori dalla proposta")]
        carte = [x for x in pezzi if x and "dopo l'attacco" not in x and not x.startswith("tieni ")]
        if carte and carte[0].startswith("tieni "):
            tieni.append(carte.pop(0)[6:])
        voci = self.creature(", ".join(carte)) if carte else []
        if "tieni " in ", ".join(voci):
            voci2 = []
            for v in voci:
                if v.startswith("tieni "): tieni.append(v[6:])
                else: voci2.append(v)
            voci = voci2
        idx = None
        if voci:
            # un passo per carta (Autore, 12 ott 2026: «deve mandare un messaggio per step, no a elenco [...] ogni step
            # eseguito deve diventare grigio»): la finestra mostra il primo da fare, gli altri arrivano quando e' fatto
            quando = "niente attacco: adesso" if subito else ("dopo l'attacco" if dopo else ("prima dell'attacco" if rimanda else ""))
            if cambio or subito:              # la proposta nuova sostituisce i passi non ancora fatti di quella vecchia
                for x in self.msg:
                    if x.get("passo") and x["passo"][0] == "carta" and not x["fatto"] and x.get("t") == self.turno: x["barrato"] = True
            for i, v in enumerate(voci):
                base = re.sub(r" \d+/\d+$", "", re.split(r" su | \(preparata\)| dalla mano", v)[0]).strip()
                terra = base in ("Plains", "Island", "Swamp", "Mountain", "Forest") or "Land" in _TIPI.get(base, "")
                testo = f"Gioca la terra: {v}" if terra else (f"Gioca {v}" if re.search(r" \d+/\d+", v) else f"Lancia {v}")
                j = self._m("tu", testo, nota=(("cambio idea · " if cambio and i == 0 else "") + quando) if i == 0 else quando,
                            ico="cambio" if cambio and i == 0 else "gioca", passo=("carta", base))
                idx = j if idx is None else idx
        # «Dopo l'attacco: niente da giocare» e «Le creature te le dico dopo l'attacco» non sono azioni: una fase senza
        # niente da fare non ha riga (Autore, 8 ott 2026; 13 ott: «ogni azione deve avere una riga»)
        for x in tieni:
            self._m("tu", f"Tieni in mano: {x}", ico="mano")
        return idx

    def creature(self, s):
        """«A, B, Kiora, the Rising Tide» -> una creatura per voce. La virgola sta anche dentro certi nomi
        (Kiora, the Rising Tide; Ruric Thar, Biomagus): si riattacca il pezzo se insieme fanno un nome vero."""
        set_ = self.evento.split("_")[1] if "_" in self.evento else "FRA"
        voti_carte(set_)
        noti = _PRINCIPALI.get(set_, set())
        out = []
        for pezzo in [x.strip() for x in s.split(",") if x.strip()]:
            base = out[-1].split(" su ")[-1].split(" 2/")[0] if out else ""
            if out and (f"{out[-1]}, {pezzo}" in noti or f"{base}, {pezzo}" in noti or any(n.startswith(f"{base}, {pezzo}") for n in noti) or pezzo[:1].islower()):
                out[-1] = f"{out[-1]}, {pezzo}"
            else:
                out.append(pezzo)
        return out

    def leggi_lui(self, t):
        """Cio' che di lui si vede (Autore, 12 ott 2026: «le carte visibili lui dovrebbe dire che le vede»): mano (solo il
        numero), terre, creature, magie pronte, cimitero, e le magie gia' viste in partita. Torna True se il riquadro cambia."""
        u = self.suo; prima = repr(u)
        if t.startswith("STATO Partita"):
            io = self.io
            m0 = re.search(r"turno Arena (\d+) \([^)]*\) \| (\w+) (\w+)", t)
            if m0:
                if (io.get("turno"), io.get("fase")) != (int(m0.group(1)), m0.group(2)): self.suo_cambiato = True
                io["turno"], io["fase"], io["passo"] = int(m0.group(1)), m0.group(2), m0.group(3)
            for seg in t.split("||"):
                seg = seg.strip()
                if seg.startswith("LA TUA MANO"):
                    io["mano"] = dict(collections.Counter(re.sub(r"\s+\[.*$", "", x).strip() for x in seg.split(" | ")[1:]
                                                          if x.strip() and ":" not in x))
                if seg.startswith("IL TUO CAMPO:"):
                    io["pw"] = {re.sub(r" \(pedina\)", "", m.group(1)).strip(): int(m.group(2)) for m in re.finditer(r"([^|]+?)\s+\[fedelta' (\d+)\]", seg)}
            if self.verifica_passi(): self.suo_cambiato = True
            for seg in t.split("||"):
                seg = seg.strip()
                m = re.search(r"Mano avversaria: (\d+)", seg)
                if m: u["mano"] = int(m.group(1))
                if seg.startswith("IL SUO CAMPO:"):
                    parti = seg.split(" | ")
                    m = re.match(r"IL SUO CAMPO: terre (\d+) \((\d+) stappate\)", parti[0])
                    if m: u["terre"], u["libere"] = int(m.group(1)), int(m.group(2))
                    cr = []
                    for x in parti[1:]:
                        m = re.match(r"(.+?)\s+\[(\d+/\d+)?([^\]]*)\]", x.strip())
                        if m and m.group(2): cr.append((m.group(1).strip(), m.group(2), "TAPPATA" in (m.group(3) or "")))
                    u["creature"] = cr
                if seg.startswith("Cimitero suo:"):
                    u["cimitero"] = len([x for x in seg[len("Cimitero suo:"):].split(",") if x.strip()])
        elif t.startswith("suo campo:"):
            u["pronte"] = re.findall(r"pronta: ([^,|\[]+)", t)
            for n in [c[0] for c in u["creature"]]:
                m = re.search(re.escape(n) + r" \d+/\d+ ([a-z, ]+)", t)
                if m: u["kw"][n] = m.group(1)
        else:
            m = re.match(r"MAGIA sua: (.+?) (\{[^|]*\})? ?\|", t)
            if m and m.group(1).strip() not in u["viste"]: u["viste"].append(m.group(1).strip())
        return False if repr(u) == prima else (setattr(self, "suo_cambiato", True) or False)

    def verifica_passi(self):
        """Un passo e' fatto quando la sua carta lascia la tua mano, quando l'attacco o il blocco sono passati, quando il tuo
        planeswalker cambia fedelta', o quando il turno e' finito. Torna True se qualcosa e' cambiato."""
        io = self.io; cambiato = False
        dopo_attacchi = io["fase"] in ("Main2", "Ending") or io["passo"] in ("DeclareBlock", "CombatDamage", "FirstStrikeDamage", "EndCombat")
        for m in self.msg:
            ps = m.get("passo")
            if not ps or m["fatto"] or m["barrato"]: continue
            fatto = bool(io["turno"] and m.get("t") and io["turno"] > m["t"] + (0 if m["lato"] == "tu" and ps[0] != "blocco" else 1))
            # il riferimento si prende al primo stato del turno del passo: la riga STATO arriva dopo i consigli
            if not fatto and m["fase0"] is None:
                if io["turno"] == m.get("t"):
                    m["fase0"] = io["fase"]; m["mano0"] = io["mano"].get(ps[1], 0) if ps[0] == "carta" else None
                    m["fed0"] = io["pw"].get(ps[1], m.get("nasce")) if ps[0] == "pw" else None
                    if ps[0] == "pw" and io["pw"].get(ps[1]) is not None: m["visto_pw"] = True   # sparisce a zero: il -1 c'e' stato
                    # un planeswalker che al primo stato non c'e' e non deve nascere non si puo' piu' attivare: il passo e' chiuso
                    if ps[0] == "pw" and io["pw"].get(ps[1]) is None and not m.get("nasce"): m["fatto"] = True; cambiato = True
                    # la carta non e' gia' piu' in mano (la terra giocata prima che arrivasse lo stato): fatto
                    if ps[0] == "carta" and not m["prep"] and not m["mano0"]: m["fatto"] = True; cambiato = True
                continue
            if io["fase"] == "Ending" and io["turno"] == m.get("t") and m["lato"] == "tu": fatto = True   # il turno e' finito
            if ps[0] == "carta":
                if m["mano0"]: fatto = fatto or io["mano"].get(ps[1], 0) < m["mano0"]
                elif m["prep"]: fatto = fatto or io["fase"] != m["fase0"]
                elif io["mano"].get(ps[1], 0): m["mano0"] = io["mano"][ps[1]]
            elif ps[0] == "attacco": fatto = fatto or dopo_attacchi
            elif ps[0] == "blocco": fatto = fatto or io["passo"] in ("CombatDamage", "EndCombat") or io["fase"] in ("Main2", "Ending", "Main1")
            elif ps[0] == "pw":
                ora = io["pw"].get(ps[1])
                if ora is not None: m["visto_pw"] = True
                if m["fed0"] is None and ora is not None: m["fed0"] = ora; continue
                # fatto quando la fedelta' cambia, o quando il planeswalker visto sparisce (il -1 che lo porta a zero)
                fatto = fatto or (m["fed0"] is not None and ora is not None and ora != m["fed0"]) or (ora is None and bool(m.get("visto_pw")))
            elif ps[0] == "fase": fatto = fatto or io["fase"] != m["fase0"]
            if fatto: m["fatto"] = True; cambiato = True
        return cambiato

    def vedi_sue(self, t):
        """Ogni carta dell'avversario si conta una volta, quando compare la prima volta (campo, magia, cimitero)."""
        if t.startswith("MAGIA sua:"):
            t = t.split("|")[0]
        elif t.startswith("STATO"):
            t = " || ".join(x for x in t.split("||") if "IL SUO CAMPO:" in x or "Cimitero suo:" in x)
        set_ = self.evento.split("_")[1] if "_" in self.evento else "FRA"
        voti_carte(set_)
        for nome in sorted(_PRINCIPALI.get(set_, ()), key=len, reverse=True):
            if nome in t and nome not in self.sue_carte and f"{nome} (pedina)" not in t:
                if any(nome != altro and nome in altro and altro in t for altro in self.sue_carte):
                    continue
                self.sue_carte[nome] = 1

    def riga(self, r):
        """Una riga del diario (senza l'ora). Torna True se ha cambiato qualcosa."""
        s = r.rstrip()
        t = s.strip()
        if not t:
            return False
        self.bers = []
        # il companion che riparte: la chat riparte vuota (Autore, 17 ott 2026: «chat pulita perche' siamo ripartiti da zero»)
        if t.startswith("COMPANION ATTIVO"):
            self.reset(""); return True
        # le righe di Claude (Autore, 13 ott 2026 sera: «non lo vogliamo», «la prossima tu scrivi nella chat del companion»,
        # «farai i calcoli ev»): «CLAUDE: titolo | voce | voce». Con --solo-claude i consigli automatici non si mostrano.
        if t.startswith("CLAUDE:"):
            corpo = t[7:].strip()
            # nello stile scelto per la finestra (Autore: «scrivi con lo stile che abbiamo scelto del companion»): una riga
            # nei formati della spalla («TURNO INTERO: 1) … | vinci N%», «ATTACCO (EV): …») passa al suo impaginatore
            if re.match(r"(TURNO INTERO|GIOCA|ATTACCO|PW TUO|PW SUO|BLOCCA|SE TIENE IL MANA|SUO MANA):", corpo):
                global SOLO_CLAUDE
                prima, SOLO_CLAUDE = SOLO_CLAUDE, False
                try: return self.riga(corpo)
                finally: SOLO_CLAUDE = prima
            pezzi = [x.strip() for x in corpo.split(" | ") if x.strip()]
            j = self._m("info", pezzi[0] if pezzi else "", ico="occhio", lista=pezzi[1:], nel_tuo_turno=True)
            self.msg[j]["claude"] = True; return True
        # il Cercatore dal vivo e il metro delle vittorie passano anche con --solo-claude (sessione Magic 07, 4 nov 2026): il
        # primo cambia la scelta da fare, il secondo e' una riga di fine partita
        if t.startswith("CERCATORE"):
            return self.cercatore(t)
        if t.startswith("LIMITED:"):     # Launch di Play limited: la chat dice che il companion limited e' pronto (pronto_limited.py)
            pezzi = [x.strip() for x in t[8:].split(" | ") if x.strip()]
            self._m("info", pezzi[0] if pezzi else "", ico="controllo", lista=pezzi[1:], nel_tuo_turno=True); return True
        if t.startswith("METRO"):
            voci = [x.strip() for x in re.sub(r"^METRO:?\s*", "", t).split(" | ") if x.strip()]
            self._m("info", "Metro", nota=" · ".join(voci), ico="controllo", nel_tuo_turno=True); return True
        # il drafter resta (draft, costruzione, cancello): la modalita' «solo Claude» spegne i consigli di PARTITA
        if SOLO_CLAUDE and not (t.startswith("=== ") or re.match(r"TURNO \d+ \||PICK \d|STEMMI \d|MAZZI|CANCELLO|COMPANION \| drafter", t)):
            return False
        spinta = " | spinta: lui e' a corto di mana" in t
        t = t.replace(" | spinta: lui e' a corto di mana", "")
        ms = re.match(r"SUO MANA: (\d+) terre dopo (\d+) suoi turni \(ne ha saltate (\d+)\), (\S+) carte in mano: e' a corto di mana\. (.+?)(?: \(grado C\))?$", t)
        if ms:
            consiglio = ms.group(5)
            if "spingi" in consiglio:
                # piu' semplici (Autore, 13 ott 2026: «questi testi devono essere piu' semplificati», «cambia spingi con attack push»)
                # «nel dubbio, attacca» e «gioca prima le creature» tolte: non dicevano niente (Autore, 13 ott); al loro posto
                # la definizione di attack push, sotto la voce
                voci = [("Attack push", "attacca subito, prima che trovi le terre per difendersi"),
                        "Tieni le rimozioni per le sue minacce"]
            else:
                pr = re.search(r"\(([^)]*)\)", consiglio)
                voci = ["Sei tu sotto pressione" + (f": {pr.group(1)}" if pr else ""), "Prima difenditi, attacchi dopo"]
            self._m("info", f"Lui è a corto di mana: {ms.group(1)} terre dopo {ms.group(2)} turni, {ms.group(4)} carte in mano",
                    ico="avviso", lista=voci, nel_tuo_turno=True)
            return True
        bm = re.search(r" \| BERSAGLI: ([^|]+?)(?: \| ([^|]+))?$", t)
        if bm:
            t = t[:bm.start()]
            self.bers = [x.split(" -> ") for x in bm.group(1).split("; ") if " -> " in x]
            self.bers_motivo = bm.group(2) or ""
        m = re.match(r"=== PARTITA: (\S+) ===", t)
        if m:
            self.reset(m.group(1)); return True
        m = re.match(r"MANO \((\d+)\) contro (.+?) \[.*?\]: (.*?) \| terre (\d+/\d+) -> (\w+)", t)
        if m:
            self.avversario = m.group(2)
            self._sep("tu", "Mano iniziale")
            self._m("tu", f"{m.group(5).capitalize()} la mano: {m.group(4)} terre", ico="mano"); return True
        m = re.match(r"TURNO (\d+) \| vite tu (\d+) lui (\d+)", t)
        if m:
            self.miei_turni += 1
            self.turno = int(m.group(1))
            self.mano_turno = (re.search(r"\| mano: (.*)$", t) or [None, ""])[1]   # la mano a inizio turno: il riferimento dei passi
            self.vite = (int(m.group(2)), int(m.group(3)))
            self.gioca_id = None
            self._sep("tu", "", nome=ambiente.NOME_PLAYER); return True
        if t.startswith("suo campo:") or t.startswith("MAGIA sua:") or "IL SUO CAMPO:" in t or "Cimitero suo:" in t:
            self.vedi_sue(t)
        if self.leggi_lui(t): return True
        if t.startswith("tuo campo:") or t.startswith("suo campo:") or t.startswith("(restare a casa"):
            return False
        m = re.match(r"GIOCA: (.+)", t)
        if m:
            self.gioca_id = self.gioca(m.group(1)); return True
        m = re.match(r"GIOCA DOPO L'ATTACCO T\d+: (.+)", t)
        if m:
            self.gioca_id = self.gioca(m.group(1), dopo_attacco=True); return True
        m = re.match(r"GIOCA ORA T\d+: (.+)", t)
        if m:
            if self.gioca_id is not None:
                self.msg[self.gioca_id]["barrato"] = True
            self.gioca_id = self.gioca(m.group(1), cambio=True); return True
        m = re.match(r"MANA AVANZATO: dopo GIOCA ti restano (\d+) mana -> attiva (.+?) \| (.+)$", t)
        if m:
            q = re.match(r"(.+?) (\{[^:]*\})(?:, \{T\})?:", m.group(2))
            if q:
                costo = sum(int(c) if c.isdigit() else 1 for c in re.findall(r"\{([^}]*)\}", q.group(2)))
                testo = f"Attiva {q.group(1)} ({costo} mana)"
            else:
                testo = f"Attiva {m.group(2).split(':')[0]}"
            quando = m.group(3).split(":")[0].strip()
            self._m("tu", testo, nota=quando, ico="mana", passo=("fase",)); return True
        m = re.match(r"PERICOLO: lui ti chiude in (\d+) turn[oi] con (\d+) danni a turno che non fermi: (.+?), contro le tue (\d+) vite \| (.+?)(?: \(grado C\))?$", t)
        if m:
            # il suo orologio su di te coi danni che passano anche tenendo tutti a casa (12 ott 2026, caso 6 contro Legosi)
            uscite = [re.sub(r"^\d+\) ", "", x.strip()) for x in m.group(5).replace("uscite: ", "").split("; ")]
            self._m("info", f"Pericolo: ti chiude in {m.group(1)} turn{'o' if m.group(1) == '1' else 'i'}, {m.group(2)} danni a turno che non fermi",
                    nota=m.group(3), ico="avviso", lista=uscite, nel_tuo_turno=True); return True
        m = re.match(r"ADESSO O MAI PIU': oggi lui ha (\d+) creature tappate \((.+?)\), domani bloccano anche loro\. Con tutti all'attacco oggi passano almeno (\d+) danni \(lui da (\d+) a (\d+)\), domani (\d+)\.", t)
        if m:
            # l'attacco di oggi contro quello di domani (12 ott 2026, caso 1 contro Legosi): un'informazione, non un ordine
            self._m("info", f"Adesso o mai più: oggi passano {m.group(3)} danni (lui da {m.group(4)} a {m.group(5)}), domani {m.group(6)}",
                    nota=f"tappate oggi: {m.group(2)}", ico="avviso", nel_tuo_turno=True); return True
        m = re.match(r"CONFRONTO T(\d+) contro .+?: (.+?)\. Errore della riga o scelta tua\?", t)
        if m:
            # il confronto passo per passo a fine partita (regola di Autore, 12 ott 2026 16:25): una domanda per riga
            self._m("info", f"T{m.group(1)}: {m.group(2)}", nota="errore della spalla o scelta tua?", ico="controllo", nel_tuo_turno=True); return True
        m = re.match(r"CONFRONTO: (.+)", t)
        if m:
            self._m("info", "Confronto con la spalla: " + m.group(1), ico="controllo", nel_tuo_turno=True); return True
        m = re.match(r"TURNO INTERO( ORA T\d+)?:\s*(.+?) \| vinci (\d+)%", t)
        if m:
            self.piano_turno(m.group(2), int(m.group(3)), cambio=bool(m.group(1))); return True
        m = re.match(r"ATTACCO SCELTO IN P \(segui questo\): (.+?) \| vinci (\d+)%", t)
        if m:     # si segue sempre, anche nei turni senza piano intero (turno 7 contro SrLeitao: diceva «Non attaccare»)
            self.attacco_in_p(m.group(1), int(m.group(2))); return True
        if getattr(self, "piano_t", None) == self.turno and re.match(r"(GIOCA: |PW TUO: |ATTACCO \(EV\): |MANA AVANZATO: |\(restare a casa)", t):
            return False      # il piano del turno ha gia' detto queste cose, una riga per azione (13 ott 2026)
        m = re.match(r"TURNO INTERO(?: ORA T\d+)?:(.+?) \| vale ([+-]?\d+\.\d+), giocata e attacco separati ([+-]?\d+\.\d+)", t)
        if m:
            # il piano del turno intero (12 ott 2026, Companion/Suggeritore/turno_intero.py): i passi uno per riga, come la sequenza
            passi = [re.sub(r"^\d+\) ", "", x.strip()) for x in m.group(1).split(" | ")]
            self._m("tu", "Il turno intero, in quest'ordine", nota=f"vale {m.group(2)}, giocata e attacco separati {m.group(3)}",
                    ico="catena", lista=[f"{i + 1}.  {x}" for i, x in enumerate(passi)]); return True
        m = re.match(r"SEQUENZA: (.+?)(?: \(grado C\))?$", t)
        if m:
            passi = [re.sub(r"^\d+\) ", "", x.strip()) for x in m.group(1).split(" | ")]
            self._m("tu", "Sequenza, in quest'ordine", ico="catena", lista=[f"{i + 1}.  {x}" for i, x in enumerate(passi)]); return True
        m = re.match(r"PW TUO: (.+?): usa \[([^\]]+)\] (.+?) \(fedelta' (-?\d+) -> (-?\d+)\)", t)
        if m:
            self._m("tu", f"{m.group(1)}: usa {m.group(2).replace('-', '−')}, {m.group(3)}", nota=f"fedeltà {m.group(4)} → {m.group(5)}", ico="pw", passo=("pw", m.group(1).replace(" (pedina)", "").strip())); return True   # come lo chiama lo stato
        m = re.match(r"PW TUO: (.+)", t)
        if m:
            self._m("tu", m.group(1).split(". Perche'")[0], ico="pw"); return True
        m = re.match(r"PW SUO: (.+?) fedelta' (\d+): (.+?)\. (TOGLILO|lascialo)", t)
        if m:
            toglilo = m.group(4) == "TOGLILO"
            poteri = [x.strip().replace("[-", "[−") for x in re.split(r", (?=\[)", m.group(3))]
            nome = m.group(1).replace(" (pedina)", "")
            self._m("tu", (f"Togli il suo {nome} (fedeltà {m.group(2)}): ha un potere che chiude" if toglilo
                            else f"Attacca lui, non il suo {nome} (fedeltà {m.group(2)})"),
                    ico="pw", lista=poteri if toglilo else [], nel_tuo_turno=True); return True
        # le carte della sua mano che vedi (13 ott 2026): allarmi per il piano d'attacco, di difesa e per il suo turno
        m = re.match(r"MANO SUA VISTA: (.+?) \| sue terre (\d+), libere ora (\d+)$", t)
        if m:
            self.suo["in_mano"] = []
            for pezzo in m.group(1).split(" | "):
                q = re.match(r"(.+?) \[(.*)\]$", pezzo)
                nome, cosa = (q.group(1), q.group(2)) if q else (pezzo, "")
                self.suo["in_mano"].append(nome)
                if cosa != "terra":
                    self._m("info", f"In mano ha: {nome}", nota=cosa.replace(", ", "  ·  "), ico="avviso", nel_tuo_turno=True)
            self.suo_cambiato = True
            return True
        if t.startswith("MANO SUA VISTA: nessuna"):
            self.suo["in_mano"] = []; self.suo_cambiato = True; return True
        # il bersaglio della sua magia, arrivato dopo la magia: la riga «Ha giocato X» diventa «X → Y» (13 ott 2026)
        m = re.match(r"BERSAGLIO SUO: (.+?) su (.+)$", t)
        if m:
            magia, bers = m.groups()
            i = next((x["id"] for x in reversed(self.msg) if x["tipo"] == "msg" and x["lato"] == "lui"
                      and re.match(r"(Lui ha giocato|Ha giocato) " + re.escape(magia) + r"( su .+)?$", x["testo"])), None)
            if i is not None:
                self.msg[i]["testo"] = re.sub(r" su .+$", "", self.msg[i]["testo"]) + " su " + ", ".join(
                    re.sub(r" \((tua|sua)\)$", "", x) for x in bers.split(", "))
                if "(tua)" in bers or re.search(r"(^|, )te(,|$)", bers): self.msg[i]["ico"] = "avviso"
            return True
        # la sua aura: la riga «Ha giocato X» prende il bersaglio e l'effetto (13 ott 2026)
        m = re.match(r"AURA SUA: (.+?) su (.+?) \((tua|sua)\): (.+)$", t)
        if m:
            aura, chi, dove, eff = m.groups()
            i = next((x["id"] for x in reversed(self.msg) if x["tipo"] == "msg" and x["lato"] == "lui"
                      and re.match(r"(Lui ha giocato|Ha giocato) " + re.escape(aura) + r"( su .+)?$", x["testo"])), None)
            # un equipaggiamento che passa a un'altra creatura (Medic's Kitesail, macazilla 16 ott) e' un fatto nuovo: non
            # riscrive il bersaglio del primo messaggio, che restava solo sull'ultima creatura (collaudo V11, 3 nov 2026)
            if i is not None and " su " in self.msg[i]["testo"] and not self.msg[i]["testo"].endswith(f" su {chi}"):
                i = None
            if i is not None:
                self.msg[i]["testo"] = re.sub(r" su .+$", "", self.msg[i]["testo"]) + f" su {chi}"
                self.msg[i]["nota"] = eff.replace(", ", "  ·  ")
                if dove == "tua": self.msg[i]["ico"] = "avviso"
            else:
                self._m("info", f"Aura sua: {aura} su {chi}", nota=eff.replace(", ", "  ·  "), ico="avviso", nel_tuo_turno=True)
            return True
        # le ipotesi sul mana che ha lasciato aperto (13 ott 2026)
        m = re.match(r"SE TIENE IL MANA: (\d+) terre aperte \((\w+|\?)\), (\d+) carte in mano: (.+?) \(ipotesi", t)
        if m:
            voci = [re.sub(r" \[(.+)\]$", r"  (\1)", x.strip()) for x in m.group(4).split(" | ")]
            self._m("info", "Col mana aperto può giocare", nota=(f"{m.group(1)} terre aperte" if m.group(1) != "1" else "1 terra aperta") + f"  ·  {m.group(3)} carte in mano  ·  ipotesi dal formato",
                    ico="avviso", lista=voci, nel_tuo_turno=True)
            return True
        m = re.match(r"TRUCCO NOTO IN COMBATTIMENTO: (.+?) \(", t)
        if m:
            self._m("info", f"Trucco noto in combattimento: {m.group(1)}", nota="lo paga col mana libero adesso", ico="avviso", nel_tuo_turno=True); return True
        m = re.match(r"PUNISCE AL SUO TURNO: (.+)$", t)
        if m:
            for x in m.group(1).split(" | "):
                q = re.match(r"(.+?) su (.+)$", x)
                if q: self._m("info", f"Al suo turno toglie: {q.group(2)} con {q.group(1)}", ico="avviso", nel_tuo_turno=True)
            return True
        m = re.match(r"ATTACCO: lui non ha creature, puoi attaccare con (.+?): danni liberi", t)
        if m:
            # un messaggio di valore, non un'azione (Autore, 13 ott 2026): l'allarme e cosa notare; l'attacco lo dice il piano
            self._m("info", "Lui non ha creature", nota="ogni attacco va a segno: i danni sono liberi", ico="avviso")
            if getattr(self, "piano_t", None) == self.turno: return True
            self._m("tu", "Attacca con", ico="attacca", lista=self.con_bersaglio(self.creature(m.group(1))), passo=("attacco",)); return True
        m = re.match(r"LETALE: attacchi con (.+?)( \(anche col trucco\))?$", t)
        if m:
            self._m("tu", "LETALE", nota="anche col trucco" if m.group(2) else "", ico="letale", lista=self.con_bersaglio(self.creature(m.group(1))), passo=("attacco",)); return True
        m = re.match(r"PIANO(?: ORA T\d+)?: (.+)", t)
        if m:
            a = re.search(r"tu chiudi in (\d+) turn", m.group(1)); b = re.search(r"lui in (\d+)", m.group(1))
            d = re.search(r"dopo GIOCA forza \d+: (\d+) turn", m.group(1))
            self.piano = (int(d.group(1)) if d else (int(a.group(1)) if a else None), int(b.group(1)) if b else None)
            return True
        m = re.match(r"ATTACCO \(EV\): (.+?) [+-]\d+\.\d+ \(p trucco ([\d.]+)", t)
        if m:
            cosa = m.group(1)
            nota = f"trucchi {round(float(m.group(2)) * 100)}%" + ("  ·  attack push: lui è a corto di mana" if spinta else "")
            if cosa.startswith("nessun attacco"):
                self._m("tu", "Non attaccare", nota=nota, ico="difendi")
            else:
                chi = self.con_bersaglio(self.creature(cosa.replace("attacchi con ", "")))
                self._m("tu", "Attacca con " + ", ".join(chi), nota=nota, ico="attacca", passo=("attacco",))
            return True
        if t.startswith("!! CONTRATTACCO A RISCHIO"):
            m = re.search(r"visibili (\d+) \+ nascosti ~(\d+).*?contro (\d+) vite", t)
            self._m("info", "Contrattacco a rischio" + (f": {m.group(1)} visibili e circa {m.group(2)} nascosti contro {m.group(3)} vite" if m else ""), ico="avviso")
            return True
        m = re.match(r"MAGIA sua: (.+?) (\{[^|]*\})? ?\|", t)
        if m:
            # Autore, 13 ott 2026: «e se lui nella nostra fase di attacco fa qualcosa?». La riga dice di chi e' il turno e la
            # fase: nel tuo turno la sua magia resta nel tuo turno (prima apriva un suo turno finto), nella fase in cui arriva
            q = re.search(r"\| nel (tuo|suo) turno T(\d+), (\w+)", t)
            costo = sum(int(c) if c.isdigit() else 1 for c in re.findall(r"\{([^}]*)\}", m.group(2) or "") if c != "X")
            nota = f"{costo} mana" if m.group(2) else ""
            # il bersaglio (13 ott 2026): «Last Gasp → Grim Repriser»; su una tua creatura o su di te l'icona e' l'avviso
            bq = re.search(r"\| bersaglio: (.+?)(?: \||$)", t)
            su = ""; ico = "magia"
            if bq:
                su = " su " + ", ".join(re.sub(r" \((tua|sua)\)$", "", x) for x in bq.group(1).split(", "))
                if "(tua)" in bq.group(1) or re.search(r"(^|, )te(,|$)", bq.group(1)): ico = "avviso"
            nome_m = re.sub(r"\s*\?$", "", m.group(1).strip())      # carta fuori dal set: il costo e' «?» (Sparky, 13 ott)
            if q and q.group(1) == "tuo":
                j = self._m("lui", f"Lui ha giocato {nome_m}{su}", nota=nota, ico=ico, nel_tuo_turno=True)
            else:
                j = self._m("lui", f"Ha giocato {nome_m}{su}", nota=nota, ico=ico)
            if q: self.msg[j]["fase_io"] = q.group(3)
            return True
        tn = re.match(r"ATTACCO SUO T(\d+):", t)
        if tn:
            self.turno = int(tn.group(1)) - (1 if self.ultimo_lato != "lui" else 0)
        m = re.match(r"ATTACCO SUO T\d+: (.+?) = (\d+) su (\d+) vite( \+ (\d+) sul planeswalker)?.*?-> (?!tuo planeswalker)(.+)$", t)
        if m:
            chi = re.sub(r" (\d+/\d+)[^,]*", r" \1", m.group(1))
            if m.group(5) and m.group(2) == "0":
                self._m("lui", f"Attacca il tuo planeswalker con {chi}: {m.group(5)} danni", ico="attacca")
            else:
                self._m("lui", f"Ti attacca con {chi}: {m.group(2)} danni" + (f", {m.group(5)} al planeswalker" if m.group(5) else ""), ico="attacca")
            dopo = m.group(6)
            if "nessun bloccante" in dopo:
                self._m("tu", "Non hai bloccanti liberi", ico="scoperto")
            else:
                b = re.match(r"BLOCCO: (.+?) \(EV", dopo)
                if b:
                    x = b.group(1)
                    nb = x.startswith("nessun blocco")
                    self._m("tu", "Non bloccare" if nb else "Blocca: " + x.replace("->", "su").replace("#1", "").replace("#2", ""), ico="scoperto" if nb else "difendi", passo=("blocco",))
            return True
        m = re.match(r"(SURVEIL|SCRY): (.+?) -> (\w+)", t)
        if m:
            dove = {"sopra": "in cima", "cimitero": "nel cimitero", "sotto": "in fondo"}.get(m.group(3), m.group(3))
            # il surveil c'e' stato: il passo del planeswalker che lo fa e' fatto (Shovelspoon T12, 13 ott 2026: Jace -1 a
            # fedelta' 1 spariva prima del primo stato, e in seconda fase la finestra chiedeva di attivarlo ancora)
            for x in self.msg:
                if (x["tipo"] == "msg" and x.get("t") == self.turno and not x["fatto"] and (x.get("passo") or ("",))[0] == "pw"
                        and m.group(1).lower() in x["testo"].lower()):
                    x["fatto"] = True; break
            self._m("tu", f"{m.group(1).capitalize()}: {m.group(2)} {dove}", ico="occhio"); return True
        m = re.match(r"=== FINE PARTITA: \S+ (VINTA|PERSA) ===", t)
        if m:
            self.esito = m.group(1)
            self._m("info", "Partita vinta" if m.group(1) == "VINTA" else "Partita persa", ico="vinta" if m.group(1) == "VINTA" else "persa"); return True
        m = re.match(r"STEMMI (\d+-\d+): (.+)$", t)
        if m:
            # gli stemmi del pack (8 nov 2026): escono subito, il pick del drafter arriva dopo e cambia il titolo dello stesso messaggio
            pack, pick = m.group(1).split("-")
            if pack != getattr(self, "pack", None):
                self.pack = pack; self._sep("tu", f"Pack {pack}")
            voci = []
            for x in m.group(2).split(" | "):
                g = re.match(r"(.+) (-?\d+(?:\.\d+)?)$", x.strip())
                if g:
                    voci.append((g.group(1), float(g.group(2))))
            i = self._m("tu", f"Pick {pick}: thinking…", ico="pick")
            self.msg[i]["stemmi"] = voci[:5]
            self.ultimo_pick = (m.group(1), i); return True
        m = re.match(r"PICK (\d+-\d+): PRENDI -> (.+?)( \||$)", t)
        if m:
            # in testa il titolo col pack, sotto solo il numero del pick (Autore, 5 nov 2026: «in testa ai pick deve esserci un titolo che e' il nome del pack:
            # titolo numero pack e poi sotto solo il numero pick»)
            pack, pick = m.group(1).split("-")
            if pack != getattr(self, "pack", None):
                self.pack = pack; self._sep("tu", f"Pack {pack}")
            testo = f"Pick {pick}: prendi {m.group(2)}"
            ult = getattr(self, "ultimo_pick", None)
            # la rara obbligata esce subito e il pick completo dopo (8 nov 2026): la seconda riga dello stesso pick aggiorna la prima
            if ult and ult[0] == m.group(1) and ult[1] < len(self.msg) and self.msg[ult[1]].get("ico") == "pick":
                self.msg[ult[1]]["testo"] = testo
                self.msg[ult[1]]["scelta"] = re.sub(r"\s+\(.*$", "", m.group(2)).strip()     # il fuoco passa alla carta del drafter
                return True
            self.ultimo_pick = (m.group(1), self._m("tu", testo, ico="pick")); return True
        m = re.match(r"=== (DRAFT|COSTRUZIONE): (\S+) ===", t)
        if m:
            self.reset(m.group(2)); self._sep("tu", "Draft" if m.group(1) == "DRAFT" else "Costruzione del mazzo"); return True
        m = re.match(r"MAZZI (\d)\. (.+?): ([\d.]+) vittorie attese(?:, meglio del (\d+)%)?", t)
        if m:
            self.mazzo_n = m.group(1)
            self._m("tu", f"Mazzo {m.group(1)}: {m.group(2)}, {m.group(3)} vittorie attese"
                    + (f", meglio del {m.group(4)}% dei pool" if m.group(4) else ""), ico="mazzo"); return True
        # la lista delle carte sotto ogni mazzo (13 ott 2026, Autore: «a me non sono stati dati mazzi dal companion»)
        m = re.match(r"MAZZI\s{2,}(?!mana)(\S.*)", t)
        if m and getattr(self, "mazzo_n", None):
            self._m("tu", f"Lista {self.mazzo_n}: {m.group(1).strip()}", ico="mazzo"); return True
        m = re.match(r"CANCELLO (Verde|Giallo|Rosso)", t)
        if m:
            self._m("tu" if m.group(1) == "Verde" else "info", f"Controllo del mazzo: {m.group(1).lower()}", ico="controllo"); return True
        # il motore delle opzioni (Motore_Opzioni/opzioni.py --dal-vivo --companion, 13 ott 2026 sera: Autore «mostramelo
        # nel companion proprio»): le 3 mosse migliori di chi e' di turno, la migliore dell'altro, e i planeswalker
        m = re.match(r"OPZIONI T\d+ PW: (.+)$", t)
        if m:
            self._m("info", "Planeswalker", ico="pw", lista=[x.strip() for x in m.group(1).split(" · ")], nel_tuo_turno=True); return True
        m = re.match(r"OPZIONI T\d+ (tu|lui) \w+: (.+)$", t)
        if m:
            corpo, poi = (m.group(2).split(" · poi ", 1) + [""])[:2]
            voci = [re.sub(r"^\d\) ", "", x.strip()) for x in corpo.split(" | ") if x.strip()]
            if poi: voci.append("Poi " + poi.replace(": ", ", al suo turno: ", 1) if poi.startswith("lui") else "Poi " + poi.replace(": ", ", al tuo turno: ", 1))
            self._m("info", "Opzioni (motore nuovo)" if m.group(1) == "tu" else "Opzioni di lui (motore nuovo)", ico="ventaglio",
                    lista=voci, nel_tuo_turno=True); return True
        return False
