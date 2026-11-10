"""Il pulsante Closed session della scheda Drafter (Autore, 8 nov 2026: «metti sul drafter un pulsante che dice closed session / il draft si chiude e parte la rotation post draft»).

Chiude a mano il limited in corso e lancia lo stesso giro di fine draft del companion (companion.Companion.fine_draft): il rito (segnala --fine-draft), l'archivio del log, le ruote nuove
per la citta' e il rigioco del draft col vivo, a priorita' bassa. Il companion lo fa da solo a 7 vinte, a 3 perse o alle dimissioni dall'evento; il pulsante serve quando non se ne accorge
(companion spento, log ripartito) o quando il draft lo lasci tu.

1. Scrive nel diario «=== FINE DRAFT: <evento> W-L · closed session ===»: la finestra torna a Play limited e svuota i mazzi, come a una fine vera.
2. Segna il corso in Log_Arena/draft_chiusi.json: la finestra non lo riapre dal Player.log (limited_dal_log) ne' da Untapped. Un draft nuovo ha un altro CourseId e la prima partita dopo.
3. Il giro di fine draft, salvo che il companion l'abbia gia' fatto per questo draft (una riga «=== FINE DRAFT» dopo l'ultima «=== DRAFT» del diario): non si rifa' due volte.
Il companion acceso non lo sa: se poi il corso arriva davvero a ClaimPrize o a 7-3 rifa' il giro, coi dati in piu'.

    py -I -X utf8 Companion/App/Schede/Drafter/chiudi_draft.py --diario FILE [--evento EV --w N --l N]    chiude e lancia il giro (evento e record dalla finestra se il log non li ha)
    py -I -X utf8 Companion/App/Schede/Drafter/chiudi_draft.py --senza-giro ...                          chiude soltanto
    --log FILE al posto del Player.log; CHIUDI_DRAFT_FILE nell'ambiente al posto di Log_Arena/draft_chiusi.json (collaudi)
    py -I -X utf8 Companion/App/Schede/Drafter/chiudi_draft.py --prova                                   i casi, con la prova negativa
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime, json, re, subprocess, tempfile

ROOT = percorsi.ROOT
LOGDIR = os.path.join(ROOT, "Log_Arena")
FILE = os.environ.get("CHIUDI_DRAFT_FILE") or os.path.join(LOGDIR, "draft_chiusi.json")     # la variabile solo per i collaudi
LUCCHETTO = os.path.join(LOGDIR, "chiudi_draft.lock")
PY = sys.executable.replace("pythonw.exe", "python.exe")
# il log di adesso e quello della sessione prima, come finestra_companion.limited_dal_log: appena Arena riparte il Player.log
# non ha ancora i corsi, e il draft lasciato aperto sta in Player-prev.log (8 nov 2026: due clic su Closed session non hanno
# segnato niente, perche' qui si leggeva solo il Player.log, e la finestra riapriva il draft dal log di prima)
LOG_ARENA = (os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log"),
             os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player-prev.log"))
RX_CORSO = re.compile(r'"CourseId":"([^"]+)","InternalEventName":"([^"]*(?:Draft|Sealed|Cube)[^"]*)","CurrentModule":"([^"]*)"')
RX_VINTE, RX_PERSE = re.compile(r'"CurrentWins":(\d+)'), re.compile(r'"CurrentLosses":(\d+)')
MODULI_APERTI = ("BotDraft", "Draft", "DeckSelect", "CreateMatch", "WaitingForMatch", "Match", "MatchResults")
# il giro del companion a fine draft (companion.Companion.fine_draft), con gli stessi filtri: in chat solo le righe che servono, il resto nei dettagli
GIRO = (("segnala.py", ["--fine-draft"], "RITO ", lambda r: r.startswith("PER AUTORE")),
        ("archivia_log.py", [], "ARCHIVIO ", None),
        ("citta_quick.py", ["--ruote"], "RUOTE ", lambda r: False),
        ("rigioca_draft.py", ["--vivo", "--ripetizioni", "1", "--processi", "6"], "RIGIOCO ", lambda r: "PER AUTORE" in r or r.startswith("- ") and "vivo" in r))


def chiusi(f=None):
    """-> [dict(corso, evento, w, l, quando)] dei draft chiusi a mano, quando e' «AAAA-MM-GG HH:MM:SS»."""
    try:
        with open(f or FILE, encoding="utf-8") as fh:
            v = json.load(fh)
        return v if isinstance(v, list) else []
    except (OSError, ValueError):
        return []


