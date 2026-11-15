"""I pick del draft nel Leak Finder (15 nov 2026, Autore: «prosegui con i pick del draft»; la pagella dell'enciclopedia, capitoli 20 e 23: segnali, ruote,
il pick a cui ti impegni, la prima scelta nel mazzo, le rare, il drafter).

Dai log di Arena (Log_Arena/*Player*.log e il Player.log di adesso), per ogni draft: l'evento, quando comincia, i pack visti (DraftPack, a ogni pick) e
le carte prese (BotDraftDraftPick, Quick Draft coi bot). Un draft che sta in piu' log si unisce per evento e primo pack, come fa lo strumento del drafter
(citta_quick, che non si tocca: e' blindato). Ogni log si legge una volta: la copia sta in Log_Arena/draft_letti.json (VERSIONE).
Dai diari del companion (Log_Arena/companion_AAAAMMGG.txt) il consiglio del drafter a ogni pick («PICK p-k: PRENDI -> carta»): c'e' solo dove il companion
seguiva il draft (nell'app pubblica il Drafter non c'e': la voce resta vuota).

Ogni partita Limited prende il suo draft: lo stesso evento, il draft cominciato prima della partita e piu' vicino (DA.riga -> «draft»). Le voci della partita
(campi):
  d_impegno    il pick da cui l'80% dei pick colorati sta nei colori del tuo mazzo: «Pack 1, picks 1-5», «Pack 1, picks 6+», «Pack 2», «Pack 3», «Never»;
  d_p1         quanti dei pick colorati del pack 1 stanno nei colori del mazzo: «Most (75%+)», «Half (40-75%)», «Few (under 40%)»;
  d_ruote      il segnale della ruota: le carte dei colori del tuo mazzo ancora nel tuo primo pack quando torna (pack 1, pick 9): «0», «1-2», «3+»;
  d_p1p1       la prima scelta e' nel mazzo: «Yes», «No»;
  d_rare_prese le rare e mitiche prese; d_rare_passate quelle viste e mai prese: «0», «1-2», «3+»;
  d_drafter    i pick diversi dal consiglio del drafter: «0», «1-3», «4+» (None senza il diario).
Il Premier Draft (umani) scrive i pick in un altro modo, e nei log di oggi non ce n'e' uno: non e' letto (si dice, non si tace).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import bisect  # noqa: E402
import datetime  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

VERSIONE = 1
CASA = os.path.join(percorsi.ROOT, "Log_Arena")
COPIA = os.path.join(CASA, "draft_letti.json")
RX_ORA = re.compile(rb"\[UnityCrossThreadLogger\](\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d):(\d\d)")
RX_PACK = re.compile(rb'\\?"EventName\\?"\s*:\s*\\?"([^"\\]+)\\?"[^\n]*?\\?"PackNumber\\?"\s*:\s*(\d+)\s*,\s*\\?"PickNumber\\?"\s*:\s*(\d+)[^\n]*?'
                     rb'\\?"DraftPack\\?"\s*:\s*\[([^\]]*)\]')
RX_PICK = re.compile(rb'BotDraftDraftPick[^\n]*?\\?"EventName\\?"\s*:\s*\\?"([^"\\]+)\\?"[^\n]*?\\?"CardIds\\?"\s*:\s*\[([^\]]*)\][^\n]*?'
                     rb'\\?"PackNumber\\?"\s*:\s*(\d+)\s*,\s*\\?"PickNumber\\?"\s*:\s*(\d+)')
RX_DIARIO_DRAFT = re.compile(r"^(\d\d):(\d\d):(\d\d) === DRAFT: (\S+)")
RX_DIARIO_PICK = re.compile(r"^(\d\d):(\d\d):(\d\d) PICK (\d+)-(\d+): PRENDI -> ([^|(]+)")
_MEMO = {}


def leggi_file(path):
    """I draft di un log: [dict(evento, inizio (ms), pack {"pn-kn": [grpId]}, pick {"pn-kn": grpId})]. Un draft comincia al pack 0, pick 0."""
    try:
        data = open(path, "rb").read()
    except OSError:
        return []
    ore = [(m.start(), m.groups()) for m in RX_ORA.finditer(data)]
    pos_ore = [p for p, _g in ore]

    def ora(pos):
        i = bisect.bisect_right(pos_ore, pos) - 1
        if i < 0:
            return None
        g, me, an, o, mi, se = (int(x) for x in ore[i][1])
        try:
            return int(datetime.datetime(an, me, g, o, mi, se).timestamp() * 1000)
        except ValueError:
            return None
    eventi = []
    for m in RX_PACK.finditer(data):
        eventi.append((m.start(), "pack", m.group(1).decode(), int(m.group(2)), int(m.group(3)), [int(x) for x in re.findall(rb"\d+", m.group(4))]))
    for m in RX_PICK.finditer(data):
        ids = [int(x) for x in re.findall(rb"\d+", m.group(2))]
        if ids:
            eventi.append((m.start(), "pick", m.group(1).decode(), int(m.group(3)), int(m.group(4)), ids[0]))
    eventi.sort(key=lambda e: e[0])
    out, cur = [], {}
    for pos, tipo, ev, pn, kn, val in eventi:
        if tipo == "pack" and pn == 0 and kn == 0:
            cur[ev] = dict(evento=ev, inizio=ora(pos), pack={}, pick={})
            out.append(cur[ev])
        d = cur.get(ev)
        if d is None:
            continue
        if tipo == "pack":
            d["pack"].setdefault(f"{pn}-{kn}", val)
        else:
            d["pick"].setdefault(f"{pn}-{kn}", val)
    return out


def tutti(file_=None):
    """I draft di tutti i log, uniti per evento e primo pack, dal piu' vecchio. La copia su disco tiene i draft di ogni log per nome e misura."""
    try:
        copia = json.load(open(COPIA, encoding="utf-8"))
        if copia.get("v") != VERSIONE:
            copia = {"v": VERSIONE, "file": {}}
    except (OSError, ValueError):
        copia = {"v": VERSIONE, "file": {}}
    if file_ is None:
        file_ = sorted(glob.glob(os.path.join(CASA, "*Player*.log")))
        try:
            import piattaforma
            pl = piattaforma.player_log()
            file_ += [p for p in (pl, pl.replace("Player.log", "Player-prev.log")) if p and os.path.exists(p)]
        except Exception:      # noqa: BLE001 - senza il Player.log di adesso restano gli archivi
            pass
    cambiato = False
    uniti = {}
    for p in file_:
        try:
            st = os.stat(p)
        except OSError:
            continue
        k = os.path.basename(p) if CASA in os.path.abspath(p) else os.path.abspath(p)
        c = copia["file"].get(k)
        if not c or c.get("misura") != st.st_size:
            c = {"misura": st.st_size, "draft": leggi_file(p)}
            copia["file"][k] = c
            cambiato = True
        for d in c["draft"]:
            if "0-0" not in d["pack"]:
                continue
            chiave = (d["evento"], tuple(d["pack"]["0-0"]))
            u = uniti.setdefault(chiave, dict(evento=d["evento"], inizio=d["inizio"], pack={}, pick={}))
            u["inizio"] = min(x for x in (u["inizio"], d["inizio"]) if x) if (u["inizio"] or d["inizio"]) else None
            for kk, v in d["pack"].items():
                u["pack"].setdefault(kk, v)
            for kk, v in d["pick"].items():
                u["pick"].setdefault(kk, v)
    if cambiato:
        try:
            tmp = COPIA + ".tmp"
            json.dump(copia, open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, COPIA)
        except OSError:
            pass
    return sorted(uniti.values(), key=lambda d: d["inizio"] or 0)


