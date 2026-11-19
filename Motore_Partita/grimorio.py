"""Il grimorio e il mescolatore del motore di partita (Autore, 14 ott 2026: «costruiamolo noi per step, partiamo dal
miscelatore carte, crea un mescolatore carte attendibile»).

Primo pezzo del motore di partita nostro: Forge (Motore/forge_sim.py) ha 30 carte FRA su 285, e il motore di Arena non si
puo' usare. Questo modulo tiene il grimorio di un giocatore e fa, secondo il regolamento ufficiale (Regole/MagicCompRules.txt):
  - mescolare (103.3, 701.24a: «randomize the cards so that no player knows their order»): Fisher-Yates su un generatore
    PCG64 di numpy, con il seme scritto, cosi' ogni partita simulata si puo' rifare uguale;
  - pescare, una carta alla volta (121.1, 121.2); da un grimorio vuoto si perde (121.4, 704.5b): il grimorio lo segna;
  - la mano iniziale e il mulligan London (103.5): si rimescola la mano nel grimorio, si pescano 7 carte, se ne mettono in
    fondo tante quante i mulligan presi;
  - macinare (701.17a; 701.17b: se ne chiedono piu' di quante ce ne sono si macina cio' che c'e'), scry (701.22a),
    surveil (701.25a), cercare e rimescolare (701.23, 701.24b), mettere una carta N-esima dall'alto (401.7: con meno di N
    carte va in fondo), in cima o in fondo (401.4: l'ordine lo sceglie il proprietario).
Il grimorio non sa cosa fanno le carte: le tratta come nomi. Le decisioni (cosa tenere sopra col scry, cosa mettere in fondo
col mulligan) le passa chi lo usa, come funzioni.

    py -I -X utf8 Motore_Partita/grimorio.py --prova          le prove: regole e statistica del mescolatore
    py -I -X utf8 Motore_Partita/grimorio.py --prova --lunga  la statistica con 10 volte i campioni
"""
import secrets
import sys

import numpy as np


class GrimorioVuoto(Exception):
    pass


