"""Archivio permanente delle partite: una scheda JSON per partita in Partite/.

Regola di Autore, 8 ott 2026 23:10: «voglio che teniamo sempre tutte le partite e continuiamo
a costruire analisi anche sulle carte giocate e come sono giocate dagli altri giocatori».

Legge il Player.log attuale, il Player-prev.log e tutti i log archiviati in Log_Arena/ (fuori da
git, pesanti), separa le partite per matchId e salva di ognuna, in piccolo e in git:
- chi, quando, evento, esito, il tuo mazzo visto;
- la cronologia: ogni magia lanciata e ogni abilita' con bersaglio (di entrambi), le terre giocate,
  gli attacchi col bersaglio, i blocchi, le creature morte, le vite, con turno, fase e mana libero
  di chi agisce.
Una partita gia' archiviata si riscrive solo se la nuova lettura ha piu' eventi (log piu' completo).
Ogni file di log si legge per conto suo; se la stessa partita sta in piu' file, per ogni turno si tiene
la lettura piu' completa (fino al 9 ott 2026 gli eventi si accodavano e le partite uscivano doppie).

Uso: python -I Companion/Strumenti/archivio_partite.py          (tutte le fonti)
     python -I Companion/Strumenti/archivio_partite.py --solo-attuale
     python -I Companion/Strumenti/archivio_partite.py --ripara   (toglie i doppioni dalle schede gia' archiviate)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import datetime
import glob
import json
import re
from pathlib import Path

import tavolo  # noqa: E402

ROOT = Path(percorsi.ROOT)
DEST = ROOT / "Partite"
DEST.mkdir(exist_ok=True)
SRC = Path(piattaforma.cartella_arena())
TS = re.compile(r'"timestamp": "(\d{13})"')


def tipo_zona(st, zid):
    return (st["zone"].get(zid) or {}).get("type", "")


def terre_libere(st, seat):
    n = 0
    for z in st["zone"].values():
        if z.get("type") != "ZoneType_Battlefield":
            continue
        for iid in z.get("objectInstanceIds", []):
            o = st["obj"].get(iid)
            if o and o.get("controllerSeatId") == seat and "CardType_Land" in o.get("cardTypes", []) and not o.get("isTapped"):
                n += 1
    return n


class Registro:
    def __init__(self):
        self.partite = {}   # mid -> scheda
        self.prima = {}     # mid -> {iid: (zona, attackState, blockState)}
        self.ts = None
        self.grp = {}       # iid -> grpId, per riconoscere chi lascia il campo

    def chi(self, st, seat):
        return "io" if seat == st["me"] else "lui"

    def scheda(self, st):
        mid = st["mid"]
        if mid not in self.partite:
            self.partite[mid] = {"matchId": mid, "inizio": self.ts, "evento": st.get("evento"), "avversario": st.get("avv"),
                                 "esito": None, "motivo": None, "turni": 0, "vite_finali": {}, "mio_mazzo_visto": [],
                                 "sue_carte_viste": [], "eventi": []}
            self.prima[mid] = {}
        return self.partite[mid]

    def on_msg(self, st):
        if not st or not st.get("me"):
            return
        s = self.scheda(st)
        s["avversario"] = st.get("avv") or s["avversario"]
        s["evento"] = st.get("evento") or s["evento"]
        tu = st["turno"]
        turno = tu.get("turnNumber", 0)
        ph = (tu.get("phase") or "").replace("Phase_", "")
        fase = ph if ph in ("Main1", "Main2", "Beginning", "Ending") or not tu.get("step") else tu["step"].replace("Step_", "")
        s["turni"] = max(s["turni"], turno or 0)
        prima = self.prima[st["mid"]]
        ora = {}
        for z in st["zone"].values():
            for iid in z.get("objectInstanceIds", []):
                o = st["obj"].get(iid)
                if o:
                    ora[iid] = (z.get("type"), o.get("attackState"), o.get("blockState"))
        tavolo.ST = st
        # chi e' uscito dal campo in questo messaggio: serve a distinguere «muore» da «finisce al cimitero» (surveil, scarto)
        usciti = {st["obj"].get(i, {}).get("grpId") for i, v in prima.items() if v[0] == "ZoneType_Battlefield" and ora.get(i, ("",))[0] != "ZoneType_Battlefield"}
        usciti |= {self.grp.get(i) for i, v in prima.items() if v[0] == "ZoneType_Battlefield" and i not in ora}
        for iid, (zona, att, blo) in ora.items():
            o = st["obj"][iid]
            p = prima.get(iid)
            base = {"t": turno, "fase": fase, "chi": self.chi(st, o.get("controllerSeatId") or o.get("ownerSeatId"))}
            nm = tavolo.nome(o.get("grpId"))
            if o.get("ownerSeatId") == st["me"] and o.get("type") != "GameObjectType_Ability" and zona != "ZoneType_Library":
                if nm not in s["mio_mazzo_visto"] and not nm.startswith("grp"):
                    s["mio_mazzo_visto"].append(nm)
            if o.get("ownerSeatId") not in (None, st["me"]) and o.get("type") == "GameObjectType_Card" and zona not in ("ZoneType_Library", "ZoneType_Hand"):
                if nm not in s["sue_carte_viste"] and not nm.startswith("grp"):
                    s["sue_carte_viste"].append(nm)
            if p is None:
                if zona == "ZoneType_Stack":
                    if o.get("type") == "GameObjectType_Ability":
                        ev = dict(base, tipo="abilita", carta=tavolo.nome(o.get("objectSourceGrpId")))
                    else:
                        ev = dict(base, tipo="lancia", carta=nm,
                                  tipi=[x.replace("CardType_", "") for x in o.get("cardTypes", [])])
                    ev["mana_libero_dopo"] = terre_libere(st, o.get("controllerSeatId"))
                    s["eventi"].append(ev)
                elif zona == "ZoneType_Battlefield" and "CardType_Land" in o.get("cardTypes", []):
                    s["eventi"].append(dict(base, tipo="terra", carta=nm))
                elif zona == "ZoneType_Battlefield" and o.get("type") == "GameObjectType_Token":
                    s["eventi"].append(dict(base, tipo="pedina", carta=nm))
                elif zona == "ZoneType_Graveyard" and "CardType_Creature" in o.get("cardTypes", []) and o.get("grpId") in usciti:
                    s["eventi"].append(dict(base, tipo="muore", carta=nm, chi=self.chi(st, o.get("ownerSeatId"))))
            else:
                if att == "AttackState_Attacking" and p[1] != "AttackState_Attacking":
                    tid = (o.get("attackInfo") or {}).get("targetId")
                    dove = "io" if tid == st["me"] else ("lui" if tid in (1, 2) else tavolo.nome_oggetto(tid))
                    s["eventi"].append(dict(base, tipo="attacca", carta=nm, pt=f"{o.get('power',{}).get('value')}/{o.get('toughness',{}).get('value')}", bersaglio=dove))
                if blo == "BlockState_Blocking" and p[2] != "BlockState_Blocking":
                    bl = [tavolo.nome_oggetto(a) for a in (o.get("blockInfo") or {}).get("attackerIds", [])]
                    s["eventi"].append(dict(base, tipo="blocca", carta=nm, pt=f"{o.get('power',{}).get('value')}/{o.get('toughness',{}).get('value')}", blocca=bl))
        # bersagli delle magie e abilita' in pila
        for aff, bers in (st.get("mire") or {}).items():
            for ev in reversed(s["eventi"][-12:]):
                o = st["obj"].get(aff)
                if not o or "bersagli" in ev:
                    continue
                abil = o.get("type") == "GameObjectType_Ability"
                if (abil and ev["tipo"] == "abilita" and tavolo.nome(o.get("objectSourceGrpId")) == ev["carta"]) or                    (not abil and ev["tipo"] == "lancia" and tavolo.nome(o.get("grpId")) == ev["carta"]):
                    if True:
                        ev["bersagli"] = [("io" if b == st["me"] else "lui" if b in (1, 2) else tavolo.nome_oggetto(b)) for b in bers]
                        ev["bersagli_di"] = [("io" if b == st["me"] else "lui" if b in (1, 2) else
                                              self.chi(st, (st["obj"].get(b) or {}).get("controllerSeatId") or (st["obj"].get(b) or {}).get("ownerSeatId"))) for b in bers]
                        break
        self.prima[st["mid"]] = ora
        for i in ora:
            self.grp[i] = st["obj"][i].get("grpId")
        for seat, p in st["pl"].items():
            if "lifeTotal" in p:
                s["vite_finali"][self.chi(st, seat)] = p["lifeTotal"]
        if st.get("fine"):
            for r in st["fine"].get("resultList", []):
                if r.get("scope") == "MatchScope_Match":
                    s["esito"] = "vinta" if r.get("winningTeamId") == st.get("mio_team") else "persa"
                    s["motivo"] = (r.get("reason") or "").replace("ResultReason_", "")


def leggi_file(path, reg):
    t = tavolo.Tracker()
    t.on_msg = reg.on_msg
    for riga in open(path, encoding="utf-8", errors="ignore"):
        m = TS.search(riga[:200])
        if m:
            reg.ts = datetime.datetime.fromtimestamp(int(m.group(1)) / 1000).strftime("%Y-%m-%dT%H:%M")
        t.feed(riga)
        if t.stato and t.stato.get("fine") and t.stato["mid"] in reg.partite:
            reg.on_msg(t.stato)


def pulisci(n):
    return re.sub(r"[^A-Za-z0-9]+", "", n or "")[:20] or "anonimo"


def pezzi(eventi):
    """Divide una lista di eventi nei pezzi letti da file diversi: dentro un file il turno non torna mai indietro."""
    out, cur, ultimo = [], [], -1
    for e in eventi:
        if e["t"] < ultimo:
            out.append(cur)
            cur = []
        cur.append(e)
        ultimo = e["t"]
    if cur:
        out.append(cur)
    return out


def unisci_pezzi(lista):
    """Per ogni turno tiene gli eventi del pezzo che ne ha di piu' (la lettura piu' completa di quel turno).
    Fino al 9 ott 2026 i pezzi si accodavano: una partita presente in due log usciva doppia
    (106 schede su 252, fra cui il Quick Draft con booflord copiato per intero)."""
    per_turno = {}
    for i, p in enumerate(lista):
        for e in p:
            per_turno.setdefault(e["t"], {}).setdefault(i, []).append(e)
    eventi = []
    for t in sorted(per_turno):
        scelto = max(per_turno[t].items(), key=lambda kv: (len(kv[1]), -kv[0]))[1]
        eventi += scelto
    return eventi


def unisci_schede(schede):
    """Piu' letture della stessa partita (una per file di log) -> una scheda sola, senza doppioni."""
    base = max(schede, key=lambda s: (s["turni"], len(s["eventi"])))
    s = dict(base)
    s["eventi"] = unisci_pezzi([x["eventi"] for x in schede if x["eventi"]])
    s["turni"] = max(x["turni"] for x in schede)
    s["esito"] = next((x["esito"] for x in schede if x.get("esito")), None)
    s["motivo"] = next((x["motivo"] for x in schede if x.get("esito")), None)
    s["inizio"] = min((x["inizio"] for x in schede if x.get("inizio")), default=None)
    for k in ("mio_mazzo_visto", "sue_carte_viste"):
        s[k] = list(dict.fromkeys(n for x in schede for n in x[k]))
    return s


