"""Export di un mazzo: la lista per Arena e per MTGO."""
import re

import prezzi_carte as PZ

from tema import CI as C
from widget import ARANCIO, pulsante_solido


def lista_arena(main, side=None, comandante=None, compagno=None):
    """La lista nel formato che Arena importa (Importa nel menu dei mazzi): «Commander» o «Companion» se ci sono, poi
    «Deck», una riga per carta, poi «Sideboard»."""
    righe = []
    for titolo, zona in (("Commander", comandante), ("Companion", compagno)):
        if zona:
            righe += [titolo] + [f"{q} {n}" for n, q in zona.items()] + [""]
    righe += ["Deck"] + [f"{q} {n}" for n, q in main.items()]
    if side:
        righe += ["", "Sideboard"] + [f"{q} {n}" for n, q in side.items()]
    return "\n".join(righe)


def nome_mtgo(n):
    """Il nome per MTGO: le carte a due facce col nome della faccia davanti, le split (e le Room) intere «A // B». Grado C: non provato su MTGO."""
    if " // " in n:
        pz = PZ.prezzo(n)
        if not pz or pz.get("layout") != "split":
            return n.split(" // ")[0]
    return n


def lista_mtgo(main, side=None, comandante=None, compagno=None):
    """La lista per Magic Online (e per i siti che leggono il testo: Moxfield, MTGGoldfish, Archidekt): «4 Nome», una riga vuota,
    poi la sideboard. MTGO non ha zone per comandante e compagno: vanno in sideboard."""
    righe = [f"{q} {nome_mtgo(n)}" for n, q in main.items()]
    sb = {}
    for z in (comandante, compagno, side):
        for n, q in (z or {}).items():
            sb[n] = sb.get(n, 0) + q
    if sb:
        righe += [""] + [f"{q} {nome_mtgo(n)}" for n, q in sb.items()]
    return "\n".join(righe) + "\n"


PRINCIPALI = ("Edit", "Add to wishlist")


class EsportaMazzo:
    """Export: la lista per Arena e per MTGO, negli appunti o in un file."""

    def esportazione(self, padre, nome, main, side, comandante, compagno, azioni=()):
        """Le uscite della lista: copiarla per Arena o per MTGO, o salvarla in un file. Arena importa dal testo copiato (Decks › Import),
        MTGO da un file (Import Deck nella collezione): il .txt di MTGO va bene anche per Moxfield, MTGGoldfish, Archidekt."""
        tk, F = self.tk, self.F
        self._problemi = getattr(self, "_problemi", [])
        # Edit e Add to wishlist in testa a tutti i pulsanti, in arancio (Autore, 10 nov 2026: «nei menu deck wishlist e edit devono essere in testa agli altri
        # pulsanti e di colore diverso dagli altri»); le altre azioni restano sotto l'esportazione
        prime = [a_ for a_ in azioni if a_[0] in PRINCIPALI]
        azioni = [a_ for a_ in azioni if a_[0] not in PRINCIPALI]
        if prime:
            self.riga_azioni(padre, prime, colori=ARANCIO, sotto=8)
        self.etichetta(padre, "export", C["scheda"]).pack(anchor="w", pady=(0, 3))
        g = tk.Frame(padre, bg=C["scheda"]); g.pack(fill="x")
        for j in range(2):
            g.columnconfigure(j, weight=1, uniform="esp")
        testi = dict(arena=lista_arena(main, side, comandante, compagno), mtgo=lista_mtgo(main, side, comandante, compagno))
        file_ = re.sub(r'[\\/:*?"<>|]+', " ", nome or "Deck").strip() or "Deck"

        def avvisa(b, testo, dopo):
            b.metti(testo, False); b.after(2500, lambda: b.winfo_exists() and b.metti(dopo, False))

        def copia(b, chi, dopo):
            b.clipboard_clear(); b.clipboard_append(testi[chi]); b.update()
            avvisa(b, "Copied: Arena › Decks › Import" if chi == "arena" else "Copied", dopo)

        def salva(b, chi, dopo):
            from tkinter import filedialog
            f = filedialog.asksaveasfilename(parent=b.winfo_toplevel(), title="Save the deck list", defaultextension=".txt",
                                             initialfile=f"{file_}{' (MTGO)' if chi == 'mtgo' else ''}.txt", filetypes=[("Text", "*.txt")])
            if f:
                with open(f, "w", encoding="utf-8", newline="\r\n") as h:
                    h.write(testi[chi])
                avvisa(b, "Saved", dopo)
        voci = (("Copy for Arena", copia, "arena"), ("Copy for MTGO / text", copia, "mtgo"),
                ("Save file for Arena", salva, "arena"), ("Save file for MTGO", salva, "mtgo"))
        for i, (t, f_, chi) in enumerate(voci):
            casa = {}
            b = casa["b"] = pulsante_solido(tk, F, g, t, False, lambda casa=casa, f_=f_, chi=chi, t=t: f_(casa["b"], chi, t), alto=28, bg=C["scheda"])
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 6 if i % 2 == 0 else 0), pady=(0, 6))
        if azioni:      # le altre azioni del mazzo, sotto l'esportazione
            self.riga_azioni(padre, azioni)

    def riga_azioni(self, padre, azioni, colori=None, sotto=0):
        """Una riga di pulsanti d'azione, larghi uguali. due_clic: vuole un secondo clic per confermare."""
        tk, F = self.tk, self.F
        a = tk.Frame(padre, bg=C["scheda"]); a.pack(fill="x", pady=(0, sotto))
        a.azioni = [t_ for t_, _f, _d in azioni]       # per le prove
        for j in range(len(azioni)):
            a.columnconfigure(j, weight=1, uniform="az")
        for j, (t, f_, due_clic) in enumerate(azioni):
            casa = {"armato": False}

            def premi(casa=casa, f_=f_, t=t, due_clic=due_clic):
                b = casa["b"]
                if due_clic and not casa["armato"]:       # togliere vuole un secondo clic
                    casa["armato"] = True; b.metti("Click again to confirm", True)
                    b.after(2500, lambda: b.winfo_exists() and (casa.update(armato=False), b.metti(t, False)))
                    return
                esito = f_()
                if esito and b.winfo_exists():
                    b.metti(esito, False); b.after(2500, lambda: b.winfo_exists() and b.metti(t, False))
            casa["b"] = pulsante_solido(tk, F, a, t, False, premi, alto=28, bg=C["scheda"], colori=colori)
            casa["b"].grid(row=0, column=j, sticky="ew", padx=(0, 6 if j < len(azioni) - 1 else 0))
