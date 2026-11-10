"""Economia del Quick Draft: quanto rende un draft per ogni win rate, il pareggio, e dove siamo noi.

Domanda di Autore, 8 ott 2026 23:35: obiettivo «raccogliere rare e vincere quante piu' gemme
possibile per provare a giocare all'infinito pagando in gemme».

Tabella premi (gemme e buste per vittorie, 7 vittorie o 3 sconfitte, partite al meglio di una,
ingresso 750 gemme o 5.000 oro): letta da una pagina wiki non datata e confermata sul massimo
(950 gemme + 2 buste) da Draftsim, mar 2025, e da un calendario 2026. Grado B: va ricontrollata nel
client, nella schermata dell'evento, prima di fidarsi dei decimali. Le buste intermedie (1,2-1,4)
sono il valore atteso della busta in piu' a sorpresa.

Il nostro record viene da Untapped (tutte le partite di Quick Draft, ogni set). I draft si
ricostruiscono dai contatori di vittorie e sconfitte dell'evento prima di ogni partita.

Uso: python -I Motore/economia_draft.py   -> Note/Economia_Quick_Draft.md
"""
import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Companion")); import percorsi  # la casa del Companion: i percorsi stanno in Companion/percorsi.py (13 ott 2026)
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Note" / "Economia_Quick_Draft.md"

INGRESSO = 750
GEMME = {0: 50, 1: 100, 2: 200, 3: 300, 4: 450, 5: 650, 6: 850, 7: 950}
BUSTE = {0: 1.2, 1: 1.22, 2: 1.24, 3: 1.26, 4: 1.3, 5: 1.35, 6: 1.4, 7: 2.0}
# Premier Draft, per confronto (Draftsim, guida aggiornata giu 2026; stesse gemme dello State of the Game apr 2020). Grado B.
P_INGRESSO = 1500
P_GEMME = {0: 50, 1: 100, 2: 250, 3: 1000, 4: 1400, 5: 1600, 6: 1800, 7: 2200}
P_BUSTE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}


def distribuzione(p):
    """Probabilita' di chiudere con w vittorie (0-7), a win rate di partita p."""
    q = 1 - p
    d = {w: math.comb(w + 2, w) * p ** w * q ** 3 for w in range(7)}
    d[7] = sum(math.comb(6 + l, l) * p ** 7 * q ** l for l in range(3))
    return d


def resa(p, gemme=GEMME, buste=BUSTE):
    d = distribuzione(p)
    return sum(d[w] * gemme[w] for w in d), sum(d[w] * buste[w] for w in d), sum(d[w] * w for w in d), d


def pareggio(gemme=GEMME, ingresso=INGRESSO):
    lo, hi = 0.3, 0.95
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if resa(m, gemme)[0] < ingresso else (lo, m)
    return lo


def wilson(v, n, z=1.96):
    if not n:
        return (0, 0)
    p = v / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def nostre_partite():
    from partite_untapped import partite
    P = [g for g in partite(8) if "QuickDraft" in (g.get("event_name") or "")]
    out = []
    for g in P:
        vinta = g.get("winning_team_id") == g.get("friendly_team_id")
        out.append({"evento": g["event_name"], "t": g.get("match_start"), "vinta": vinta,
                    "mazzo": g.get("friendly_deck_id") or g.get("friendly_deck_name"),
                    # nonostante il nome «before», Untapped li da' DOPO la partita (verificato 8 ott 2026)
                    "w": g.get("friendly_course_wins_before") or 0, "l": g.get("friendly_course_losses_before") or 0})
    return out


def draft(partite):
    """Ricostruisce i draft: uno per mazzo (ogni draft ha il suo mazzo). L'esito e' il contatore piu' alto."""
    runs = {}
    for g in partite:
        r = runs.setdefault((g["evento"], g["mazzo"]), {"evento": g["evento"], "v": 0, "s": 0, "partite": 0})
        r["v"] = max(r["v"], g["w"]); r["s"] = max(r["s"], g["l"]); r["partite"] += 1
    return list(runs.values())