def consigli():
    """I consigli del drafter dai diari del companion: [dict(evento, inizio (ms), pick {"pn-kn": nome})] (pn e kn da 0, come nel log)."""
    out = []
    for p in sorted(glob.glob(os.path.join(CASA, "companion_2*.txt"))):
        m_ = re.search(r"companion_(\d{4})(\d\d)(\d\d)\.txt$", p)
        if not m_:
            continue
        giorno = datetime.datetime(int(m_.group(1)), int(m_.group(2)), int(m_.group(3)))
        prima, cur = None, None
        try:
            righe = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for r in righe:
            t_ = re.match(r"^(\d\d):(\d\d):(\d\d) ", r)
            if not t_:
                continue
            ora = giorno + datetime.timedelta(hours=int(t_.group(1)), minutes=int(t_.group(2)), seconds=int(t_.group(3)))
            if prima is not None and ora < prima - datetime.timedelta(hours=1):     # dopo mezzanotte il diario resta quello del giorno prima
                giorno += datetime.timedelta(days=1)
                ora += datetime.timedelta(days=1)
            prima = ora
            md = RX_DIARIO_DRAFT.match(r)
            if md:
                cur = dict(evento=md.group(4), inizio=int(ora.timestamp() * 1000), pick={})
                out.append(cur)
                continue
            mp = RX_DIARIO_PICK.match(r)
            if mp and cur is not None:
                cur["pick"].setdefault(f"{int(mp.group(4)) - 1}-{int(mp.group(5)) - 1}", mp.group(6).strip())
    return out