def ripara_archivio():
    """Toglie i doppioni dalle schede gia' archiviate (i loro log vecchi spesso non ci sono piu')."""
    riparate = 0
    for p in sorted(DEST.glob("*.json")):
        s = json.load(open(p, encoding="utf-8"))
        nuovi = unisci_pezzi(pezzi(s["eventi"]))
        if len(nuovi) != len(s["eventi"]):
            print(f"  {p.name}: {len(s['eventi'])} -> {len(nuovi)} eventi")
            s["eventi"] = nuovi
            json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            riparate += 1
    print(f"schede riparate {riparate}")


def main():
    if "--ripara" in sys.argv:
        ripara_archivio()
        return
    fonti = [SRC / "Player.log", SRC / "Player-prev.log"]
    if "--solo-attuale" not in sys.argv:
        fonti += sorted(Path(p) for p in glob.glob(str(ROOT / "Log_Arena" / "*.log")))
    letture = {}
    for f in fonti:
        if f.exists():
            r = Registro()  # un registro per file: la stessa partita in due log non si accoda due volte
            leggi_file(f, r)
            for mid, s in r.partite.items():
                letture.setdefault(mid, []).append(s)
    reg = Registro()
    reg.partite = {mid: unisci_schede(v) for mid, v in letture.items()}
    nuove = aggiornate = 0
    esistenti = {}
    for p in DEST.glob("*.json"):
        try:
            esistenti[json.load(open(p, encoding="utf-8"))["matchId"]] = p
        except Exception:
            pass
    for mid, s in reg.partite.items():
        if not s["eventi"] or not s.get("avversario") or s["avversario"] == "?":
            continue
        if mid in esistenti:
            vecchia = json.load(open(esistenti[mid], encoding="utf-8"))
            if len(vecchia.get("eventi", [])) >= len(s["eventi"]) and vecchia.get("esito"):
                continue
            percorso = esistenti[mid]; aggiornate += 1
        else:
            data = (s["inizio"] or "0000-00-00T00:00").replace(":", "").replace("T", "_")
            percorso = DEST / f"{data}_{pulisci(s['evento'])}_{pulisci(s['avversario'])}_{mid[:8]}.json"
            nuove += 1
        json.dump(s, open(percorso, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"partite lette {len(reg.partite)} | nuove {nuove} | aggiornate {aggiornate} | in archivio {len(list(DEST.glob('*.json')))}")


if __name__ == "__main__":
    main()