def main():
    righe = []
    w = righe.append
    w("---\ncreato: 2026-10-08T23:45\nfonte: tabella premi (wiki + Draftsim, grado B), partite da Untapped\n---\n")
    w("# Economia del Quick Draft\n")
    w(f"Ingresso {INGRESSO} gemme (o 5.000 oro). Si gioca fino a 7 vittorie o 3 sconfitte, al meglio di una.\n")
    w("## 1. Quanto rende un draft, per win rate di partita\n")
    w("| Win rate | Vittorie medie | Gemme medie | Saldo gemme per draft | Buste medie | Draft a 7 vittorie |")
    w("| --: | --: | --: | --: | --: | --: |")
    for p in [0.40, 0.45, 0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75]:
        g, b, v, d = resa(p)
        w(f"| {p*100:.0f}% | {v:.2f} | {g:.0f} | {g-INGRESSO:+.0f} | {b:.2f} | {d[7]*100:.1f}% |")
    pz = pareggio()
    w(f"\n**Pareggio in gemme: {pz*100:.1f}% di partite vinte.** Sotto quel numero ogni draft costa gemme; sopra, se ne guadagnano. "
      "Le buste e le carte prese restano in piu' (sono il valore delle rare), ma non pagano il draft dopo.\n")

    P = nostre_partite()
    w("## 2. Dove siamo noi (Untapped, tutte le partite di Quick Draft)\n")
    per_ev = defaultdict(list)
    for g in P:
        per_ev[g["evento"]].append(g)
    w("| Evento | Partite | Vinte | Win rate | Intervallo al 95% |")
    w("| :-- | --: | --: | --: | :-- |")
    for ev, gs in sorted(per_ev.items()):
        v = sum(x["vinta"] for x in gs); lo, hi = wilson(v, len(gs))
        w(f"| {ev} | {len(gs)} | {v} | {v/len(gs)*100:.0f}% | {lo*100:.0f}-{hi*100:.0f}% |")
    v = sum(x["vinta"] for x in P); n = len(P); lo, hi = wilson(v, n)
    w(f"| **totale** | **{n}** | **{v}** | **{v/n*100:.0f}%** | {lo*100:.0f}-{hi*100:.0f}% |")
    R = draft(P)
    finiti = [r for r in R if r["v"] == 7 or r["s"] == 3]
    gem = sum(GEMME[r["v"]] for r in finiti)
    w(f"\n**Draft ricostruiti:** {len(R)} ({len(finiti)} finiti). Esiti dei finiti: " +
      ", ".join(f"{k} vittorie x{sum(1 for r in finiti if r['v']==k)}" for k in range(8) if any(r["v"] == k for r in finiti)) + ".")
    if finiti:
        w(f"Gemme vinte nei draft finiti: **{gem}** contro **{len(finiti)*INGRESSO}** di ingressi (saldo {gem-len(finiti)*INGRESSO:+}, "
          f"{(gem/len(finiti)):.0f} gemme a draft). Se l'ingresso e' stato pagato in oro, il saldo in gemme e' tutto guadagno.\n")
    pm = v / n if n else 0
    g_m, b_m, v_m, _ = resa(pm)
    w(f"Al nostro win rate di oggi ({pm*100:.0f}%) un draft rende in media **{g_m:.0f} gemme** ({g_m-INGRESSO:+.0f}) e {b_m:.2f} buste. "
      f"Per arrivare al pareggio servono **{(pz-pm)*100:+.1f} punti** di win rate.\n")
    pp = pareggio(P_GEMME, P_INGRESSO)
    w("## 3. Confronto col Premier Draft (ingresso 1.500 gemme)\n")
    w("| Win rate | Quick: saldo gemme | Quick: buste | Premier: saldo gemme | Premier: buste |")
    w("| --: | --: | --: | --: | --: |")
    for p in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
        g, b, _, _ = resa(p); g2, b2, _, _ = resa(p, P_GEMME, P_BUSTE)
        w(f"| {p*100:.0f}% | {g-INGRESSO:+.0f} | {b:.2f} | {g2-P_INGRESSO:+.0f} | {b2:.2f} |")
    w(f"\n**Pareggio Premier: {pp*100:.1f}%** contro {pz*100:.1f}% del Quick. Il Premier costa il doppio ma premia molto di piu' le 3+ vittorie: "
      "ma anche li' il pareggio e' alto. Contro-caso: in Premier gli avversari draftano fra persone e sono in media piu' forti, "
      "quindi il nostro win rate li' sarebbe piu' basso di quello del Quick. E la regola di Autore oggi e' «sempre Quick Draft».\n")
    w("## 4. Quante partite servono per sapere se siamo sopra il pareggio\n")
    w("Con n partite, il margine d'errore al 95% sul win rate e' circa:\n")
    w("| Partite | Margine |")
    w("| --: | --: |")
    for k in (30, 60, 100, 200, 400):
        w(f"| {k} | +/- {1.96*math.sqrt(0.25/k)*100:.0f} punti |")
    w("\n## Limiti\n- Tabella premi di grado B: da controllare nella schermata dell'evento.\n"
      "- Il win rate del set precedente (HOB) non e' quello di FRA: set diverso, mazzi diversi.\n"
      "- I draft ricostruiti da Untapped possono sbagliare se manca una partita dal suo archivio.\n")
    OUT.write_text("\n".join(righe), encoding="utf-8")
    print(f"scritto {OUT} | pareggio {pz*100:.1f}% | partite {n} vinte {v} | draft {len(R)}")


if __name__ == "__main__":
    main()