class Grimorio:
    """Le carte dall'alto (indice 0) al basso. Il seme e' quello del generatore: con lo stesso seme e le stesse operazioni
    il grimorio torna uguale (per rifare una partita simulata)."""

    def __init__(self, carte, seme=None, mescola=True):
        self.seme = int(seme) if seme is not None else secrets.randbits(64)
        self.rng = np.random.Generator(np.random.PCG64(self.seme))
        self.carte = list(carte)
        self.mescolate = 0
        self.perso = False          # 121.4: ha provato a pescare da vuoto (704.5b: perde alla prossima priorita')
        self.storia = []            # le operazioni, per rileggere una partita simulata
        if mescola: self.mescola()  # 103.3

    def __len__(self): return len(self.carte)

    # ------------------------------------------------------------------ mescolare
    def mescola(self):
        """Fisher-Yates (Durstenfeld): ogni ordine delle carte ha la stessa probabilita', 1/n!. 701.24e: anche con 0 o 1
        carte e' una mescolata (gli inneschi «quando si mescola» scattano lo stesso), quindi si conta."""
        c = self.carte
        for i in range(len(c) - 1, 0, -1):
            j = int(self.rng.integers(0, i + 1))
            c[i], c[j] = c[j], c[i]
        self.mescolate += 1
        self.storia.append(("mescola", len(c)))

    # ------------------------------------------------------------------ pescare
    def pesca(self, n=1):
        """n pescate, una alla volta (121.2). Da vuoto: si segna la sconfitta (121.4) e si smette di pescare."""
        out = []
        for _ in range(n):
            if not self.carte:
                self.perso = True
                self.storia.append(("pesca da vuoto",))
                break
            out.append(self.carte.pop(0))
        self.storia.append(("pesca", len(out)))
        return out

    def mano_iniziale(self, n=7, mulligan=None, max_mulligan=7):
        """La mano iniziale col mulligan London (103.5). mulligan(mano, quanti_fatti) -> True per rifarla; dopo k mulligan
        fondo(mano, k) -> le k carte da mettere in fondo (se manca, le ultime k). -> (mano, mulligan fatti)."""
        mano, k = self.pesca(n), 0
        while mulligan and k < max_mulligan and mulligan(mano, k):
            self.carte.extend(mano); self.mescola()
            k += 1
            mano = self.pesca(n)
        return mano, k

    def fondo_mulligan(self, mano, k, scegli=None):
        """Le k carte della mano che vanno in fondo dopo k mulligan (103.5), nell'ordine scelto. -> la mano che resta."""
        via = list(scegli(mano, k)) if scegli else mano[len(mano) - k:]
        resto = list(mano)
        for c in via: resto.remove(c)
        self.carte.extend(via)
        self.storia.append(("in fondo dal mulligan", len(via)))
        return resto

    # ------------------------------------------------------------------ guardare e spostare
    def cima(self, n):
        return self.carte[:n]

    def macina(self, n):
        """701.17a; 701.17b: con meno carte si macina cio' che c'e'. -> le carte macinate (vanno nel cimitero)."""
        via, self.carte = self.carte[:n], self.carte[n:]
        self.storia.append(("macina", len(via)))
        return via

    def scry(self, n, decidi):
        """701.22a. decidi(carte_guardate) -> (sopra, sotto), due liste nell'ordine scelto. 701.22b: scry 0 non e' un evento."""
        if n <= 0: return [], []
        guardate = self.carte[:n]
        sopra, sotto = decidi(list(guardate))
        assert sorted(sopra + sotto) == sorted(guardate), "scry: le carte devono essere quelle guardate"
        self.carte = list(sopra) + self.carte[n:] + list(sotto)
        self.storia.append(("scry", n, len(sotto)))
        return sopra, sotto

    def surveil(self, n, decidi):
        """701.25a. decidi(carte_guardate) -> (sopra, cimitero). -> le carte che vanno nel cimitero."""
        if n <= 0: return []
        guardate = self.carte[:n]
        sopra, via = decidi(list(guardate))
        assert sorted(sopra + via) == sorted(guardate), "surveil: le carte devono essere quelle guardate"
        self.carte = list(sopra) + self.carte[n:]
        self.storia.append(("surveil", n, len(via)))
        return list(via)

    def cerca(self, predicato, quante=1, mescola=True):
        """701.23: cerca fino a «quante» carte che rispettano il predicato (701.23b: in una zona nascosta si puo' non
        trovarle), poi rimescola (701.24b). -> le carte trovate."""
        trovate = []
        for c in list(self.carte):
            if len(trovate) >= quante: break
            if predicato(c): trovate.append(c); self.carte.remove(c)
        self.storia.append(("cerca", len(trovate)))
        if mescola: self.mescola()
        return trovate

    def metti(self, carta, posizione="cima"):
        """«cima», «fondo» o un intero N (N-esima dall'alto, 1 = cima). 401.7: con meno di N carte va in fondo."""
        if posizione == "cima": self.carte.insert(0, carta)
        elif posizione == "fondo": self.carte.append(carta)
        else:
            n = int(posizione)
            if n > len(self.carte): self.carte.append(carta)
            else: self.carte.insert(n - 1, carta)
        self.storia.append(("metti", posizione))

    def mescola_dentro(self, carte):
        """Mescolare delle carte nel grimorio (701.24c-d: si mescola anche se non ce n'e' nessuna)."""
        self.carte.extend(carte); self.mescola()


# ====================================================================== le prove
def _chi2_p(osservati, attesi, gradi):
    from scipy.stats import chi2
    stat = float(((osservati - attesi) ** 2 / attesi).sum())
    return stat, float(chi2.sf(stat, gradi))