def _colori(n, DA):
    return set((DA._carta(n) or {}).get("colori") or "") & set("WUBRG")


def campi(draft, deck, DA, consiglio=None):
    """Le voci di un draft per una partita col suo mazzo (deck: {nome: copie}). -> dict (vuoto senza pick)."""
    if not draft or not draft.get("pick"):
        return {}
    nome = lambda g: DA.nome_intero(DA.nome_grp(g) or "") if g not in DA.SENZA_FACCIA else ""
    ordine = sorted(draft["pick"], key=lambda k: tuple(int(x) for x in k.split("-")))
    presi = [(k, nome(draft["pick"][k])) for k in ordine]
    nel_mazzo = {n for n, q in (deck or {}).items() if q}
    col_mazzo = set().union(*[_colori(n, DA) for n in nel_mazzo if not DA.e_terra(n)] or [set()])
    out = {}
    colorati = [(k, n, _colori(n, DA)) for k, n in presi if n and _colori(n, DA)]
    if col_mazzo and colorati:
        dentro = [c <= col_mazzo for _k, _n, c in colorati]
        impegno = None
        for i in range(len(colorati)):
            resto = dentro[i:]
            if resto and sum(resto) / len(resto) >= 0.8:
                impegno = colorati[i][0]
                break
        if impegno is None:
            out["d_impegno"] = "Never"
        else:
            pn, kn = (int(x) for x in impegno.split("-"))
            out["d_impegno"] = ("Pack 1, picks 1-5" if kn < 5 else "Pack 1, picks 6+") if pn == 0 else "Pack 2" if pn == 1 else "Pack 3"
        p1 = [d_ for (k, _n, _c), d_ in zip(colorati, dentro) if k.startswith("0-")]
        if p1:
            q = sum(p1) / len(p1)
            out["d_p1"] = "Most (75%+)" if q >= 0.75 else "Half (40-75%)" if q >= 0.4 else "Few (under 40%)"
    if nel_mazzo:
        # il segnale della ruota: quando il tuo primo pack torna (pack 1, pick 9) quante carte dei colori del tuo mazzo c'erano ancora. Nel Quick ogni pick dal 9
        # in poi e' una ruota per costruzione, quindi contare le carte prese in ruota non distingueva niente (le prime prove: «3+» in tutte le 58 partite)
        ritorno = draft["pack"].get("0-8")
        if ritorno is not None and col_mazzo:
            ruote = sum(1 for g in ritorno if (n := nome(g)) and not DA.e_terra(n) and _colori(n, DA) and _colori(n, DA) <= col_mazzo)
            out["d_ruote"] = "0" if not ruote else "1-2" if ruote <= 2 else "3+"
        p1p1 = dict(presi).get("0-0")
        if p1p1:
            out["d_p1p1"] = "Yes" if p1p1 in nel_mazzo else "No"
    rar = lambda n: (DA._carta(n) or {}).get("r") in ("R", "M")
    prese = {n for _k, n in presi if n and rar(n)}
    viste = {nome(g) for pack in draft["pack"].values() for g in pack}
    passate = {n for n in viste if n and rar(n)} - prese
    fascia = lambda v: "0" if v == 0 else "1-2" if v <= 2 else "3+"
    out["d_rare_prese"], out["d_rare_passate"] = fascia(len(prese)), fascia(len(passate))
    if consiglio and consiglio.get("pick"):
        diversi = sum(1 for k, n in presi if k in consiglio["pick"] and n and DA.nome_intero(consiglio["pick"][k]) != n)
        out["d_drafter"] = "0" if diversi == 0 else "1-3" if diversi <= 3 else "4+"
        out["_drafter_n"] = diversi
    return out