def corsi_chiusi(f=None):
    return {c["corso"] for c in chiusi(f) if c.get("corso")}


def ultima_chiusura(f=None):
    """-> datetime dell'ultima chiusura a mano, None se non ce ne sono."""
    q = [c.get("quando") for c in chiusi(f) if c.get("quando")]
    return datetime.datetime.strptime(max(q), "%Y-%m-%d %H:%M:%S") if q else None


def corso_aperto(files=LOG_ARENA):
    """-> dict(corso, evento, modulo, w, l) dell'ultimo limited aperto nel Player.log, None se non c'e'. Lo stesso conto di finestra_companion.limited_dal_log."""
    for f in files:
        try:
            with open(f, "rb") as fh:
                testo = fh.read().decode("utf-8", "ignore")
        except OSError:
            continue
        corsi = {}
        for m in RX_CORSO.finditer(testo):
            coda = testo[m.end():m.end() + 4000]
            k = coda.find('"InternalEventName"')
            coda = coda[:k] if k > 0 else coda
            v, p = RX_VINTE.search(coda), RX_PERSE.search(coda)
            corsi[m.group(1)] = dict(pos=m.start(), corso=m.group(1), evento=m.group(2), modulo=m.group(3), w=int(v.group(1)) if v else 0, l=int(p.group(1)) if p else 0)
        if not corsi:
            if '"InternalEventName"' in testo:      # Arena ha elencato i corsi e nessuno e' un limited: il log di prima non conta
                return None
            continue
        aperti = [c for c in corsi.values() if c["modulo"] in MODULI_APERTI and c["corso"] not in corsi_chiusi()]
        if aperti:
            c = max(aperti, key=lambda x: x["pos"])
            c.pop("pos")
            return c
        return None
    return None


def fatto_dal_companion(diario):
    """Il companion ha gia' chiuso questo draft: dopo l'ultima riga «=== DRAFT» c'e' una «=== FINE DRAFT»."""
    try:
        with open(diario, encoding="utf-8", errors="replace") as fh:
            righe = [re.sub(r"^\d\d:\d\d:\d\d ", "", r) for r in fh]
    except (OSError, TypeError):
        return False
    ultimo = max((i for i, r in enumerate(righe) if r.startswith("=== DRAFT")), default=-1)
    return any(r.startswith("=== FINE DRAFT") for r in righe[ultimo + 1:])


def scrivi(testo, diario=None, dettaglio=False):
    """Una riga nel diario (o nei dettagli, companion_dettagli_<data>.txt accanto), con l'ora come il companion."""
    print(testo, flush=True)
    if not diario:
        return
    f = diario
    if dettaglio:
        d, n = os.path.split(diario)
        f = os.path.join(d, n.replace("companion_", "companion_dettagli_", 1)) if n.startswith("companion_") else diario
    try:
        with open(f, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{datetime.datetime.now():%H:%M:%S} {testo}\n")
    except OSError:
        pass


def segna(voce, f=None):
    f = f or FILE
    v = chiusi(f) + [voce]
    os.makedirs(os.path.dirname(f), exist_ok=True)
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(v[-200:], fh, ensure_ascii=False, indent=1)
    os.replace(tmp, f)


def lancia(nome, argomenti, prefisso, filtro, diario):
    """Come companion.lancia con basso=True e attendi=True: le righe che passano il filtro nel diario, le altre nei dettagli."""
    try:
        p = subprocess.Popen([PY, "-I", "-X", "utf8", percorsi.programma(nome)] + argomenti, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=ROOT,
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"), text=True, encoding="utf-8", errors="replace", bufsize=1,
                             creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        scrivi(f"COMPANION: {nome} did not start: {e}", diario); return 1
    for r in p.stdout:
        r = r.rstrip()
        if r:
            scrivi(prefisso + r, diario, dettaglio=not (filtro is None or filtro(r) or re.search(r"Traceback|Error:|ERRORE|CADUTA", r)))
    return p.wait()


def libero():
    """Un giro alla volta: il lucchetto col pid, che non vale piu' se quel processo e' morto."""
    try:
        pid = int(open(LUCCHETTO).read().strip())
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if h:
            codice = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codice)); ctypes.windll.kernel32.CloseHandle(h)
            if codice.value == 259:     # STILL_ACTIVE
                return False
    except (OSError, ValueError):
        pass
    return True


