"""Il passo 8 del motore di partita: giocatori finti e simulazione (14 ott 2026).

Autore, 14 ott 2026 (handoff, §5 passo 8): «due mazzi veri che giocano fra loro con scelte semplici, poi la ricerca
di mosse (guardare avanti), confrontata con le partite vere dei log». Questo file e' il passo 8.1, le scelte semplici:
  - i mazzi veri: le 40 carte e il sideboard di Autore, letti dal «deckMessage» dei log di Arena delle 44 partite di
    Quick Draft FRA (10 mazzi distinti), scritti in `mazzi_veri.json` con la partita da cui vengono (catena dei dati);
  - `Semplice`: un giocatore che sceglie con regole da giocatore, non da regolamento (le regole le fa rispettare il
    motore, che rifiuta ogni mossa illegale). Mano: tiene 2-5 terre. Gioca la terra, poi i permanenti dal costo piu' alto
    che riesce a pagare; tiene gli istantanei per il turno dell'altro (contromagie sulle magie che contano, rimozioni
    sugli attaccanti, il resto alla fine del turno dell'altro); attacca se nessun bloccante lo uccide senza morire, o se
    il danno basta a chiudere; blocca se sopravvive, scambia se ci guadagna, si sacrifica se il danno in arrivo e' letale;
    i bersagli: chi fa male va sull'avversario e preferisce chi uccide, chi aiuta va sulla propria creatura migliore
    (`POLARITA`, una voce per ogni effetto con bersaglio delle carte FRA; una voce mancante e' rossa nelle prove);
  - `partita(a, b, seme, g0, g1)`: il motore del passo 7 (`effetti.Partita` su `effetti.TavoloEffetti`) con l'inizio di
    Arena misurato sul Quick (`modo="arena_bo1", campioni=2`, Misura_Smoothing_Bo1.md) e le carte fuori dalla partita
    (400.11, 100.4b: il sideboard vero e le terre base del Limited).
Quello che le scelte semplici NON sono: un modo di giocare bene. Sono il giocatore delle simulazioni (le «rollout») del
guardare avanti, il passo 8.2; il loro metro e' battere chi sceglie a caso e il giocatore base del passo 7.

    py -I -X utf8 Motore_Partita/simula.py --mazzi            rilegge i mazzi dai log e riscrive mazzi_veri.json
    py -I -X utf8 Motore_Partita/simula.py --partita A B S    una partita fra il mazzo A e il mazzo B (indici), seme S
    py -I -X utf8 Motore_Partita/simula.py --torneo N         ogni mazzo contro ogni altro, N semi per coppia
    py -I -X utf8 Motore_Partita/simula.py --prova            le prove
"""
import json
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import carte_fra as F
import combattimento as C
import effetti as E
import mana as M
from inizio import inizia
from mana import NonCoperto
from tavolo import costituzione, forza, parole

QUI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(QUI)
MAZZI = os.path.join(QUI, "mazzi_veri.json")
BASI = ("Plains", "Island", "Swamp", "Mountain", "Forest")


# ====================================================================== i mazzi veri
def leggi_mazzi():
    """Dai log delle partite di Quick Draft FRA (le stesse del riscontro): il «deckMessage» di Arena, cioe' le 40 carte
    e il sideboard con cui Autore ha giocato. -> [{"mazzo", "sideboard", "partite", "log"}], uno per mazzo distinto."""
    import riscontro as R
    visti = {}
    for id_, log in R.partite():
        mazzo, side = mazzo_dal_log(log, id_)
        k = tuple(mazzo)
        if k not in visti: visti[k] = {"mazzo": mazzo, "sideboard": side, "partite": [], "log": os.path.relpath(log, ROOT)}
        visti[k]["partite"].append(id_)
    return list(visti.values())


def mazzo_dal_log(log, id_=""):
    """Il «deckMessage» di Arena in un log: le 40 carte e il sideboard con cui Autore ha giocato, per nome. Un posto
    solo per leggerlo: la lista dei mazzi veri e, dal 16 ott 2026, il confronto sulle partite nuove (confronto_log).
    -> (mazzo, sideboard)."""
    return mazzo_da_testo(open(log, encoding="utf-8", errors="replace").read(), id_)


def mazzo_da_testo(txt, id_=""):
    """Il deckMessage in un pezzo di log, anche una riga sola (dal vivo, cercatore_vivo.py)."""
    import riscontro as R
    m = re.search(r'"deckMessage": *\{ *"deckCards": *\[([^\]]*)\](?:, *"sideboardCards": *\[([^\]]*)\])?', txt)
    if not m: raise RuntimeError(f"{id_}: il log non ha il deckMessage")
    mazzo = sorted(R.nome(int(x)) for x in m.group(1).split(","))
    side = sorted(R.nome(int(x)) for x in (m.group(2) or "").split(",") if x.strip())
    if None in mazzo or None in side: raise RuntimeError(f"{id_}: una carta del mazzo non e' nel database di Arena")
    return mazzo, side