def assegna(righe, DA, drafts=None, cons=None):
    """Mette nelle partite Limited le voci del loro draft (riga["draft"] = dict, e i campi d_*). Il draft di una partita: lo stesso evento, cominciato prima
    della partita, il piu' vicino; il consiglio del drafter: lo stesso evento, cominciato entro 15 minuti dal draft."""
    drafts = tutti() if drafts is None else drafts
    cons = consigli() if cons is None else cons
    per_ev = {}
    for d in drafts:
        if d.get("inizio"):
            per_ev.setdefault(d["evento"], []).append(d)
    for x in righe:
        if x.get("tipo") != "Limited":
            continue
        ms = int(x["quando"].timestamp() * 1000) if x.get("quando") else None
        lista = per_ev.get(x.get("evento") or "")
        if not lista or ms is None:
            continue
        prima = [d for d in lista if d["inizio"] <= ms]
        if not prima:
            continue
        d = prima[-1]
        k = (d["evento"], d["inizio"], tuple(sorted((x.get("deck") or {}).items())))
        if k not in _MEMO:
            c = next((c for c in cons if c["evento"] == d["evento"] and abs(c["inizio"] - d["inizio"]) <= 15 * 60 * 1000), None)
            _MEMO[k] = campi(d, x.get("deck") or {}, DA, c)
        x["draft"] = dict(evento=d["evento"], inizio=d["inizio"], pick=len(d["pick"]))
        x.update({kk: v for kk, v in _MEMO[k].items() if not kk.startswith("_")})
        x["_drafter_n"] = _MEMO[k].get("_drafter_n")
    return righe


NOMI = {"d_impegno": "Draft · the pick you settled into your deck's colors", "d_p1": "Draft · your pack 1 picks in your deck's colors",
        "d_ruote": "Draft · cards in your deck's colors still in your first pack when it wheeled", "d_p1p1": "Draft · your first pick is in your deck",
        "d_rare_prese": "Draft · rares and mythics you took", "d_rare_passate": "Draft · rares and mythics you saw and passed",
        "d_drafter": "Draft · picks different from the drafter"}
ORDINE = {"d_impegno": ("Pack 1, picks 1-5", "Pack 1, picks 6+", "Pack 2", "Pack 3", "Never"),
          "d_p1": ("Most (75%+)", "Half (40-75%)", "Few (under 40%)"), "d_ruote": ("0", "1-2", "3+"), "d_p1p1": ("Yes", "No"),
          "d_rare_prese": ("0", "1-2", "3+"), "d_rare_passate": ("0", "1-2", "3+"), "d_drafter": ("0", "1-3", "4+")}