def chiudi(diario=None, evento=None, w=None, l=None, giro=True, files=LOG_ARENA, f=None, giro_fn=None):
    """-> dict(voce, giro): giro e' «fatto» se il companion l'aveva gia' fatto, «lanciato», «saltato» (--senza-giro) o «in corso» (un altro giro sta girando)."""
    c = corso_aperto(files) or {}
    voce = dict(corso=c.get("corso"), evento=c.get("evento") or evento or "limited", w=c.get("w", w), l=c.get("l", l),
                quando=f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    gia = fatto_dal_companion(diario)
    segna(voce, f)
    if not gia:
        wl = f" {voce['w']}-{voce['l']}" if voce["w"] is not None and voce["l"] is not None else ""
        scrivi(f"=== FINE DRAFT: {voce['evento']}{wl} · closed session ===", diario)
    if not giro:
        return dict(voce=voce, giro="saltato")
    if gia:
        scrivi("COMPANION: closed session: the post-draft rotation already ran for this draft", diario)
        return dict(voce=voce, giro="fatto")
    if not libero():
        scrivi("COMPANION: closed session: a post-draft rotation is already running", diario)
        return dict(voce=voce, giro="in corso")
    scrivi("COMPANION: closed session: post-draft rotation started (review, log archive, bot wheels, draft replay)", diario)
    (giro_fn or giro_vero)(diario)
    return dict(voce=voce, giro="lanciato")


def giro_vero(diario):
    with open(LUCCHETTO, "w") as fh:
        fh.write(str(os.getpid()))
    try:
        for nome, arg, pre, filtro in GIRO:
            lancia(nome, arg, pre, filtro, diario)
        scrivi("COMPANION: closed session: post-draft rotation finished", diario)
    finally:
        try:
            os.remove(LUCCHETTO)
        except OSError:
            pass


def prova():
    """I casi, in una cartella temporanea: il corso aperto si chiude e non si riapre, il diario dice FINE DRAFT, il giro parte una volta sola, un draft nuovo resta aperto."""
    ok = tot = 0

    def caso(nome, vero):
        nonlocal ok, tot
        tot += 1; ok += bool(vero)
        print(("  ok  " if vero else "  NO  ") + nome)

    d = tempfile.mkdtemp(prefix="chiudi_draft_")
    log, dia, fc = os.path.join(d, "Player.log"), os.path.join(d, "companion_20261108.txt"), os.path.join(d, "draft_chiusi.json")
    corso = lambda cid, ev, mod, w=0, l=0: '{"CourseId":"%s","InternalEventName":"%s","CurrentModule":"%s","CurrentWins":%d,"CurrentLosses":%d}\n' % (cid, ev, mod, w, l)
    open(log, "w").write(corso("A1", "QuickDraft_FRA_20261008", "Complete", 7, 1) + corso("B2", "QuickDraft_FRA_20261008", "CreateMatch", 2, 1))
    open(dia, "w", encoding="utf-8").write("10:00:00 === DRAFT: QuickDraft_FRA_20261008 ===\n10:30:00 === PARTITA: x ===\n")
    global FILE, LUCCHETTO
    vecchio, FILE = FILE, fc
    vecchio_l, LUCCHETTO = LUCCHETTO, os.path.join(d, "chiudi_draft.lock")      # la prova non guarda il giro vero, che puo' girare
    try:
        giri = []
        caso("il corso aperto e' l'ultimo non chiuso", (corso_aperto((log,)) or {}).get("corso") == "B2")
        r = chiudi(dia, files=(log,), f=fc, giro_fn=giri.append)
        testo = open(dia, encoding="utf-8").read()
        caso("record e corso dal log", r["voce"]["corso"] == "B2" and (r["voce"]["w"], r["voce"]["l"]) == (2, 1))
        caso("il diario dice FINE DRAFT col record", "=== FINE DRAFT: QuickDraft_FRA_20261008 2-1 · closed session ===" in testo)
        caso("il giro parte", r["giro"] == "lanciato" and giri == [dia])
        caso("il corso chiuso non si riapre", corso_aperto((log,)) is None and "B2" in corsi_chiusi(fc))
        caso("ultima chiusura letta", ultima_chiusura(fc) is not None)
        r2 = chiudi(dia, files=(log,), f=fc, giro_fn=giri.append)
        caso("un secondo clic non rifa' il giro", r2["giro"] == "fatto" and len(giri) == 1 and open(dia, encoding="utf-8").read().count("=== FINE DRAFT") == 1)
        open(log, "a").write(corso("C3", "QuickDraft_FRA_20261008", "BotDraft"))
        open(dia, "a", encoding="utf-8").write("11:00:00 === DRAFT: QuickDraft_FRA_20261008 ===\n")
        caso("un draft nuovo resta aperto", (corso_aperto((log,)) or {}).get("corso") == "C3" and not fatto_dal_companion(dia))
        open(dia, "a", encoding="utf-8").write("12:00:00 === FINE DRAFT: QuickDraft_FRA_20261008 0-3 ===\n")
        r3 = chiudi(dia, files=(log,), f=fc, giro_fn=giri.append)
        caso("chiuso dal companion: niente giro, niente riga doppia", r3["giro"] == "fatto" and len(giri) == 1 and open(dia, encoding="utf-8").read().count("=== FINE DRAFT") == 2)
        r4 = chiudi(None, evento="PremierDraft_DFT_x", w=1, l=0, files=(os.path.join(d, "manca.log"),), f=fc, giro=False)
        caso("senza log: evento e record dalla finestra", r4["voce"]["evento"] == "PremierDraft_DFT_x" and r4["voce"]["corso"] is None and r4["giro"] == "saltato")
        # prova negativa: senza il segno nel file il corso torna aperto
        open(fc, "w").write("[]")
        caso("prova negativa: senza il segno il corso e' di nuovo aperto", (corso_aperto((log,)) or {}).get("corso") == "C3")
        # il corso lasciato aperto nel log della sessione prima, col log di adesso senza corsi (Arena appena ripartita)
        prev, ora = os.path.join(d, "Player-prev.log"), os.path.join(d, "Player_ora.log")
        open(prev, "w").write(corso("P9", "QuickDraft_FRA_20261027", "CreateMatch", 3, 2))
        open(ora, "w").write("[UnityCrossThreadLogger] niente corsi ancora\n")
        caso("il corso aperto si trova anche nel log di prima", (corso_aperto((ora, prev)) or {}).get("corso") == "P9")
    finally:
        FILE = vecchio; LUCCHETTO = vecchio_l
    print(f"chiudi_draft --prova: {ok}/{tot}")
    return ok == tot


def main():
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    a = sys.argv
    val = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None
    num = lambda k: int(val(k)) if val(k) not in (None, "", "None") else None
    r = chiudi(val("--diario"), val("--evento"), num("--w"), num("--l"), giro="--senza-giro" not in a, files=(val("--log"),) if val("--log") else LOG_ARENA)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
