"""Le connessioni padre -> figlio fra le carte di un mazzo, e cosa ne impara lo strumento (Autore, 9 nov 2026).

La storia: prima una rete col pulsante Synergies e un pannello («la rete di connessione voglio costruirla io», «come se potessi costruire un obsidian ma di carte»);
poi, lo stesso giorno: «quando premo synergies si blocca, ascolta fa cosi' togli il meccanismo di synergies, metti un pallino sotto le carte e tirando quel pallino
posso agganciarle ad altre, la prima carta e' padre e chi riceve il pallino e' figlio, lo strumento impara sinergie guardando le connessioni tra padre e figlio».

- Una connessione ha un verso: dal PADRE (la carta da cui tiri il pallino) al FIGLIO (la carta dove lo lasci). Rifare la stessa connessione la toglie.
  Per mazzo, in `Log_Arena/sinergie_mazzi.json`; resta anche se il mazzo cambia (una connessione fra carte che non ci sono non si vede, ma torna se le rimetti).
  Le connessioni del primo giro (senza verso, «tue») si riprendono col primo nome come padre.
- Ogni connessione porta le famiglie che la spiegano dal testo delle carte (le tabelle PRODUCE/VUOLE dello scout, `Motore/sinergie_tag.py`): quelle che il padre
  produce e il figlio vuole. Le scrive chi la crea, col database delle carte che ha in mano.
- L'IMPARATO (`impara`): da tutte le connessioni di tutti i mazzi, quante volte una carta e' padre di un'altra, chi fa da padre e da figlio piu' spesso, quali famiglie
  legano padre e figlio. In `Log_Arena/sinergie_imparate.json`, rifatto a ogni connessione nuova o tolta. Lo strumento non crea connessioni da solo: le impara da te.
`--prova`: verso, toggle, una carta con se stessa no, salvataggio, ripresa del primo giro, famiglie dal testo, l'imparato da piu' mazzi, con le negative."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import collections
import json
import threading

import sinergie_tag as ST

import account as _ACC  # noqa: E402
FILE = _ACC.lega(globals(), "FILE", "sinergie_mazzi.json")           # nell'app pubblica uno per account (10 nov 2026, Magic 12)
IMPARATE = _ACC.lega(globals(), "IMPARATE", "sinergie_imparate.json")
# il nome che si legge per ogni famiglia dello scout (le tribu' restano col loro nome)
NOMI = {"counter": "+1/+1 counters", "token": "tokens", "lifegain": "lifegain", "lifeloss": "life loss", "noncreature": "noncreature spells", "etb": "enter triggers",
        "discard_self": "discard", "mill_self": "graveyard", "sac_outlet": "sacrifice", "dies": "dies", "mana": "mana", "landfall_land": "landfall", "draw": "card draw",
        "blink": "blink", "bounce_own": "bounce", "evasion": "evasion", "equipment": "equipment", "vehicle": "vehicles", "artifact": "artifacts",
        "enchantment": "enchantments", "instant_sorcery": "instants & sorceries", "treasure": "treasure", "food": "food", "prowess_body": "prowess",
        "deathtouch": "deathtouch + fight", "outlaw": "outlaws", "speed": "speed", "damage_face": "burn", "swarm": "go wide", "pesca_evento": "draw triggers",
        "vita_evento": "lifegain triggers"}
_TAG = {}
_CHIAVE = threading.Lock()


def scheda(nome, carte_db):
    c = carte_db.get(nome) or carte_db.get(nome.split(" // ")[0].strip()) or {}
    return c.get("tipo") or c.get("type") or "", c.get("testo") or c.get("oracle") or ""


def tag(nome, carte_db):
    """(produce, vuole) della carta dal suo testo; le terre niente. Una volta per carta (se il testo c'e')."""
    if nome not in _TAG:
        tipo, testo = scheda(nome, carte_db)
        if not testo and not tipo:
            return set(), set()
        _TAG[nome] = (set(), set()) if "Land" in tipo.split(" // ")[0] else ST.tags({"type": tipo, "oracle": testo})
    return _TAG[nome]


def famiglie(padre, figlio, carte_db):
    """Le famiglie che il padre produce e il figlio vuole."""
    return sorted(tag(padre, carte_db)[0] & tag(figlio, carte_db)[1])


def etichetta(fam):
    return ", ".join(NOMI.get(f, f) for f in fam)


def carica(f=None):
    try:
        with open(f or FILE, encoding="utf-8") as g:
            return json.load(g)
    except (OSError, ValueError):
        return {}


def scrivi(f, d):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8") as g:
        json.dump(d, g, ensure_ascii=False, indent=1)
    os.replace(f + ".tmp", f)


PERLA = "#c9cad0"      # il grigio perlato delle linee (Autore, 9 nov 2026: «le vorrei un po' piu' sottili e grigio perlato»)
# la tavolozza delle linee: il colore lo sceglie Autore, il significato anche (effetto, importanza)
COLORI = [("Pearl", PERLA), ("Gold", "#d6ac2e"), ("Blue", "#24baff"), ("Green", "#5cb85c"), ("Red", "#d9534f"), ("Violet", "#a77bdb"), ("Orange", "#f0ad4e"),
          ("White", "#f4f4f6")]
SPESSORI = {1: 1.3, 2: 2.4, 3: 3.8}       # l'importanza in pixel della linea
SPESSORE_MIN, SPESSORE_MAX = 0.6, 6.0       # lo slider dello spessore (10 nov 2026): in pixel, scelto da Autore; vince sull'importanza


class Rete:
    """Le connessioni di un mazzo: [(padre, figlio)] con le famiglie. chiave None: solo in memoria (un mazzo non ancora salvato)."""

    def __init__(self, chiave=None, f=None, f_imparate=None):
        self.chiave, self.f = chiave, f
        self.f_imp = f_imparate or (os.path.join(os.path.dirname(f), "sinergie_imparate.json") if f else IMPARATE)      # accanto al file delle reti
        d = carica(f).get(chiave, {}) if chiave else {}
        self.figli = {}         # (padre, figlio) -> [famiglie]
        for x in d.get("figli", []):
            self.figli[(x[0], x[1])] = list(x[2]) if len(x) > 2 else []
        for x in d.get("tue", []):      # il primo giro: senza verso, il primo nome fa da padre
            if x[0] != x[1] and (x[0], x[1]) not in self.figli and (x[1], x[0]) not in self.figli:
                self.figli[(x[0], x[1])] = []
        # colore e importanza di ogni connessione, scelti da Autore (9 nov 2026: «possiamo dare colore e pesatura alle linee? cosi' da riconoscere le connessioni
        # tra loro per effetto e importanza», scelta «tutti e due tuoi»): (padre, figlio) -> dict(colore="#rrggbb", peso=1|2|3); senza voce, perla e 1
        self.stili = {(x[0], x[1]): dict(colore=x[2], peso=int(x[3]), **({"spessore": float(x[4])} if len(x) > 4 and x[4] is not None else {}))
                      for x in d.get("stili", []) if (x[0], x[1]) in self.figli}

    in_memoria = False      # il Board in modalita' edit (12 nov 2026): la rete si scrive solo col suo Save (salva(forza=True))

    def salva(self, forza=False):
        if not self.chiave or (self.f is None and _ACC.sola_lettura()):      # All accounts: sola lettura
            return
        if self.in_memoria and not forza:
            return
        f = self.f or FILE
        with _CHIAVE:
            d = carica(f)
            d[self.chiave] = dict(figli=[[p, c, fam] for (p, c), fam in self.figli.items()],
                                  stili=[[p, c, st["colore"], st["peso"], st.get("spessore")] for (p, c), st in self.stili.items() if (p, c) in self.figli])
            scrivi(f, d)
            scrivi(self.f_imp, impara(d))

    def lega(self, padre, figlio, carte_db=None):
        """Padre -> figlio. -> "nuova", "tolta" (era gia' li': si toglie) o None (una carta con se stessa)."""
        if not padre or not figlio or padre == figlio:
            return None
        k = (padre, figlio)
        if k in self.figli:
            del self.figli[k]
            self.stili.pop(k, None)
            esito = "tolta"
        else:
            self.figli[k] = famiglie(padre, figlio, carte_db or {})
            esito = "nuova"
        self.salva()
        return esito

    def rinomina(self, vecchio, nuovo, carte_db=None, tieni=False):
        """La carta nuova prende le connessioni della vecchia (Autore, 9 nov 2026: «quando cambio una carta se ha delle connessioni deve mantenerle»): padre resta
        padre, figlio resta figlio, le famiglie si rifanno sui testi nuovi. Una connessione che diventerebbe della carta con se stessa cade. tieni: la vecchia
        resta nel mazzo (in un'altra zona) e tiene anche le sue. -> quante connessioni sono passate."""
        if not vecchio or not nuovo or vecchio == nuovo:
            return 0
        n = 0
        for (p, c) in list(self.figli):
            if vecchio not in (p, c):
                continue
            p2, c2 = (nuovo if p == vecchio else p), (nuovo if c == vecchio else c)
            st = self.stili.get((p, c))
            if not tieni:
                del self.figli[(p, c)]
                self.stili.pop((p, c), None)
            if p2 != c2 and (p2, c2) not in self.figli:
                self.figli[(p2, c2)] = famiglie(p2, c2, carte_db or {})
                if st:
                    self.stili[(p2, c2)] = dict(st)
                n += 1
        if n or not tieni:
            self.salva()
        return n

    def stile(self, padre, figlio):
        """(colore, peso) della connessione: quello scelto, o il grigio perlato e 1."""
        st = self.stili.get((padre, figlio)) or {}
        return st.get("colore") or PERLA, int(st.get("peso") or 1)

    def colore_spessore(self, padre, figlio):
        """(colore, spessore in pixel): lo spessore dello slider, se no quello dell'importanza."""
        col, peso = self.stile(padre, figlio)
        sp = (self.stili.get((padre, figlio)) or {}).get("spessore")
        return col, float(sp) if sp is not None else SPESSORI.get(peso, SPESSORI[1])

    def imposta_stile(self, padre, figlio, colore=None, peso=None, spessore=None):
        """Il colore, l'importanza (1-3) e/o lo spessore in pixel (lo slider) di una connessione che c'e'. L'importanza cancella lo spessore dello slider.
        -> True se e' cambiato qualcosa."""
        k = (padre, figlio)
        if k not in self.figli:
            return False
        vecchio = dict(self.stili.get(k) or {})
        c0, p0 = self.stile(padre, figlio)
        nuovo = dict(colore=colore or c0, peso=max(1, min(3, int(peso or p0))))
        if spessore is not None:
            nuovo["spessore"] = round(max(SPESSORE_MIN, min(SPESSORE_MAX, float(spessore))), 1)
        elif peso is None and vecchio.get("spessore") is not None:
            nuovo["spessore"] = vecchio["spessore"]
        if nuovo == dict(dict(colore=c0, peso=p0), **({"spessore": vecchio["spessore"]} if vecchio.get("spessore") is not None else {})):
            return False
        self.stili[k] = nuovo
        self.salva()
        return True

    def legami(self, nomi):
        """Le connessioni fra le carte date: [(padre, figlio, famiglie)]."""
        nomi = set(nomi)
        return [(p, c, fam) for (p, c), fam in self.figli.items() if p in nomi and c in nomi]


def impara(tutte):
    """Da tutte le connessioni di tutti i mazzi ({chiave: dict(figli=[[padre, figlio, famiglie]])}): coppie padre -> figlio con quanti mazzi, le carte che fanno da
    padre e da figlio piu' spesso, le famiglie che legano padre e figlio."""
    coppie, padri, figli, fam = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    mazzi = 0
    for d in tutte.values():
        righe = d.get("figli", []) if isinstance(d, dict) else []
        if righe:
            mazzi += 1
        for x in righe:
            coppie[(x[0], x[1])] += 1
            padri[x[0]] += 1
            figli[x[1]] += 1
            for f_ in (x[2] if len(x) > 2 else []):
                fam[f_] += 1
    return dict(mazzi=mazzi, coppie=[[p, c, n] for (p, c), n in coppie.most_common()], padri=dict(padri.most_common()), figli=dict(figli.most_common()),
                famiglie={NOMI.get(k, k): n for k, n in fam.most_common()})


def imparate(f=None):
    try:
        with open(f or IMPARATE, encoding="utf-8") as g:
            return json.load(g)
    except (OSError, ValueError):
        return {}


def figli_imparati(padre, f=None):
    """I figli che questa carta ha avuto nei mazzi: {figlio: quante volte}."""
    return {c: n for p, c, n in imparate(f).get("coppie", []) if p == padre}


def prova():
    import tempfile
    cart = tempfile.mkdtemp()
    f, fi = os.path.join(cart, "rete.json"), os.path.join(cart, "imparate.json")
    db = {"Token Maker": dict(tipo="Creature — Human", testo="When this creature enters, create two 1/1 white Soldier creature tokens."),
          "Anthem": dict(tipo="Enchantment", testo="Creatures you control get +1/+1."),
          "Sac Outlet": dict(tipo="Creature — Vampire", testo="Sacrifice another creature: Each opponent loses 1 life."),
          "Death Payoff": dict(tipo="Creature — Zombie", testo="Whenever a creature you control dies, draw a card."),
          "Vanilla": dict(tipo="Creature — Bear", testo="")}
    casi = []
    r = Rete("build:x", f, fi)
    casi.append(("padre -> figlio: una connessione nuova", r.lega("Token Maker", "Anthem", db) == "nuova" and ("Token Maker", "Anthem") in r.figli))
    casi.append(("le famiglie dal testo: pedine per chi le vuole", "swarm" in r.figli[("Token Maker", "Anthem")]))
    casi.append(("il verso conta: Anthem -> Token Maker e' un'altra", r.lega("Anthem", "Token Maker", db) == "nuova" and len(r.figli) == 2))
    casi.append(("rifatta, si toglie", r.lega("Anthem", "Token Maker", db) == "tolta" and len(r.figli) == 1))
    casi.append(("negativa: una carta con se stessa no", r.lega("Vanilla", "Vanilla", db) is None and len(r.figli) == 1))
    r.lega("Sac Outlet", "Death Payoff", db)
    r2 = Rete("build:x", f, fi)
    casi.append(("salvata e ripresa", r2.figli == r.figli))
    casi.append(("le connessioni fra le carte che ci sono", [x[:2] for x in r2.legami(["Token Maker", "Anthem", "Vanilla"])] == [("Token Maker", "Anthem")]))
    r3 = Rete("build:y", f, fi)
    r3.lega("Token Maker", "Anthem", db)
    imp = imparate(fi)
    casi.append(("l'imparato: la stessa coppia in due mazzi conta 2", imp.get("mazzi") == 2 and ["Token Maker", "Anthem", 2] in imp.get("coppie", [])
                 and imp["padri"].get("Token Maker") == 2 and imp["famiglie"].get("go wide") == 2))
    casi.append(("i figli imparati di una carta", figli_imparati("Token Maker", fi) == {"Anthem": 2}))
    r3.lega("Token Maker", "Anthem", db)
    casi.append(("tolta una connessione, l'imparato scende", figli_imparati("Token Maker", fi) == {"Anthem": 1}))
    d = carica(f)
    d["vecchio"] = dict(tue=[["Anthem", "Vanilla", "beatdown"]], si=[], no=[])
    scrivi(f, d)
    casi.append(("il primo giro (senza verso) si riprende col primo come padre", list(Rete("vecchio", f, fi).figli) == [("Anthem", "Vanilla")]))
    casi.append(("negativa: nessuna famiglia fra due carte senza legame nel testo", famiglie("Vanilla", "Anthem", db) == []))
    # la carta sostituita: le connessioni passano alla nuova, coi versi di prima e le famiglie sui testi nuovi
    rr = Rete("build:z", f, fi)
    rr.lega("Vanilla", "Anthem", db); rr.lega("Sac Outlet", "Vanilla", db)
    n = rr.rinomina("Vanilla", "Token Maker", db)
    casi.append(("rinominata: padre resta padre, figlio resta figlio", n == 2 and set(rr.figli) == {("Token Maker", "Anthem"), ("Sac Outlet", "Token Maker")}))
    casi.append(("rinominata: le famiglie si rifanno sul testo nuovo e il file si aggiorna", "swarm" in rr.figli[("Token Maker", "Anthem")]
                 and set(Rete("build:z", f, fi).figli) == set(rr.figli)))
    rr.lega("Anthem", "Death Payoff", db)
    n = rr.rinomina("Anthem", "Death Payoff", db)
    casi.append(("rinominata sulla carta con cui era legata: quella connessione cade", n == 1 and ("Death Payoff", "Death Payoff") not in rr.figli
                 and ("Token Maker", "Death Payoff") in rr.figli and not any("Anthem" in k for k in rr.figli)))
    rr.lega("Sac Outlet", "Vanilla", db)
    n = rr.rinomina("Vanilla", "Anthem", db, tieni=True)
    casi.append(("la vecchia che resta nel mazzo tiene le sue, e la nuova le prende", n == 1 and ("Sac Outlet", "Vanilla") in rr.figli and ("Sac Outlet", "Anthem") in rr.figli))
    prima = dict(rr.figli)
    casi.append(("negativa: una carta senza connessioni non cambia niente", rr.rinomina("Ghost", "Vanilla", db) == 0 and rr.figli == prima))
    # colore e importanza della linea, scelti da Autore: di partenza perla e 1; si salvano, seguono la carta sostituita, cadono con la connessione
    rs = Rete("build:stili", f, fi)
    rs.lega("Token Maker", "Anthem", db)
    casi.append(("di partenza la linea e' grigio perlato, importanza 1", rs.stile("Token Maker", "Anthem") == (PERLA, 1)))
    casi.append(("colore e importanza si scelgono e si salvano", rs.imposta_stile("Token Maker", "Anthem", colore="#d9534f", peso=3)
                 and Rete("build:stili", f, fi).stile("Token Maker", "Anthem") == ("#d9534f", 3)))
    casi.append(("negativa: una connessione che non c'e' non prende uno stile", not rs.imposta_stile("Anthem", "Vanilla", colore="#d9534f") and ("Anthem", "Vanilla") not in rs.stili))
    rs.rinomina("Token Maker", "Vanilla", db)
    casi.append(("la carta sostituita porta lo stile della sua linea", rs.stile("Vanilla", "Anthem") == ("#d9534f", 3)))
    rs.lega("Vanilla", "Anthem", db); rs.lega("Vanilla", "Anthem", db)
    casi.append(("tolta e rifatta, la linea torna perla e 1", rs.stile("Vanilla", "Anthem") == (PERLA, 1)))
    casi.append(("lo slider: lo spessore in pixel vince sull'importanza, si salva, ha i suoi limiti", rs.imposta_stile("Vanilla", "Anthem", spessore=4.24)
                 and Rete("build:stili", f, fi).colore_spessore("Vanilla", "Anthem") == (PERLA, 4.2)
                 and rs.imposta_stile("Vanilla", "Anthem", spessore=99) and rs.colore_spessore("Vanilla", "Anthem")[1] == SPESSORE_MAX))
    casi.append(("negativa: lo stesso spessore non cambia niente, l'importanza lo cancella", not rs.imposta_stile("Vanilla", "Anthem", spessore=SPESSORE_MAX)
                 and rs.imposta_stile("Vanilla", "Anthem", peso=2) and rs.colore_spessore("Vanilla", "Anthem")[1] == SPESSORI[2]))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