def prova(lunga=False):
    from math import comb
    casi = []
    def caso(nome, ok, dettaglio=""):
        casi.append((nome, bool(ok), dettaglio))

    N = 200_000 if lunga else 20_000
    n = 40

    def misura(mescolatore, N):
        """-> (p del chi quadro sulle posizioni, coppie vicine rimaste in media, il loro scarto in errori standard)."""
        conta, vicine = np.zeros((n, n)), 0
        for _ in range(N):
            c = mescolatore(list(range(n)))
            conta[c, np.arange(n)] += 1
            pos = np.empty(n, int); pos[c] = np.arange(n)
            vicine += int(np.sum(pos[1:] == pos[:-1] + 1))
        _, p = _chi2_p(conta, N / n, (n - 1) ** 2)
        # la carta k+1 subito dopo la k ha probabilita' 1/n: 39/40 coppie a mescolata, e il conteggio e' circa Poisson
        # (varianza vicina alla media): l'errore standard della media e' sqrt(39/40 / N)
        atteso = (n - 1) / n
        return p, vicine / N, (vicine / N - atteso) / (atteso / N) ** 0.5

    g = Grimorio([], seme=1, mescola=False)
    def buono(c):
        g.carte = c; g.mescola(); return g.carte
    p, media, z = misura(buono, N)
    # 1. uniformita' delle posizioni: per ogni carta, ogni posizione con probabilita' 1/40 (chi quadro su 40x40 celle)
    caso("posizioni uniformi (chi quadro su 1600 celle)", p > 0.001, f"p = {p:.3f}")
    # 2. le carte vicine prima non restano vicine (un mescolamento a mano, poche passate, ne lascia di piu')
    caso("le vicine non restano vicine (39/40 coppie a mescolata)", abs(z) < 3, f"{media:.4f} contro {(n - 1) / n:.4f}, {z:+.1f} errori standard")
    # 2.bis la prova negativa: una sola mescolata a ventaglio (il modello di Gilbert-Shannon-Reeds, come a mano) non e'
    #      casuale; se le prove non la vedono rossa, non distinguono niente
    rng = np.random.default_rng(5)
    def ventaglio(c):
        k = int(rng.binomial(len(c), 0.5)); a, b, out = c[:k], c[k:], []
        while a or b:
            if rng.random() < len(a) / (len(a) + len(b)): out.append(a.pop(0))
            else: out.append(b.pop(0))
        return out
    pv, mv, zv = misura(ventaglio, min(N, 20_000))
    caso("prova negativa: una mescolata a ventaglio risulta rossa", pv < 0.001 and abs(zv) > 3,
         f"p = {pv:.2g}, vicine {mv:.2f} ({zv:+.0f} errori standard)")
    # 3. le probabilita' esatte del mazzo di Limited: 17 terre su 40, quante nella mano di 7 (ipergeometrica)
    mazzo = ["terra"] * 17 + ["magia"] * 23
    g = Grimorio(mazzo, seme=2, mescola=False)
    terre = np.zeros(8)
    for _ in range(N):
        g.carte = list(mazzo); g.mescola()
        terre[sum(1 for c in g.carte[:7] if c == "terra")] += 1
    esatte = np.array([comb(17, k) * comb(23, 7 - k) / comb(40, 7) for k in range(8)])
    unite = [(terre[:2].sum(), esatte[:2].sum())] + [(terre[k], esatte[k]) for k in range(2, 6)] + [(terre[6:].sum(), esatte[6:].sum())]
    oss = np.array([u[0] for u in unite]); att = np.array([u[1] for u in unite]) * N
    stat, p = _chi2_p(oss, att, len(unite) - 1)
    caso("terre nella mano di 7 come l'ipergeometrica", p > 0.001,
         "  ".join(f"{k}:{terre[k] / N:.3f}/{esatte[k]:.3f}" for k in range(1, 6)) + f"  p = {p:.3f}")
    # 4. il caso di ieri sera: 9 Forest su 40, nessuna nelle prime 17 carte (esatta 0,30%)
    forest = ["Forest"] * 9 + ["altro"] * 31
    g = Grimorio(forest, seme=3, mescola=False)
    zero = 0
    for _ in range(N):
        g.carte = list(forest); g.mescola()
        zero += "Forest" not in g.carte[:17]
    es_ = comb(31, 17) / comb(40, 17)
    caso("nessuna Forest in 17 carte: come l'esatta 0,30%", abs(zero / N - es_) < 4 * (es_ * (1 - es_) / N) ** 0.5,
         f"{100 * zero / N:.2f}% contro {100 * es_:.2f}%")
    # 5. il seme: stesso seme stesso ordine, semi diversi ordini diversi
    a, b, c = Grimorio(range(40), seme=42), Grimorio(range(40), seme=42), Grimorio(range(40), seme=43)
    caso("stesso seme, stesso ordine (la partita si rifa' uguale)", a.carte == b.carte)
    caso("semi diversi, ordini diversi", a.carte != c.carte)
    caso("senza seme ne nasce uno, scritto", Grimorio(range(5)).seme > 0)
    # 6. nessuna carta persa o inventata dopo una sequenza di tutte le operazioni
    g = Grimorio([f"c{i}" for i in range(40)], seme=7)
    fuori = []
    mano, k = g.mano_iniziale(7, mulligan=lambda m, k: k < 2)
    mano = g.fondo_mulligan(mano, k)
    fuori += mano + g.pesca(3) + g.macina(4)
    g.scry(2, lambda v: ([v[0]], [v[1]]))
    fuori += g.surveil(2, lambda v: ([v[1]], [v[0]]))
    fuori += g.cerca(lambda x: x.endswith("7"), 2)
    caso("mulligan London: 2 mulligan, 5 carte in mano", k == 2 and len(mano) == 5)
    caso("nessuna carta persa ne' inventata", sorted(fuori + g.carte) == sorted(f"c{i}" for i in range(40)), f"{len(fuori)} fuori + {len(g)} nel grimorio")
    # 7. le regole
    g = Grimorio(["a", "b"], seme=1, mescola=False)
    g.pesca(3)
    caso("pescare da un grimorio vuoto: sconfitta segnata (121.4, 704.5b)", g.perso and len(g) == 0)
    g = Grimorio(["a", "b", "c"], seme=1, mescola=False)
    caso("macinarne 5 con 3 carte: si macinano le 3 (701.17b)", len(g.macina(5)) == 3 and len(g) == 0)
    g = Grimorio(["a", "b"], seme=1, mescola=False); g.metti("x", 5)
    caso("N-esima dall'alto con meno di N carte: va in fondo (401.7)", g.carte == ["a", "b", "x"])
    g = Grimorio(["a", "b", "c", "d"], seme=1, mescola=False); g.metti("x", 2)
    caso("seconda dall'alto", g.carte == ["a", "x", "b", "c", "d"])
    g = Grimorio(["a", "b", "c", "d"], seme=1, mescola=False)
    g.scry(2, lambda v: ([], [v[1], v[0]]))
    caso("scry 2, tutte e due sotto nell'ordine scelto (701.22a)", g.carte == ["c", "d", "b", "a"])
    g = Grimorio(["a", "b", "c"], seme=1, mescola=False)
    caso("surveil 1 nel cimitero (701.25a)", g.surveil(1, lambda v: ([], v)) == ["a"] and g.carte == ["b", "c"])
    g = Grimorio(["a"], seme=1, mescola=False); m0 = g.mescolate; g.mescola_dentro([])
    caso("mescolare anche con 0 carte da aggiungere conta come mescolata (701.24d-e)", g.mescolate == m0 + 1)
    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)} ({N} mescolate per prova statistica)")
    return 0 if all(ok for _, ok, _ in casi) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova("--lunga" in sys.argv))
    print(__doc__)
