# I glitch del replayer: il registro

Autore, 14 nov 2026: *«continua a raccogliere dati in merito ai glitch, bug ed errori che risolviamo / vogliamo essere sempre sicuri d'ora in poi di
non ripeterli mai»*.

Ogni glitch risolto entra qui con la sua causa, la correzione e il controllo che lo ripesca. Il controllo automatico è
`py -I -X utf8 Companion/Strumenti/caccia_glitch.py [--partite N] [id ...]`: rigioca le partite vere passo per passo, fuori schermo, ed esce 1 su un glitch.
È nel giro di `Companion/Strumenti/prove_app.py` (completo, non `--rapide`). Le prove una per una stanno in `Companion/App/Prove/prova_performance.py`,
`disegno_tappeto.py --prova`, `replay_log.py --prova`.

**Prima di toccare il replayer**: si legge questo registro. **Dopo**: `caccia_glitch.py` verde e le prove verdi. **Un glitch nuovo**: una riga qui e, se
si può, un controllo in `caccia_glitch.py` o una prova, con la negativa.

La regola sopra tutte (Autore): l'osservatore è un bambino sordo che non sa leggere. Un'azione alla volta, in ordine, lenta; le scritte aiutano, mai
l'unico modo di capire.

| # | Il glitch (come l'ha visto Autore) | La causa | La correzione | Il controllo |
| :- | :- | :- | :- | :- |
| 1 | Le carte sparivano dal tavolo e comparivano già nel cimitero o in esilio, poi arrivava il volo | la carta in partenza non aveva un «fermo» al suo posto; la pila d'arrivo era già quella nuova | ogni carta resta dov'era finché vola; la pila coperta con quella di prima | G-ANIM; prova «ogni carta resta dov'era» |
| 2 | Le terre tornavano nel mazzo dopo lo stap | le partenze contate per riquadri: una terra stappata cambia gruppo ×N | le partenze contate per carte, dalle foto | G-GRIM; prova «nessuna carta vola nel grimorio» |
| 3 | La magia contrastata andava «dal mazzo» al cimitero | il replayer conosceva solo la cima della pila | le magie lanciate nel turno partono dalla pila | G-GRIM |
| 4 | La pila spariva quando l'avversario pagava per rispondere | il passo del pagamento non aveva la magia come relazione | la pila intera in ogni foto (`replay_log` «p») | G-PILA; `replay_log --prova` «lui paga per rispondere» |
| 5 | La vita cambiava prima del danno | la vita è nel fondo, già nuova | coperta col cerchio di prima finché non compare il danno; nei duelli scende colpo per colpo | prova «la vita colpita resta quella di prima» |
| 6 | Le carte non andavano sui bloccanti, sparivano di colpo | il passo del danno perde il bloccante morto; pedine raggruppate | il combattimento dichiarato nel turno; chi combatte non si raggruppa | G-DUELLO |
| 7 | Sulla pila d'arrivo una «carta grigia», la carta in volo ci passava sotto | la copertura era un'immagine rifatta a parte, creata dopo il volo | il ritaglio esatto del tavolo di prima; il volo sempre sopra | foto |
| 8 | Il planeswalker prendeva danno «senza essere attaccato» | un blocco scelto e poi tolto dall'avversario restava nel log | un blocco vale solo se il danno del turno lo conferma (`blocchi_veri`) | G-BLOCCO |
| 9 | Due attaccanti impilati uno sotto l'altro | pedine uguali raggruppate col ×N anche in combattimento | chi combatte sta da solo; le pedine creatura sotto le 4 copie sempre da sole | `disegno_tappeto --prova` |
| 10 | La pila appariva e spariva | il riquadro era nella stessa immagine della carta | il riquadro STACK c'è prima della carta e resta dopo l'uscita | G-PILA |
| 11 | La pila spariva tutta mentre una carta ci volava dentro, o durante una risoluzione | si nascondeva l'immagine della pila (con le magie sotto) | resta a vista la pila di prima; niente più pila nascosta | G-PILA, foto |
| 12 | Chi usciva dalla pila era piccolo (grande come in campo) | l'immagine del volo era quella d'arrivo | parte grande come la carta in pila | foto |
| 13 | Le creature si tappavano nel passo dei bloccanti | Arena scrive la tappatura degli attaccanti nel messaggio dopo | `replay_log`: tappati già al passo dell'attacco | foto |
| 14 | La fila delle creature si rifaceva di colpo | separarsi all'attacco faceva passare a due file | pedine creatura da sole sotto 4; le carte scivolano cambiando misura | foto |
| 15 | La creatura accanto passava sotto quella morta | il riordino del tavolo era immediato | chi esce va via per primo, poi le altre scivolano una alla volta | G-ANIM |
| 16 | I «-N» passavano dietro le carte | i danni erano creati sotto chi colpisce | i danni sopra a tutto, sull'angolo della carta colpita, si muovono con lei | foto |
| 17 | Gruppi di terre o pedine che sparivano e ricomparivano «+1» | il gruppo era nascosto finché la carta nuova non arrivava | il gruppo col numero di prima resta, il numero sale all'arrivo | foto |
| 18 | La pescata dell'avversario «diventava trasparente» | il ventaglio aveva già la carta nuova; il dorso spariva all'arrivo | la carta nuova del ventaglio nascosta finché il dorso non arriva al suo posto | foto |
| 19 | Settle the Wreckage: le frecce dopo l'esilio | le frecce di una magia comparivano dopo i voli | una magia già in pila che si risolve: prima le frecce, poi l'effetto | foto |
| 20 | «-N» e frecce restavano dopo la morte | niente li toglieva | via quando la carta arriva al cimitero o in esilio | G-DANNI dei morti |
| 21 | Le animazioni scattavano | contate a fotogrammi: un ritardo le rallentava | guidate dal tempo vero, un fotogramma ogni 8 ms | foto |
| 22 | I «-N» erano tondi rossi uguali per chi colpisce e chi e' colpito; le carte morte solo grigie | — (una richiesta di chiarezza) | la goccia col «-N» su chi perde, la spada col numero su chi colpisce, il teschio sulle carte morte | foto |
| 23 | Il «-N» di una pedina morta restava a vista (trovato dalla caccia) | le pedine morte si spengono al loro posto, e lo spegnersi non toglieva «-N» e frecce | `via_con_lui` anche per le pedine che si spengono | G-DANNI dei morti |
| 24 | Con due carte uguali in campo e una morta, diventava grigia e volava quella sbagliata (trovato dalla caccia: due Semester Foreseer) | chi esce dal campo si sceglieva per nome | si riconosce per l'id di Arena; il nome solo per i gruppi ×N | G-DANNI dei morti |
| 25 | Le carte che chiedono una scelta (Perforating Artist: «perde 3 vite a meno che…») non mostravano niente | l'abilita' va in pila e si risolve nello stesso messaggio di Arena: nessun passo con lei in pila; la vita persa senza danno non aveva segno | `replay_log`: un passo con l'abilita' in pila e la freccia verso chi ne subisce l'effetto, poi la perdita di vite come goccia | `replay_log --prova` «l'abilita' che si risolve subito» |
| 26 | Le gocce segnavano i danni a caso | chi colpisce chi si ricavava dai nomi del racconto; gocce uguali una sopra l'altra mostravano l'ultima | ogni danno porta l'id di chi lo infligge (`replay_log`, settimo campo del passo); nel duello gocce e spade dai danni veri; fuori dai duelli una goccia per carta col totale | `replay_log --prova` «i danni (con chi li infligge)» |
| 27 | La carta a due facce morta volava nel grimorio | sul tavolo ha il nome della faccia dietro (Neo Exdeath), nel cimitero quello davanti (Exdeath, Void Warlock): l'uscita dal campo cercava il nome nel cimitero, non lo trovava e la mandava nel grimorio | se il nome non c'e', vale la carta nuova del cimitero o dell'esilio che il racconto del passo nomina | `caccia_glitch.py e3b900da` (G-GRIM al passo 67) |
| 28 | Il riquadro vuoto della pila restava sul tavolo | un passo senza niente da animare non usciva piu' all'inizio (controlla anche i gesti nuovi del censimento) e il riquadro provvisorio della pila restava | senza azioni si cancella ogni pezzo provvisorio; e la caccia aspetta il segnale di fine animazione (`_anim_in_corso`), non l'assenza di pezzi provvisori: fra due duelli non ce ne sono | `caccia_glitch.py b97a4757 af3ae90b` |
| 29 | Il surveil dell'avversario (Wary Thespian) non mostrava niente | Arena non gli manda la richiesta con le carte guardate: il replayer leggeva solo quella | l'effetto segnato da Arena (MultistepEffect, SubCategory 11) fa il ventaglio, le tenute coperte, quante dal testo dell'abilita' | `replay_log.py --prova`, con la negativa |
| 30 | Le piastre del danno e della vita finivano dietro le carte | le copie delle carte che si animano nascono dopo le piastre e le coprivano | `alza_icone` fra un'azione e l'altra, a fine passo, dopo i danni (15 nov 2026) | foto del passo del danno |
| 31 | Aure ed equipaggiamenti stavano in campo come carte a parte | il replayer non leggeva chi porta chi | le annotazioni Attachment di Arena (`replay_log.segni` -> «porta»/«su»): l'aura sta dietro la carta che la porta, sfalsata in alto, e quando arriva vola dalla pila su di lei (15 nov 2026) | partita cc3c3419 passo 60 (Angelic Destiny su Elenda), caccia verde |
| 32 | L'aura che cade quando muore la creatura volava dal grimorio | l'aura attaccata non ha un pezzo suo sul tavolo, quindi la sua uscita dal campo non si trovava e il cimitero la prendeva per macinata | parte da sotto la carta che la portava, dove era disegnata (`anima_board`, «su» della foto di prima; 15 nov 2026) | partita da00bc58 passo 152 (Unflinching Courage), caccia verde |
| 33 | Multiversal Passage risultava «NO ABILITIES» ed Exemplar of Light «EXHAUSTED» | Arena scrive RemoveAbility della carta su se stessa per farle cambiare tipo, e AbilityExhausted anche per gli inneschi una volta per turno | RemoveAbility solo da un'altra carta; EXHAUSTED solo se l'abilita' dice exhaust, se no USED THIS TURN (15 nov 2026) | `replay_log.py --prova` (le negative), partite 18308c7f e bb7b67c7 |

## Come si cerca un glitch nuovo
1. `caccia_glitch.py` sulle partite dove Autore l'ha visto (l'id dalla riga della partita, «quando»).
2. Le foto: il replayer vero fotografato a intervalli (PrintWindow). Con Autore al PC la finestra di prova sta dietro a tutte, quasi trasparente e
   attraversabile ai clic: mai sopra (14 nov 2026: una finestra invisibile in cima gli ha preso i clic). Fuori schermo la foto esce nera.
3. Il dato prima del disegno: `dati_analizzatore.azioni_partita(x)` passo per passo (relazioni, danni, foto).

## Il censimento e i set nuovi (14 nov 2026)
Quello che il motore sa fare e che Arena scrive nei log, contro quello che il replayer mostra: `CENSIMENTO_REPLAYER.md` (generato da
`py -I -X utf8 Companion/Strumenti/censimento_replayer.py`, tabella in `censimento_replayer.json`). Per un set nuovo: il motore impara il set, il
censimento esce rosso con le voci nuove e ognuna si classifica (le «no» che contano si decidono con Autore), poi la caccia ai glitch sulle prime
partite del set. Un glitch trovato cosi' entra qui sopra col suo controllo.