def scrivi_mazzi():
    mazzi = leggi_mazzi()
    for m in mazzi:
        F.mazzo(m["mazzo"]); F.mazzo(m["sideboard"])                     # NonCoperto se una carta non e' intera
        m["nome"] = nome_mazzo(m["mazzo"])
    d = {"fonte": "deckMessage dei log di Arena (Log_Arena/partite/<ID>/arena.log), partite di Quick Draft FRA",
         "scritto": datetime.now().strftime("%Y-%m-%dT%H:%M"), "mazzi": mazzi}
    json.dump(d, open(MAZZI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return mazzi


def nome_mazzo(nomi):
    """I colori dalle terre base del mazzo e la data della prima partita: «UR 13 ott»."""
    c = Counter(n for n in nomi if n in BASI)
    return "".join("WUBRG"[BASI.index(b)] for b in BASI if c[b])


def mazzi_veri():
    if not os.path.exists(MAZZI): return scrivi_mazzi()
    return json.load(open(MAZZI, encoding="utf-8"))["mazzi"]


# ====================================================================== il valore delle cose (scelte da giocatore)
def mv(o):
    return 0 if o.carta is None or o.carta.pedina else M.valore(o.carta.car.get("costo") or "")


def valore(o):
    """Quanto conta un permanente per chi gioca semplice: una creatura per forza, costituzione, parole chiave e costo; un
    planeswalker per fedelta' e costo; il resto per il costo. Non e' una regola: e' il metro del giocatore."""
    if o.carta is None: return 0
    tipi = o.carta.tipi
    if "creature" in tipi:
        return forza(o) + costituzione(o) + 0.5 * len(parole(o)) + 0.5 * mv(o)
    if "planeswalker" in tipi: return o.segnalini["fedelta"] + mv(o)
    if "land" in tipi: return 0.5
    return 0.5 + 0.5 * mv(o)


def uccide(a, b):
    """a, combattendo, uccide b? (danno pari alla forza, 510.1a; tocco mortale 702.2b; indistruttibile 702.12b)."""
    if "indestructible" in parole(b): return False
    f = forza(a)
    return f > 0 and ("deathtouch" in parole(a) or f >= costituzione(b) - b.danno)


def potrebbe_bloccare(p, b, a):
    """b potrebbe bloccare a, se a attaccasse? La regola la dice il motore (509.1a-b, 702.9b, 613.11), che pero' la
    controlla solo per chi attacca gia': a si mette fra gli attaccanti per il tempo della domanda, poi si toglie."""
    prima = p.attaccanti
    p.attaccanti = {**prima, a: p.difensore()}
    try: return p.puo_bloccare(b, a)
    finally: p.attaccanti = prima


# ====================================================================== la polarita' degli effetti con bersaglio
# Per ogni effetto che le carte FRA danno a un bersaglio: -1 fa male (va sull'avversario), +1 aiuta (va su di se'),
# 0 conta solo il valore (Uldaros: le carte nei cimiteri). «pompa», «segnalini» e «base» dipendono dai numeri. Una voce
# per ogni effetto letto da carte_fra (la prova «polarita' completa» e' rossa se un effetto nuovo manca).
POLARITA = {
    "attacca": +1, "cima_o_fondo": -1, "contrasta": -1, "contrasta_salvo": -1, "dai_flashback": +1, "dai_mana": +1,
    "dai_parole": +1, "danno": -1, "distruggi": -1, "esilia": -1, "esilia_e_lancia_copie": 0, "esilia_finche": -1,
    "esilia_scelta_da_te": -1, "esilia_se_muore": -1, "in_fondo": 0, "in_grimorio": -1, "mescola_nel_grimorio": -1,
    "non_bloccabile": +1, "prepara": +1, "rimbalza": -1, "ritorna": +1, "sacrifica": -1, "scarta_scelta_da_te": -1,
    "segnalini_della_fonte": +1, "stappa": +1, "stordisci": -1, "tappa": -1, "togli_abilita": -1,
    "togli_segnalini_scelti": -1, "pompa": None, "segnalini": None, "base": None,
}
# gli effetti che tolgono il bersaglio dal campo (o la magia dalla pila): con questi un bersaglio «uccide» sempre
TOGLIE = {"contrasta", "distruggi", "esilia", "esilia_finche", "esilia_se_muore", "in_grimorio", "mescola_nel_grimorio",
          "rimbalza", "cima_o_fondo", "esilia_scelta_da_te", "sacrifica"}


def segno(d):
    """La polarita' di un effetto: -1, 0, +1."""
    k = d.get("fa")
    if k not in POLARITA: raise NonCoperto(f"il giocatore semplice non sa se «{k}» aiuta o fa male (POLARITA)")
    s = POLARITA[k]
    if s is not None: return s
    if k == "base": return -1 if d.get("p", 0) + d.get("t", 0) <= 2 else +1                    # 0/0, 1/1 contro 4/5
    if k == "segnalini": return -1 if d.get("tipo") == "-1/-1" else +1
    p_, t_ = d.get("p", 0), d.get("t", 0)                                                        # pompa
    if isinstance(p_, dict) or isinstance(t_, dict): return +1
    return -1 if (p_ < 0 or t_ < 0) else +1


def effetti_su(fa, k):
    return [d for d in fa if isinstance(d.get("chi"), str) and d["chi"] == f"bersaglio:{k}"]


def efficace(d, x):
    """L'effetto ostile d toglie di mezzo x? (una stima da giocatore: il danno contro la costituzione rimasta, il -N/-N
    contro la costituzione, gli effetti che tolgono dal campo sempre)."""
    if E._e_giocatore(x): return False
    k = d.get("fa")
    if k in TOGLIE: return True
    if x.carta is None or "creature" not in x.carta.tipi: return False
    if k == "danno" and isinstance(d.get("n"), int): return d["n"] >= costituzione(x) - x.danno
    if k == "pompa" and isinstance(d.get("t"), int): return costituzione(x) + d["t"] - x.danno <= 0
    if k == "base" and isinstance(d.get("t"), int): return d["t"] - x.danno <= 0
    return False


# ====================================================================== il giocatore semplice
class Semplice:
    """Scelte semplici e sensate, per far giocare due mazzi veri. Ogni scelta e' un'opinione da giocatore (le regole le
    fa il motore). rotto=True ribalta i bersagli (le rimozioni sulle proprie creature, gli aiuti sull'avversario): e' la
    prova negativa del metro."""

    def __init__(self, seme=0, rotto=False):
        self.rotto = rotto
        self._no = set()                  # (turno, fase, passo, oggetto, pila): mosse a cui ha rinunciato (bersagli vuoti)
        self._attivate = set()            # (turno, oggetto, abilita'): una volta per turno
        self._ultima = None               # (chiave della mossa, eventi prima): se il motore la rifiuta (734) non la ripropone

    # ------------------------------------------------------------------ l'inizio (103.5)
    def mulligan(self, i, mano, k):
        terre = sum(1 for c in mano if "land" in c.carta.tipi)
        return k < 2 and not (2 <= terre <= 5)

    def fondo(self, i, mano, k):
        terre = [c for c in mano if "land" in c.carta.tipi]
        altre = sorted((c for c in mano if "land" not in c.carta.tipi), key=lambda c: -mv(c))
        via = terre[:max(0, len(terre) - 3)] + altre                       # prima le terre oltre la terza, poi le piu' care
        via = (via + terre)[:k]
        return via

    # ------------------------------------------------------------------ la priorita'
    def _chiave(self, p, o):
        return (p.t.turno_numero, p.fase, p.passo, o.n, len(p.t.pila))

    def agisci(self, p, i):
        if self._ultima is not None and any(e.tipo == "illegale" for e in p.t.eventi[self._ultima[1]:]):
            self._no.add(self._ultima[0])
        self._ultima = None
        a = self._agisci(p, i)
        if a is not None and a[0] in ("lancia", "terra", "avventura", "alternativo"):
            self._ultima = (self._chiave(p, a[1]), len(p.t.eventi))
        return a

    def _agisci(self, p, i):
        t, mio = p.t, p.attivo == i
        mano = t.giocatori[i].mano
        esiliate = [o for o in t.esilio if p.permesso(i, o)]
        if mio and p.da_stregoneria(i):
            terra = self._terra(p, i, mano + esiliate)
            if terra is not None: return ("terra", terra)
            if p.fase == "principale_1":
                a = self._mosse_nuove(p, i, mano)
                if a: return a
                for o in self._da_lanciare(p, i, mano + esiliate, istantanei=False):
                    return ("lancia", o, p.x_massimo(i, o) or 0 if "{X}" in (o.carta.car.get("costo") or "") else 0, None)
                a = self._attivabile(p, i, sorcery=True)
                if a: return a
            if p.fase == "principale_2":
                a = self._attivabile(p, i, sorcery=False)
                if a: return a
            return None
        if mio: return None
        # il turno dell'altro: risposte
        if t.pila:
            cima = t.pila[-1]
            if cima.controllore != i and cima.carta is not None and (mv(cima) >= 3 or "creature" in cima.carta.tipi):
                for o in self._da_lanciare(p, i, mano, istantanei=True):
                    if any(d.get("fa") in ("contrasta", "contrasta_salvo") for d in self._fa_di(o)): return self._lancio(p, i, o)
            return None
        if p.fase == "combattimento" and p.passo == "bloccanti" and p.attaccanti:
            for o in self._da_lanciare(p, i, mano, istantanei=True):
                if self._ostile(o): return self._lancio(p, i, o)
        if p.fase == "finale" and p.passo == "finale":
            for o in self._da_lanciare(p, i, mano + esiliate, istantanei=True):
                if not any(d.get("fa") in ("contrasta", "contrasta_salvo") for d in self._fa_di(o)): return self._lancio(p, i, o)
            a = self._attivabile(p, i, sorcery=False)
            if a: return a
        return None

    def _mosse_nuove(self, p, i, mano):
        """Le mosse dei set nuovi (14 nov 2026), solo per le carte che le hanno (FRA non ne ha: le sue partite non cambiano):
        l'avventura prima della creatura (716.3: poi la creatura si lancia dall'esilio); un costo alternativo (warp,
        airbend...) quando il costo normale non si paga."""
        if not hasattr(p, "alternativi"): return None
        for o in mano:
            if self._chiave(p, o) in self._no or o.carta is None or not o.fisica.car.get("avventura"): continue
            o.come_avventura = True
            try: ok = p.puo_lanciare(i, o, 0)
            finally: o.come_avventura = False
            if ok: return ("avventura", o, 0, None)
        proprie = [o for o in p.t.esilio if o.proprietario == i and getattr(o, "alternativi_dati", None)]
        for o in mano + proprie:
            if self._chiave(p, o) in self._no or "land" in o.carta.tipi: continue
            if o in mano and p.puo_lanciare(i, o, 0): continue
            for alt in p.alternativi(i, o):
                p._alternativo[o.n] = alt
                try: ok = p.puo_lanciare(i, o, 0)
                finally: p._alternativo.pop(o.n, None)
                if ok: return ("alternativo", o, alt["nome"], 0, None)
        return None

    def _lancio(self, p, i, o):
        x = (p.x_massimo(i, o) or 0) if "{X}" in (o.carta.car.get("costo") or "") else 0
        return ("lancia", o, x, None)

    def _terra(self, p, i, mano):
        terre = [o for o in mano if "land" in o.carta.tipi and self._chiave(p, o) not in self._no and p.puo_giocare_terra(i, o)]
        if not terre: return None
        # la terra che da' il colore che manca di piu' ai costi della mano
        voglia = Counter(c for o in mano if "land" not in o.carta.tipi for c in M.colori(o.carta.car.get("costo") or ""))
        def punti(o):
            return sum(voglia[c] for c in "WUBRG" if any(c in pr for pr in self._produce(p, o)))
        return max(terre, key=punti)

    def _produce(self, p, o):
        try: return [str(x) for x in p.produzioni(o)]
        except Exception: return []

    def _fa_di(self, o):
        car = o.carta.car
        out = list(car.get("fa") or [])
        for m in car.get("modi") or []: out += list(m.get("fa") or [])
        return out

    def _ostile(self, o):
        return any(isinstance(d.get("chi"), str) and d["chi"].startswith("bersaglio") and d.get("fa") in POLARITA and segno(d) < 0
                   for d in self._fa_di(o))

    def _da_lanciare(self, p, i, carte, istantanei):
        """Le carte che puo' lanciare adesso, dalla piu' cara: i permanenti (e le stregonerie) nella propria fase
        principale, gli istantanei e il lampo nel turno dell'altro. Non quelle a cui ha gia' rinunciato qui."""
        out = []
        for o in carte:
            if "land" in o.carta.tipi or self._chiave(p, o) in self._no: continue
            rapido = "instant" in o.carta.tipi or "flash" in (o.carta.car.get("parole") or [])
            if rapido != istantanei: continue
            if p.puo_lanciare(i, o, (p.x_massimo(i, o) or 0) if "{X}" in (o.carta.car.get("costo") or "") else 0): out.append(o)
        return sorted(out, key=lambda o: (-("creature" in o.carta.tipi), -mv(o)))

    def _attivabile(self, p, i, sorcery):
        """Le abilita' attivate (non di mana): di fedelta' nella prima fase principale (il + se non c'e' un - che uccide),
        le altre una volta per turno, mai quelle che sacrificano o esiliano la fonte senza un bersaglio che conta."""
        t = p.t
        for o in list(t.campo):
            if o.controllore != i: continue
            abil = [(k, ab) for k, ab in t.abilita_di(o) if ab.get("tipo") == "attivata"]
            if "fedelta" in str([ab.get("fedelta") for _, ab in abil]) and not sorcery: continue
            fed = [(k, ab) for k, ab in abil if isinstance(ab.get("fedelta"), int)]       # il -X (107.3k) non lo usa: scelta sua
            if fed and sorcery:
                ordine = sorted(fed, key=lambda kab: (-(kab[1]["fedelta"] < 0 and self._ostile_ab(kab[1])), -kab[1]["fedelta"]))
                for k, ab in ordine:
                    if ab["fedelta"] < 0 and o.segnalini["fedelta"] + ab["fedelta"] <= 0 and ab["fedelta"] > -7: continue
                    if (t.turno_numero, o.n, k) in self._attivate: continue
                    if p.puo_attivare(i, o, k):
                        self._attivate.add((t.turno_numero, o.n, k)); return ("attiva", o, k)
                continue
            for k, ab in abil:
                if "fedelta" in ab or (t.turno_numero, o.n, k) in self._attivate: continue
                fa = ab.get("fa") or []
                if all(d.get("fa") == "aggiungi_mana" for d in fa): continue                     # le abilita' di mana le usa il pagatore
                costo = ab.get("costo") if isinstance(ab.get("costo"), dict) else {}
                if (costo.get("sacrifica_se") or costo.get("esilia_se")) and not self._ostile_ab(ab): continue
                equip = any(d.get("fa") == "attacca" for d in fa)
                if equip != sorcery and not (equip and p.fase == "principale_1"): continue
                if p.puo_attivare(i, o, k):
                    self._attivate.add((t.turno_numero, o.n, k)); return ("attiva", o, k)
        return None

    def _ostile_ab(self, ab):
        return any(isinstance(d.get("chi"), str) and d["chi"].startswith("bersaglio") and d.get("fa") in POLARITA and segno(d) < 0
                   for d in ab.get("fa") or [])

    # ------------------------------------------------------------------ i bersagli
    def bersagli(self, p, i, oggetto, reqs, legali, fa=()):
        """Per ogni bersaglio: chi fa male sull'avversario (prima chi l'effetto toglie di mezzo, poi il piu' prezioso;
        il giocatore se nessuna creatura muore), chi aiuta sulla propria cosa migliore. Se una magia o un'abilita'
        attivata non trova un bersaglio che valga, rinuncia (una proposta vuota: il motore la rifiuta e torna indietro,
        734); un innesco invece sceglie comunque (603.3d), il meno peggio."""
        forzato = isinstance(oggetto, E.Abilita) and oggetto.tipo == "innescata"
        mio = lambda x: (x == i) if E._e_giocatore(x) else (x.controllore == i if x.zona in ("campo", "pila") else x.proprietario == i)
        out = []
        for k, (r, lst) in enumerate(zip(reqs, legali)):
            eff = effetti_su(fa, k)
            s = min((segno(d) for d in eff), default=0) if eff else 0
            if self.rotto: s = -s
            q = r.get("quanti", 1)
            def punti(x):
                if E._e_giocatore(x): v = 3.0
                elif x.zona == "pila" or x.zona not in ("campo",): v = mv(x) if x.carta is not None else 0
                else: v = valore(x)
                if s < 0:
                    return (not mio(x), any(efficace(d, x) for d in eff), not E._e_giocatore(x) or not any(
                        not E._e_giocatore(y) and not mio(y) and any(efficace(d, y) for d in eff) for y in lst), v)
                if s > 0: return (mio(x), not E._e_giocatore(x), v)
                return (True, v)
            ordinati = sorted(lst, key=punti, reverse=True)
            if s < 0 and not forzato: ordinati = [x for x in ordinati if not mio(x)]
            if s > 0 and not forzato: ordinati = [x for x in ordinati if mio(x)]
            if r.get("uno_per_tipo"):
                scelti = []
                for x in ordinati:
                    if len(scelti) < q and E.uno_per_tipo(scelti + [x]): scelti.append(x)
                out.append(scelti); continue
            scelti = ordinati[:q]
            if len(scelti) < (r.get("minimo", 0) if r.get("fino_a") else q):
                if forzato: scelti = sorted(lst, key=punti, reverse=True)[:q]
                else:
                    self._rinuncia(p, oggetto); return [[] for _ in reqs]
            out.append(scelti)
        return out

    def _rinuncia(self, p, oggetto):
        fonte = getattr(oggetto, "fonte", None) if isinstance(oggetto, E.Abilita) else oggetto
        if fonte is not None and fonte.carta is not None:
            self._no.add((p.t.turno_numero, p.fase, p.passo, fonte.n, len(p.t.pila) - (1 if oggetto in p.t.pila else 0)))
            for c in list(p.t.esilio) + [o for g in p.t.giocatori for o in g.mano]:
                if c.carta is fonte.carta: self._no.add(self._chiave(p, c))

    def modi(self, p, i, oggetto, modi, legali, minimo, massimo):
        """Il modo che fa male se l'avversario ha creature, poi quello che pesca, poi il primo."""
        avv = [o for o in p.t.campo if o.controllore != i and "creature" in o.carta.tipi] if p.t.campo else []
        def punti(k):
            fa = modi[k].get("fa") or []
            ost = any(isinstance(d.get("chi"), str) and d["chi"].startswith("bersaglio") and segno(d) < 0 for d in fa)
            return (ost and bool(avv), any(d.get("fa") == "pesca" for d in fa), -k)
        return sorted(legali, key=punti, reverse=True)[:max(1, minimo)]

    def sceglie(self, p, i, d):
        return True

    # ------------------------------------------------------------------ il combattimento
    def attacca(self, p, i):
        mie = [o for o in p.t.campo if o.controllore == i and p.puo_attaccare(o)]
        if not mie: return None
        d = p.difensore()
        suoi = [o for o in p.t.campo if o.controllore == d and "creature" in o.carta.tipi and not o.tappato]
        vite = p.t.giocatori[d].vite
        if sum(max(0, forza(o)) for o in mie) >= vite + sum(max(0, forza(o)) for o in suoi):  # basta anche se blocca il meglio
            return {o: d for o in mie}
        out = {}
        for a in mie:
            if forza(a) <= 0: continue
            if "menace" in parole(a) and sum(1 for b in suoi if potrebbe_bloccare(p, b, a)) < 2: out[a] = d; continue
            pericolo = [b for b in suoi if potrebbe_bloccare(p, b, a) and uccide(b, a) and not uccide(a, b)]
            if not pericolo: out[a] = d
        return out

    def blocca(self, p, i):
        att = sorted(p.attaccanti, key=lambda a: -forza(a))
        mie = [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi and not o.tappato]
        if not att or not mie: return None
        scelta, usati = {}, set()
        in_arrivo = sum(max(0, forza(a)) for a in att if p.attaccanti.get(a) == i)
        vite = p.t.giocatori[i].vite
        for a in att:
            if "menace" in parole(a): continue
            liberi = [b for b in mie if b not in usati and p.puo_bloccare(b, a)]
            sopravvive = [b for b in liberi if not uccide(a, b)]
            scambio = [b for b in liberi if uccide(b, a) and valore(b) <= valore(a)]
            b = (min(sopravvive, key=valore) if sopravvive else min(scambio, key=valore) if scambio else
                 min(liberi, key=valore) if liberi and in_arrivo >= vite else None)
            if b is not None:
                scelta[b] = a; usati.add(b)
                if p.attaccanti.get(a) == i: in_arrivo -= max(0, forza(a))
        return scelta

    def scarta(self, p, i, mano, quante):
        terre_in_campo = sum(1 for o in p.t.campo if o.controllore == i and "land" in o.carta.tipi)
        def punti(o):
            if "land" in o.carta.tipi: return 0 if terre_in_campo >= 6 else 20
            return 10 - mv(o)
        return sorted(mano, key=punti)[:quante]


# ====================================================================== la partita fra due mazzi veri
class ArbitroFischia(RuntimeError):
    """La vigilanza ha trovato un errore in una partita simulata: la simulazione si ferma e non da' risultati."""


def partita(a, b, seme, g0, g1, vigila=True, max_turni=200, ferma=True, P=None, T=None, prepara=None, da=None):
    """Il mazzo a (giocatore 0) contro il mazzo b, col motore del passo 7 e l'inizio di Arena del Quick. -> Partita.
    L'arbitro (la vigilanza) e' sempre acceso: regola di Autore del 14 ott 2026, «tu sei arbitro con le regole in mano
    per vedere che le partite siano sempre corrette». vigila=False solo dove una prova lo chiede apposta (lo stesso
    motore senza il conto a parte); ferma=False lascia gli errori in p.err per le prove che li vogliono contare.
    P, T: la partita e il tavolo (di norma quelli del passo 7; le prove ci mettono un motore rotto apposta).
    prepara(p): le prove del passo 8.2 costruiscono una situazione dopo l'inizio e il controllo delle 20 vite (sempre la
    stessa, quindi la partita si rifa' dal seme).
    da: una copia della partita fatta a inizio turno (guarda_avanti.copia, passo 8.6), costruita da questa stessa funzione
    con gli stessi argomenti: si riprende da li' con i giocatori g0, g1 (niente inizio, niente prepara: sono gia' fatti)."""
    g = {0: g0, 1: g1}
    if da is not None: p = da
    else:
        P, T = P or E.Partita, T or E.TavoloEffetti
        fuori = [F.mazzo(a["sideboard"]), F.mazzo(b["sideboard"])]                                  # 400.11, 100.4b
        t = T([F.mazzo(a["mazzo"]), F.mazzo(b["mazzo"])], seme=seme, fuori=fuori, basi_fuori=F.mazzo(list(BASI)))
        inizia(t, modo="arena_bo1", campioni=2,
               decidi=lambda i, mano, k, dette: g[i].mulligan(i, mano, k) if hasattr(g[i], "mulligan") else False,
               fondo=lambda i, mano, k: g[i].fondo(i, mano, k) if hasattr(g[i], "fondo") else mano[-k:] if k else [])
        V = E.vigila(P) if vigila else P
        if vigila and ferma:
            class Arbitro(V):                     # al primo fischio la partita si ferma: non si gioca oltre un errore
                def _sbaglia(self, msg):
                    super()._sbaglia(msg)
                    raise ArbitroFischia(f"seme {seme}, {a.get('nome', '?')} contro {b.get('nome', '?')}, turno {self.t.turno_numero}: {msg}")
            V = Arbitro
        p = V(t)
        if vigila and any(g.vite != 20 for g in t.giocatori):                                     # 119.1
            p._sbaglia(f"vite iniziali {[g.vite for g in t.giocatori]}, non 20 (119.1)")
        if prepara: prepara(p)
    def dopo(p):
        if not vigila: return
        if any(c.durata == "fine_turno" for c in p.t.continui) and not p.t.finita:
            p._sbaglia("un effetto «fino a fine turno» e' sopravvissuto alla pulizia (514.2)")
        for g in p.t.giocatori:                                                                    # 704.5a, 104.3b: nessuna carta FRA
            if g.vite <= 0 and not g.perso:                                                        # cambia questa regola (14 ott 2026)
                p._sbaglia(f"G{g.i + 1} ha {g.vite} vite e non ha perso (704.5a)")
    p.gioca(g, max_turni=max_turni, dopo_ogni_turno=dopo)
    if vigila:
        controlli_finali(p)
        if p.err and ferma:
            raise ArbitroFischia(f"seme {seme}, {a.get('nome', '?')} contro {b.get('nome', '?')}: {p.err[0]}"
                                 + (f" (e altri {len(p.err) - 1})" if len(p.err) > 1 else ""))
    return p


def come_finisce(p):
    """Perche' e' finita: la regola dell'evento «perde» o «vince» (704.5a vite a 0 o meno, 704.5b grimorio vuoto, 104.2b
    una carta che fa vincere), o None se non e' finita."""
    for e in reversed(p.t.eventi):
        if e.tipo in ("perde", "vince"): return e.causa
    return None


def ospite(t, n):
    """L'arbitro, senza il motore: a chi era attaccato l'oggetto n (aura o equipaggiamento). L'ultimo evento «attaccata»
    (701.3a); un'aura entrata gia' attaccata risolvendosi (608.3c) non ha l'evento: allora il campo dell'oggetto."""
    for e in reversed(t.eventi):
        if e.tipo == "attaccata" and e.vecchio == n: return e.nuovo
    o = getattr(t, "oggetti", {}).get(n)
    return getattr(o, "attaccato_a", None)


SOSTITUZIONI_MORTE = {"122.1h", "614.1a"}   # «if it would be put into a graveyard / would die, exile it instead»


def di_stato(e):
    """Un evento del giro di azioni di stato (704.5): anche la morte sostituita con l'esilio (614, 122.1h: il motore scrive
    la causa della sostituzione, perche' e' quella che decide dove va la carta; seme 616 e 666, 14 ott 2026)."""
    return str(e.causa).startswith("704.5") or (e.tipo == "zona" and e.da == "campo" and e.a == "esilio" and e.causa in SOSTITUZIONI_MORTE)


def controlli_finali(p):
    """I conti a fine partita delle partite a caso del passo 7, rifatti da fuori: la pila dagli eventi, ogni pagamento
    col costo davvero fissato (601.2f-h), il mana che torna (106.4); e chi ha perso, perche' (704.5a-b, 104.2b)."""
    if p.t.finita and p.t.vincitore is not None:
        perdente = p.t.giocatori[1 - p.t.vincitore]
        ok = perdente.vite <= 0 or perdente.grimorio.perso or come_finisce(p) == "104.2b"
        if not ok: p._sbaglia(f"G{perdente.i + 1} ha perso con {perdente.vite} vite e il grimorio a posto ({come_finisce(p)})")
        if p.t.giocatori[p.t.vincitore].vite <= 0: p._sbaglia(f"ha vinto G{p.t.vincitore + 1} con {p.t.giocatori[p.t.vincitore].vite} vite (704.5a)")
    if p.t.finita:                                                                                 # 104.1: finita subito.
        k = max((j for j, e in enumerate(p.t.eventi) if e.tipo in ("perde", "vince")), default=None)  # Dopo la sconfitta solo cio'
        if k is not None:                                                                          # che era simultaneo (704.3):
            dopo = p.t.eventi[k + 1:]                                                              # le altre azioni di stato
            via = {e.vecchio for e in dopo if e.tipo == "zona" and di_stato(e)}                        # dello stesso giro. Chi
            arrivati = {e.nuovo for e in dopo if e.tipo == "zona" and di_stato(e)}                     # se ne va nel giro non
            for e in dopo:                                                                         # fa scattare niente: la pedina
                if e.tipo == "cessa" and e.vecchio not in arrivati: continue                       # che cessa (704.5d), l'aura
                if e.tipo in ("staccata", "zona") and e.causa in ("704.5n", "704.5m"):             # che cade e l'equipaggiamento
                    if ospite(p.t, e.vecchio) not in via: continue                                 # che si stacca (704.5m-n)
                elif di_stato(e): continue                                                         # sarebbero un giro dopo
                p._sbaglia(f"dopo la fine della partita: {e.tipo} {e.causa} (104.1)"); break
    p.err += E.pila_dagli_eventi(p.t)
    for costo, pag, x, fonti, riserva in p.costi_magie + p.pagati_abilita:
        perche = M.valida(pag, costo, fonti, riserva, x)
        if perche: p._sbaglia(f"pagamento illegale di {costo}: {perche}")
    speso = sum(sum(pg.spesa) for _, pg, _, _, _ in p.pagati) + sum(sum(pg.spesa) for _, pg, _, _, _ in p.pagati_abilita)
    if p.prodotto + p.mana_da_effetti != speso + p.perso:
        p._sbaglia(f"mana prodotto {p.prodotto} piu' {p.mana_da_effetti} dagli effetti, speso {speso}, perso {p.perso} (106.4)")


def wilson(v, n, z=1.96):
    """L'intervallo di Wilson al 95% per v vittorie su n partite."""
    if n == 0: return (0.0, 1.0)
    f = v / n
    c = (f + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(f * (1 - f) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - m, c + m)


def sfida(crea0, crea1, semi, mazzi=None, vigila=True):
    """crea0 contro crea1 su ogni coppia di mazzi (i mazzi scambiati a semi alterni, cosi' nessuno ha il mazzo migliore).
    crea(seme) -> giocatore. -> (vittorie di 0, partite decise, pari o finite per tempo, errori)."""
    mazzi = mazzi or mazzi_veri()
    v = n = altro = 0
    err = []
    for s in semi:
        a, b = s % len(mazzi), (s * 7 + 3) % len(mazzi)
        if a == b: b = (b + 1) % len(mazzi)
        scambia = s % 2
        g = [crea0(s * 2 + 1), crea1(s * 2 + 2)]
        m = [mazzi[a], mazzi[b]]
        if scambia: g, m = g[::-1], m[::-1]
        p = partita(m[0], m[1], s, g[0], g[1], vigila=vigila, ferma=False)
        err += [f"seme {s}: {e}" for e in p.err] if vigila else []
        w = p.t.vincitore
        if w is None or not p.t.finita: altro += 1; continue
        n += 1
        if (w == 0) != bool(scambia): v += 1
    return v, n, altro, err


# ====================================================================== le prove
def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    t0 = time.time()
    mazzi = mazzi_veri()

    # i mazzi veri, dal log
    letti = leggi_mazzi()
    caso("i mazzi di mazzi_veri.json sono quelli dei log", sorted(map(lambda m: m["mazzo"], letti)) == sorted(m["mazzo"] for m in mazzi),
         f"{len(letti)} nei log, {len(mazzi)} nel file")
    caso("10 mazzi distinti, 44 partite, 40 carte ciascuno", len(mazzi) == 10 and sum(len(m["partite"]) for m in mazzi) == 44
         and all(len(m["mazzo"]) == 40 for m in mazzi), f"{len(mazzi)} mazzi, {sum(len(m['partite']) for m in mazzi)} partite")
    try:
        for m in mazzi: F.mazzo(m["mazzo"]); F.mazzo(m["sideboard"])
        caso("ogni carta dei mazzi e dei sideboard e' intera (nessun NonCoperto)", True)
    except NonCoperto as e: caso("ogni carta dei mazzi e dei sideboard e' intera (nessun NonCoperto)", False, str(e))

    # la polarita': una voce per ogni effetto con bersaglio
    mancano = set()
    def giro(x):
        if isinstance(x, dict):
            if isinstance(x.get("fa"), str) and isinstance(x.get("chi"), str) and x["chi"].startswith("bersaglio") \
                    and x["fa"] not in POLARITA: mancano.add(x["fa"])
            for v in x.values(): giro(v)
        elif isinstance(x, list):
            for v in x: giro(v)
    for tr in F.tutte().values(): giro(tr.voce[2])
    caso("POLARITA ha una voce per ogni effetto con bersaglio delle 285 carte", not mancano, str(sorted(mancano)))
    caso("segno: -3/-3 fa male, +2/+2 aiuta, base 0/0 fa male, base 4/5 aiuta, -1/-1 fa male",
         segno({"fa": "pompa", "p": -3, "t": -3}) < 0 and segno({"fa": "pompa", "p": 2, "t": 2}) > 0
         and segno({"fa": "base", "p": 0, "t": 0}) < 0 and segno({"fa": "base", "p": 4, "t": 5}) > 0
         and segno({"fa": "segnalini", "tipo": "-1/-1"}) < 0)

    # le scelte, una per una, su un tavolo costruito
    import prove_carte_fra as PF
    def tavolo(m0, m1, seme=1):
        t = E.TavoloEffetti([F.mazzo(m0), F.mazzo(m1)], seme=seme, fuori=[[], []], basi_fuori=[])
        inizia(t, primo=0)
        for g in t.giocatori:
            for o in list(g.mano): t.sposta(o, "grimorio", posizione="fondo", causa="prova")
        return E.Partita(t)
    # Last Gasp fa -3/-3: sceglie la creatura dell'avversario che muore, non quella piu' grande che non muore
    p = tavolo(["Last Gasp"] + ["Swamp"] * 39, ["Ghalta the Immovable", "Rank Rat"] + ["Forest"] * 38)
    gh, rr = PF._dai(p, 1, "Ghalta the Immovable"), PF._dai(p, 1, "Rank Rat")
    lg = F.tutte()["Last Gasp"].voce[2]
    scelta = Semplice().bersagli(p, 0, None, lg["bersagli"], [[gh, rr]], lg["fa"])
    caso("bersagli: Last Gasp va sulla creatura che uccide (Rank Rat 1/1), non sulla piu' grande che non muore (Ghalta 0/7)",
         scelta == [[rr]], f"{scelta}")
    scelta = Semplice().bersagli(p, 1, None, lg["bersagli"], [[gh, rr]], lg["fa"])
    caso("bersagli: con le sole creature proprie, una magia ostile rinuncia (proposta vuota, 734)", scelta == [[]], f"{scelta}")
    scelta = Semplice(rotto=True).bersagli(p, 1, None, lg["bersagli"], [[gh, rr]], lg["fa"])
    caso("prova negativa: il giocatore rotto mette Last Gasp sulla propria creatura", len(scelta[0]) == 1 and scelta[0][0].controllore == 1,
         f"{scelta}")
    inn = E.Abilita(999, gh, 0, {}, 1, "innescata")
    scelta = Semplice().bersagli(p, 1, inn, lg["bersagli"], [[gh, rr]], lg["fa"])
    caso("bersagli: un innesco ostile senza bersagli avversari sceglie comunque (603.3d), il meno prezioso", scelta == [[rr]], f"{scelta}")

    # il combattimento semplice: Tether Technician 4/5 contro Keeper of the Quiet Hour 3/2 e Rank Rat 1/1
    p = tavolo(["Tether Technician", "Keeper of the Quiet Hour"] + ["Mountain"] * 38, ["Keeper of the Quiet Hour", "Rank Rat", "Tether Technician"] + ["Swamp"] * 37)
    tt, kq = PF._dai(p, 0, "Tether Technician"), PF._dai(p, 0, "Keeper of the Quiet Hour")
    kq1, rr1 = PF._dai(p, 1, "Keeper of the Quiet Hour"), PF._dai(p, 1, "Rank Rat")
    for o in (tt, kq): o.controllo_dal = -1                                                      # in campo dall'inizio del turno (302.6)
    p.inizio_turno[0] = 0
    p.t.turno_numero, p.fase, p.passo = 3, "combattimento", "attaccanti"
    att = Semplice().attacca(p, 0) or {}
    caso("attacca: Tether 4/5 e Keeper 3/2 attaccano contro Keeper 3/2 e Rank Rat 1/1 (nessun bloccante uccide senza morire)",
         tt in att and kq in att, f"{[o.nome for o in att]}")
    tt1 = PF._dai(p, 1, "Tether Technician")
    att = Semplice().attacca(p, 0) or {}
    caso("attacca: con Tether 4/5 avversario stappato, Keeper 3/2 resta a casa (morirebbe senza uccidere), Tether va",
         kq not in att and tt in att, f"{[o.nome for o in att]}")
    p.t.sposta(tt1, "cimitero", causa="prova")
    p.attaccanti = {tt: 1}
    p.fase, p.passo = "combattimento", "bloccanti"
    bl = Semplice().blocca(p, 1) or {}
    caso("blocca: a 20 vite non blocca Tether 4/5 con chi muore senza ucciderlo", not bl, f"{[(b.nome, a.nome) for b, a in bl.items()]}")
    p.t.giocatori[1].vite = 3
    bl = Semplice().blocca(p, 1) or {}
    caso("blocca: a 3 vite si sacrifica col meno prezioso (Rank Rat) contro un danno letale", list(bl) == [rr1],
         f"{[(b.nome, a.nome) for b, a in bl.items()]}")
    p.t.giocatori[1].vite = 20
    p.attaccanti = {kq: 1}
    bl = Semplice().blocca(p, 1) or {}
    caso("blocca: Keeper 3/2 contro Keeper 3/2, lo scambio alla pari si fa", list(bl) == [kq1], f"{[(b.nome, a.nome) for b, a in bl.items()]}")
    p.attaccanti = {}
    caso("potrebbe_bloccare: chiede la regola al motore e lascia gli attaccanti com'erano",
         potrebbe_bloccare(p, kq1, tt) and not p.puo_bloccare(kq1, tt) and p.attaccanti == {})
    p.attaccanti = {}

    # le partite fra mazzi veri: finiscono, il motore non trova niente da ridire
    semi = list(range(1, 21))
    tempi, finite, durata, err, fini = [], 0, [], [], Counter()
    for s in semi:
        a, b = mazzi[s % 10], mazzi[(s * 3 + 1) % 10]
        t1 = time.time()
        p = partita(a, b, s, Semplice(s), Semplice(s + 100), ferma=False)
        tempi.append(time.time() - t1)
        err += [f"seme {s}: {e}" for e in p.err]
        finite += p.t.finita
        durata.append(p.t.turno_numero)
        fini[come_finisce(p)] += 1
    caso("20 partite Semplice contro Semplice con mazzi veri: tutte finite, vigilanza pulita", finite == 20 and not err,
         f"finite {finite}, turni {min(durata)}-{max(durata)}, errori {err[:2]}, {sum(tempi):.0f} s")
    caso("le partite partono da 20 vite e finiscono per le regole: chi perde e' a 0 o meno (704.5a), o senza carte da pescare (704.5b)",
         finite == 20 and sum(fini.values()) == 20 and set(fini) <= {"704.5a", "704.5b", "104.2b"}, f"{dict(fini)}")
    p1 = partita(mazzi[2], mazzi[5], 7, Semplice(), Semplice())
    p2 = partita(mazzi[2], mazzi[5], 7, Semplice(), Semplice())
    caso("stesso seme, stessi giocatori: stessa partita evento per evento",
         [(e.tipo, e.vecchio, e.nuovo, e.causa) for e in p1.t.eventi] == [(e.tipo, e.vecchio, e.nuovo, e.causa) for e in p2.t.eventi],
         f"{len(p1.t.eventi)} eventi")

    # il metro: Semplice batte chi sceglie a caso e il giocatore base del passo 7; il rotto no
    N = range(1, 61)
    fischi = []
    v, n, x, e_ = sfida(lambda s: Semplice(s), lambda s: E.CasoEffetti(s, illegali=0), N); fischi += e_
    lo, hi = wilson(v, n)
    caso("Semplice batte chi sceglie a caso (CasoEffetti senza mosse illegali)", lo > 0.5, f"{v}/{n} ({v / max(n, 1):.0%}, 95% {lo:.0%}-{hi:.0%}), non decise {x}")
    v, n, x, e_ = sfida(lambda s: Semplice(s), lambda s: E.GiocaEffetti(), N); fischi += e_
    lo, hi = wilson(v, n)
    caso("Semplice batte il giocatore base del passo 7 (GiocaEffetti)", lo > 0.5, f"{v}/{n} ({v / max(n, 1):.0%}, 95% {lo:.0%}-{hi:.0%}), non decise {x}")
    v, n, x, e_ = sfida(lambda s: Semplice(s, rotto=True), lambda s: Semplice(s), N); fischi += e_
    lo, hi = wilson(v, n)
    caso("prova negativa: il Semplice rotto (bersagli ribaltati) perde contro il Semplice", hi < 0.5,
         f"{v}/{n} ({v / max(n, 1):.0%}, 95% {lo:.0%}-{hi:.0%}), non decise {x}")

    caso("l'arbitro non ha fischiato in nessuna delle 180 partite del metro", not fischi, f"{fischi[:3]}")
    # 104.1, 104.2a, 704.3: chi perde nello stesso giro di azioni di stato in cui muore una sua pedina; la partita e' finita
    # subito, e la pedina finita nel cimitero non cessa in un secondo giro (704.5d)
    def ultimo_giro(T_):
        t = T_([F.mazzo(mazzi[0]["mazzo"]), F.mazzo(mazzi[1]["mazzo"])], seme=5, fuori=[[], []], basi_fuori=[])
        inizia(t, primo=0)
        pd = t.crea_pedina(1, "Pedina", "Creature", car={"forza": 1, "costituzione": 1})
        pd.danno, t.giocatori[1].vite = 1, 0
        t.azioni_di_stato()
        return t, [e.tipo + " " + str(e.causa) for e in t.eventi if e.causa and str(e.causa).startswith("704")]
    t, ev = ultimo_giro(E.TavoloEffetti)
    caso("104.1: perde e muore la sua pedina nello stesso giro (704.3), poi la partita e' finita: nessun secondo giro (704.5d)",
         t.finita and t.vincitore == 0 and "cessa 704.5d" not in ev and "perde 704.5a" in ev, f"{ev}")
    class DueGiri(E.TavoloEffetti):                 # il motore di prima: un altro giro di azioni di stato a partita persa
        def azioni_di_stato(self):
            fatte = super().azioni_di_stato()
            if self.finita:
                self.finita = False
                try: fatte += super().azioni_di_stato()
                finally: self.finita = True
            return fatte
    t, ev = ultimo_giro(DueGiri)
    caso("prova negativa: il motore che fa un altro giro dopo la sconfitta fa cessare la pedina (rosso per la 104.1)", "cessa 704.5d" in ev, f"{ev}")
    # 704.3, 704.5n: l'equipaggiamento che si stacca nello stesso giro della sconfitta (la creatura se n'era gia' andata) e' di
    # quel giro e l'arbitro lo accetta; quello la cui creatura muore proprio nel giro della sconfitta si staccherebbe al giro
    # dopo, che non c'e' (104.1). Il caso vero: seme 10 del metro del passo 8.2, Medic's Kitesail (14 ott 2026)
    def equip(T_, ospite_gia_via):
        t = T_([F.mazzo(["Medic's Kitesail", "Rank Rat"] + ["Swamp"] * 38), F.mazzo(mazzi[1]["mazzo"])], seme=5, fuori=[[], []], basi_fuori=[])
        inizia(t, primo=0)
        p = E.vigila(E.Partita)(t)
        ks, rr = PF._dai(p, 0, "Medic's Kitesail"), PF._dai(p, 0, "Rank Rat")
        t.attacca(ks, rr)
        if ospite_gia_via: t.sposta(rr, "grimorio", causa="prova")
        else: rr.danno = 5                                                                         # 704.5g nello stesso giro
        t.giocatori[0].vite = 0
        t.azioni_di_stato()
        controlli_finali(p)
        return p.err, [e.tipo + " " + str(e.causa) for e in t.eventi if str(e.causa).startswith("704")]
    err, ev = equip(E.TavoloEffetti, True)
    caso("704.3: la sconfitta e l'equipaggiamento che si stacca (la creatura era gia' andata) nello stesso giro; l'arbitro tace",
         "staccata 704.5n" in ev and "perde 704.5a" in ev and not err, f"{ev} {err}")
    err, ev = equip(E.TavoloEffetti, False)
    caso("104.1: la creatura muore nel giro della sconfitta, l'equipaggiamento non si stacca dopo (niente secondo giro)",
         "staccata 704.5n" not in ev and "zona 704.5g" in ev and not err, f"{ev} {err}")
    def finalita():                                 # 122.1h: la creatura con un segnalino finalita' muore nel giro della sconfitta
        t = E.TavoloEffetti([F.mazzo(["Rank Rat"] + ["Swamp"] * 39), F.mazzo(mazzi[1]["mazzo"])], seme=5, fuori=[[], []], basi_fuori=[])
        inizia(t, primo=0)
        p = E.vigila(E.Partita)(t)
        rr = PF._dai(p, 0, "Rank Rat")
        rr.segnalini["finalita"], rr.danno, t.giocatori[0].vite = 1, 5, 0
        t.azioni_di_stato()
        controlli_finali(p)
        return p.err, [f"{e.tipo} {e.causa} {e.a}" for e in t.eventi if e.tipo in ("perde", "zona") and e.causa != "prova"]
    err, ev = finalita()
    caso("704.3, 122.1h: la sconfitta e la creatura col segnalino finalita' che muore e va in esilio, nello stesso giro; l'arbitro tace",
         "perde 704.5a None" in ev and "zona 122.1h esilio" in ev and not err, f"{ev} {err}")
    err, ev = equip(DueGiri, False)
    caso("prova negativa: col motore che fa un secondo giro l'equipaggiamento si stacca dopo la sconfitta e l'arbitro fischia",
         "staccata 704.5n" in ev and any("104.1" in x for x in err), f"{ev} {err}")

    # l'arbitro fischia davvero: un motore rotto apposta deve fermare la simulazione, non dare un risultato
    class SenzaStato(E.Partita):                    # niente azioni di stato prima della priorita' (117.5, 704.3)
        def priorita(self): return []
    class MaiFine(E.TavoloEffetti):                  # gli effetti «fino a fine turno» non finiscono mai (514.2)
        def fine_turno(self): pass
    class Immortali(E.TavoloEffetti):                # a 0 vite non si perde: dimentica la sola 704.5a
        def azioni_di_stato(self):
            sotto = [(g, g.vite) for g in self.giocatori if g.vite <= 0 and not g.perso]
            for g, _ in sotto: g.vite = 1
            try: return super().azioni_di_stato()
            finally:
                for g, v in sotto: g.vite = v
    for nome, P_, T_ in (("niente azioni di stato (117.5)", SenzaStato, None), ("gli effetti di fine turno restano (514.2)", None, MaiFine),
                         ("a 0 vite non si perde (704.5a)", None, Immortali)):
        fischio = None
        for s_ in range(1, 11):
            try: partita(mazzi[s_ % 10], mazzi[(s_ * 3 + 1) % 10], s_, Semplice(s_), Semplice(s_ + 100), P=P_, T=T_)
            except ArbitroFischia as e: fischio = (s_, str(e)); break
        caso(f"prova negativa: col motore rotto apposta ({nome}) l'arbitro fischia e la simulazione si ferma",
             fischio is not None, f"{fischio[1][:140] if fischio else 'nessun fischio in 10 partite'}")
    ok = sum(1 for _, k, _ in casi if k)
    for nome, k, det in casi: print(("OK   " if k else "ROSSO"), nome, ("  -- " + det) if det else "")
    print(f"\n{ok}/{len(casi)} in {time.time() - t0:.0f} s")
    return ok == len(casi)


def racconta(a, b, seme):
    mazzi = mazzi_veri()
    p = partita(mazzi[a], mazzi[b], seme, Semplice(seme), Semplice(seme + 100), ferma=False)
    print(f"{mazzi[a]['nome']} ({mazzi[a]['partite'][0][:10]}) contro {mazzi[b]['nome']} ({mazzi[b]['partite'][0][:10]}), seme {seme}")
    vite = [20, 20]                                                                                # 119.1
    for e in p.t.eventi:
        g, nome = (e.giocatore or 0) + 1, (e.carta.nome if e.carta is not None else "")
        if e.tipo == "turno": print(f"--- turno, G{g}")
        elif e.tipo == "lanciata": print(f"  G{g} lancia {nome}")
        elif e.tipo == "attivata": print(f"  G{g} attiva {nome}")
        elif e.tipo == "attacca": print(f"  G{g} attacca con {nome}")
        elif e.tipo == "blocca": print(f"  G{g} blocca con {nome}")
        elif e.tipo == "vite":
            vite[g - 1] += e.quanto
            print(f"  G{g} {'perde' if e.quanto < 0 else 'guadagna'} {abs(e.quanto)} vite: ora {vite[g - 1]}")
        elif e.tipo in ("perde", "vince"): print(f"  G{g} {e.tipo} ({e.causa})")
        elif e.tipo == "zona" and e.da == "campo" and e.a == "cimitero": print(f"  {nome} va al cimitero")
        elif e.tipo == "zona" and e.da == "mano" and e.a == "campo" and e.carta is not None and "land" in e.carta.tipi: print(f"  G{g} gioca {nome}")
    print("vincitore:", None if p.t.vincitore is None else f"G{p.t.vincitore + 1}", "| vite", [g.vite for g in p.t.giocatori],
          "| turni", p.t.turno_numero, "| errori della vigilanza", len(p.err))


def torneo(n):
    mazzi = mazzi_veri()
    vinte = Counter(); giocate = Counter()
    for a in range(len(mazzi)):
        for b in range(len(mazzi)):
            if a == b: continue
            for s in range(n):
                p = partita(mazzi[a], mazzi[b], 1000 * a + 10 * b + s, Semplice(s), Semplice(s + 7))
                if p.t.vincitore is None: continue
                giocate[a] += 1; giocate[b] += 1
                vinte[a if p.t.vincitore == 0 else b] += 1
    for k in sorted(range(len(mazzi)), key=lambda k: -vinte[k] / max(giocate[k], 1)):
        lo, hi = wilson(vinte[k], giocate[k])
        print(f"{k:2} {mazzi[k]['nome']:3} {mazzi[k]['partite'][0][:16]}  {vinte[k]:3}/{giocate[k]:3} {vinte[k] / max(giocate[k], 1):.0%} ({lo:.0%}-{hi:.0%})"
              f"  vero: {len(mazzi[k]['partite'])} partite")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--prova"]: sys.exit(0 if prova() else 1)
    elif a[:1] == ["--mazzi"]:
        for m in scrivi_mazzi(): print(m["nome"], len(m["partite"]), m["partite"][0])
    elif a[:1] == ["--partita"]: racconta(int(a[1]), int(a[2]), int(a[3]))
    elif a[:1] == ["--torneo"]: torneo(int(a[1]) if len(a) > 1 else 2)
    else: print(__doc__)
