"""Le carte viste e la probabilita' di pescata del mazzo inviato."""
import re


class Pescate:
    """Le tue carte gia' viste nella partita in corso e quante ne restano nel grimorio, dal diario del companion (Autore,
    17 ott 2026: «elenco del mazzo con la % di pescata delle carte, le carte gia' viste o pescate vengono scritte in grigio
    scuro e hanno 0% accanto»). Le fonti: la mano iniziale (MANO), la mano a inizio turno (TURNO ... | mano:) e le righe
    STATO di segui_turno, che scrivono solo le sezioni cambiate: si tiene l'ultima versione di ogni sezione tua (mano, campo,
    cimitero) e una carta conta come vista il massimo di copie mai viste insieme. Il grimorio da «librerie: tu N».
    Si legge prima del filtro --solo-claude: le righe di stato non arrivano alla chat ma servono qui."""

    SEZ = (("LA TUA MANO", "mano"), ("IL TUO CAMPO", "campo"), ("Cimitero tuo", "cimitero"))

    def __init__(self):
        self.reset()

    def reset(self):
        self.viste = {}; self.sez = {}; self.lib = None; self.lib_sua = None; self.mano_sua = None
        self.avv = ""; self.vite = None; self.turno = None; self.in_partita = False

    @staticmethod
    def conta(testo, nomi):
        out = {}
        for n in sorted(nomi, key=len, reverse=True):     # i nomi lunghi prima: «Forest» non si conta dentro un altro nome
            k = testo.count(n)
            if k:
                out[n] = k; testo = testo.replace(n, " ")
        return out

    def riga(self, t, nomi):
        """Una riga del diario (senza ora). nomi: i nomi delle carte del mazzo. -> True se e' cambiato qualcosa."""
        if t.startswith("=== PARTITA:"):
            self.reset(); self.in_partita = True; return True
        if t.startswith("=== FINE PARTITA") or t.startswith("=== FINE DRAFT"):
            self.in_partita = False; return True
        # il companion che riparte, o la vigilanza senza partita nel log: nessuna partita in corso (17 ott 2026)
        if t.startswith("COMPANION ATTIVO") or "nessuna partita nel log" in t:
            self.in_partita = False; return True
        m = re.match(r"MANO \(\d+\) contro (.+?) \[.*?\]: (.*?) \| terre", t)
        if m:
            self.in_partita = True; self.avv = m.group(1); self.sez = {"mano": self.conta(m.group(2), nomi)}
            return self._aggiorna()
        m = re.match(r"TURNO (\d+) \| vite tu (\d+) lui (\d+).*?\| mano: (.*)$", t)
        if m:
            self.in_partita = True; self.turno = int(m.group(1)); self.vite = (int(m.group(2)), int(m.group(3)))
            self.sez["mano"] = self.conta(m.group(4), nomi)
            return self._aggiorna()
        if not t.startswith("STATO "):
            return False
        self.in_partita = True
        for rx, k in ((r"Partita contro (\S+)", "avv"), (r"turno Arena (\d+)", "turno")):
            q = re.search(rx, t)
            if q: setattr(self, k, int(q.group(1)) if k == "turno" else q.group(1))
        q = re.search(r"TU: vita (-?\d+) \| LUI: vita (-?\d+)", t)
        if q: self.vite = (int(q.group(1)), int(q.group(2)))
        q = re.search(r"librerie: tu (\d+), lui (\d+)", t)
        if q: self.lib, self.lib_sua = int(q.group(1)), int(q.group(2))
        q = re.search(r"Mano avversaria: (\d+)", t)
        if q: self.mano_sua = int(q.group(1))
        for pezzo in t.split("||"):
            for intestazione, k in self.SEZ:
                if pezzo.strip().startswith(intestazione):
                    corpo = pezzo.split("Mano avversaria")[0] if k == "mano" else pezzo
                    self.sez[k] = {} if corpo.strip().endswith("vuoto") else self.conta(corpo, nomi)
        return self._aggiorna()

    def _aggiorna(self):
        tot = {}
        for c in self.sez.values():
            for n, k in c.items():
                tot[n] = tot.get(n, 0) + k
        for n, k in tot.items():
            self.viste[n] = max(self.viste.get(n, 0), k)
        return True

    def elenco(self, mazzo):
        """mazzo: [(costo, quante, nome)]. -> [(costo, quante, nome, rimaste, % alla prossima pescata)], grimorio."""
        tot = sum(q for _, q, _ in mazzo)
        # le carte fuori dal grimorio sono almeno quelle viste: «librerie» puo' essere di qualche riga fa (una pescata dopo
        # l'ultima riga di stato con la mano), quindi vale il piu' piccolo dei due (12 ott, turno 10: 28 letto, 27 vero)
        fuori = max(tot - sum(min(self.viste.get(n, 0), q) for _, q, n in mazzo), 0)
        lib = fuori if self.lib is None else min(self.lib, fuori)
        out = []
        for c, q, n in mazzo:
            rim = max(q - self.viste.get(n, 0), 0)
            out.append((c, q, n, rim, 100.0 * rim / lib if lib else 0.0))
        return out, lib