def prova():
    casi = []
    riga = lambda pn, kn, pack, ev="QuickDraft_FRA_20261008": ('[UnityCrossThreadLogger]09/10/2026 03:%02d:00\n{"CurrentModule":"BotDraft","Payload":"{\\"EventName\\":\\"%s\\",'
                                                              '\\"DraftStatus\\":\\"PickNext\\",\\"PackNumber\\":%d,\\"PickNumber\\":%d,\\"DraftPack\\":[%s]}"}\n'
                                                              % (pn * 14 + kn, ev, pn, kn, ",".join('\\"%d\\"' % g for g in pack)))
    pick = lambda pn, kn, g, ev="QuickDraft_FRA_20261008": ('[UnityCrossThreadLogger]==> BotDraftDraftPick {"request":"{\\"EventName\\":\\"%s\\",\\"PickInfo\\":'
                                                           '{\\"EventName\\":\\"%s\\",\\"CardIds\\":[\\"%d\\"],\\"PackNumber\\":%d,\\"PickNumber\\":%d}}"}\n'
                                                           % (ev, ev, g, pn, kn))
    import tempfile
    testo = riga(0, 0, [1, 2, 3, 9]) + pick(0, 0, 1) + riga(0, 1, [4, 5]) + pick(0, 1, 4) + riga(0, 8, [2, 9]) + pick(0, 8, 2)
    p = os.path.join(tempfile.gettempdir(), "draft_log_prova.log")
    open(p, "w", encoding="utf-8").write(testo)
    dd = leggi_file(p)
    casi.append(("un draft: l'evento, l'ora del primo pack, i pack e i pick per pack-pick", len(dd) == 1 and dd[0]["evento"] == "QuickDraft_FRA_20261008"
                 and dd[0]["pack"]["0-0"] == [1, 2, 3, 9] and dd[0]["pick"] == {"0-0": 1, "0-1": 4, "0-8": 2} and dd[0]["inizio"]))
    open(p, "w", encoding="utf-8").write(testo + riga(0, 0, [7, 8]) + pick(0, 0, 7))
    casi.append(("un secondo pack 0-0 dello stesso evento e' un draft nuovo", [len(d["pick"]) for d in leggi_file(p)] == [3, 1]))
    open(p, "w", encoding="utf-8").write(pick(0, 0, 1))
    casi.append(("negativa: un pick senza il pack 0-0 non fa un draft", leggi_file(p) == []))
    os.remove(p)

    class FintoDA:
        SENZA_FACCIA = set()
        carte = {"A": dict(colori="W", r="R"), "B": dict(colori="U", r="C"), "C": dict(colori="W", r="U"), "D": dict(colori="W", r="M"), "E": dict(colori="R", r="C")}

        @staticmethod
        def nome_grp(g):
            return {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 9: "C"}.get(g)

        @staticmethod
        def nome_intero(n):
            return n

        @classmethod
        def _carta(cls, n):
            return cls.carte.get(n)

        @staticmethod
        def e_terra(n):
            return False
    dr = dict(evento="Q", inizio=1, pack={"0-0": [1, 2, 3, 9], "0-1": [4, 5], "0-8": [3, 2]}, pick={"0-0": 1, "0-1": 4, "0-8": 3})
    c = campi(dr, {"A": 1, "D": 1, "C": 1}, FintoDA, dict(pick={"0-0": "A", "0-1": "E", "0-8": "C"}))
    casi.append(("le voci: tutto bianco dal primo pick, la prima scelta nel mazzo, al ritorno del primo pack una carta bianca (C; B e' blu), 2 rare prese (A, D), un pick diverso "
                 "dal drafter", c.get("d_impegno") == "Pack 1, picks 1-5" and c.get("d_p1p1") == "Yes" and c.get("d_ruote") == "1-2"
                 and c.get("d_rare_prese") == "1-2" and c.get("d_rare_passate") == "0" and c.get("d_drafter") == "1-3" and c.get("d_p1") == "Most (75%+)"))
    c2 = campi(dr, {"D": 1, "C": 1, "B": 2}, FintoDA)
    casi.append(("negativa: un mazzo senza la prima scelta dice No, e senza il diario niente voce del drafter", c2.get("d_p1p1") == "No" and "d_drafter" not in c2))
    casi.append(("negativa: senza pick niente voci", campi(dict(pick={}, pack={}), {"A": 1}, FintoDA) == {}))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
