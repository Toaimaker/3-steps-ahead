"""L'ambiente della finestra: cartelle, file di stato in Log_Arena, il giocatore, nome e versione del prodotto, le opzioni di avvio."""
import os
import sys

import percorsi


ROOT = percorsi.ROOT
LOGDIR = os.path.join(ROOT, "Log_Arena")
# --diario FILE (collaudo, 17 ott 2026): la finestra legge quel diario invece di quello di oggi, per esempio il diario di un
# replay (Log_Arena/companion_replay_AAAAMMGG.txt); le ore delle righe valgono come ore di oggi
DIARIO_FISSO = sys.argv[sys.argv.index("--diario") + 1] if "--diario" in sys.argv else None
PRODOTTO, VERSIONE = "3 Steps Ahead", "0.1.10"      # in fondo a destra in ogni scheda (Autore, 4 nov 2026); si alza a ogni rilascio. Dal 10 nov 2026 il nome
# dell'app, anche questa di Autore: «3 Steps Ahead» (fino a quel giorno «Companion Magic Arena»)
ASSET = percorsi.GRAFICA      # font, icone, simboli, loghi: Companion/Grafica
import account as _ACC     # chi usa l'app: Autore, o nell'app pubblica chi l'ha scaricata (account.py, 10 nov 2026)
PUBBLICA = _ACC.PUBBLICA


def rinfresca_account():
    """Il profilo di Untapped e il nome in gioco dell'account mostrato: si rifanno quando cambia l'account (account.applica, 10 nov 2026, Magic 12). Chi li usa
    li legge come ambiente.NOME_PLAYER, non con «from ambiente import»."""
    global USER, PLAYER, NOME_PLAYER, DECK_URL
    a = _ACC.account()
    USER, PLAYER = a["untapped_user"] or "", a["untapped_player"] or ""     # il profilo di Untapped: nell'app pubblica solo se l'utente lo collega
    NOME_PLAYER = a["nome"] or "You"     # il nome in gioco
    DECK_URL = f"https://mtga.untapped.gg/profile/{USER}/{PLAYER}/deck/{{id}}?gameType=limited&limitedSet={{set}}"


rinfresca_account()
_ACC.al_cambio(rinfresca_account)
INVIATO_JSON = os.path.join(LOGDIR, "mazzo_inviato.json")
FIX_JSON = os.path.join(LOGDIR, "mazzo_fix.json")
MAZZI_JSON = os.path.join(LOGDIR, "mazzi_costruzione.json")   # i 3 mazzi proposti (rating_mazzi)
PICK_JSON = sys.argv[sys.argv.index("--pick-json") + 1] if "--pick-json" in sys.argv else os.path.join(LOGDIR, "mazzi_pick.json")   # i 3 mazzi durante i pick (mazzi_in_corsa)
PY_MUTO = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")    # senza console: i lavori a parte della finestra
POS_JSON = os.path.join(LOGDIR, "finestra_pos.json")     # dove sta la finestra (Autore, 5 nov 2026: «smettila di ricaricare il drafter sullo schermo 1, fallo sul 2»)
FUORI_SCHERMO = "--fuori-schermo" in sys.argv            # collaudo: una finestra di prova non si apre mai davanti a Autore
