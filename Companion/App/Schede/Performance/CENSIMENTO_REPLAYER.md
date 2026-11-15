# Il censimento del replayer

Generato da `py -I -X utf8 Companion/Strumenti/censimento_replayer.py`. Non si scrive a mano: si scrive la tabella `censimento_replayer.json`.

Autore, 14 nov 2026: *«fai un censimento tra il motore del gioco e quello che oggi il replayer non valuta, dobbiamo trovare un workflow anche per le future espansioni che ci tenga allineati nei comportamenti»*.

Ogni cosa che puo' succedere in una partita, dalle istruzioni del motore e da quello che Arena scrive nei log, con quello che il replayer ne mostra: **si** (animato, si capisce guardando), **parte** (si vede l'esito ma non il gesto, o solo nel racconto), **no** (invisibile), **nonserve** (non cambia niente sul tavolo). I log: le ultime 400 partite.

## Le istruzioni del motore

si: 106  ·  parte: 9  ·  no: 0  ·  nonserve: 4

| Voce | Stato | Come lo mostra, o cosa manca | Dove |
| :- | :- | :- | :- |
| aggiungi_mana | si | il simbolo del mana vola dalla fonte nella vaschetta MANA POOL sotto le terre di chi paga, poi dalla vaschetta alla carta (15 nov 2026); la riserva che resta a galla sta nella vaschetta | Motore_Partita/effetti.py |
| airbend | si | TLA: la carta vola in esilio; se Arena la dice giocabile sta nella fila PLAYABLE (il permesso 47, non piu' il testo) | Motore_Partita/Set/TLA/meccaniche.py |
| amass | si | HOB, ammassare: la pedina Esercito nasce dalla pila e i segnalini +1/+1 colorano di blu i pallini | Motore_Partita/Set/HOB/meccaniche.py |
| attacca | si | il combattimento: tappa, frecce, duelli | Motore_Partita/effetti.py |
| attacca_con_difensore | si | il difensore che attacca si tappa e va in combattimento con la sua freccia, come ogni attaccante; il permesso in se' non ha un segno | Motore_Partita/effetti.py |
| aumenta_velocita | si | DFT: la pillola arancio SPEED N accanto al giocatore, MAX a 4 (V3) | Motore_Partita/Set/DFT/meccaniche.py |
| base | si | forza e costituzione nei pallini (blu o rossi rispetto allo stampato) | Motore_Partita/effetti.py |
| blight | si | ECL, i segnalini -1/-1: i pallini di forza e costituzione diventano rossi e la carta si accende d'oro | Motore_Partita/Set/ECL/meccaniche.py |
| cerca | si | la carta vola dal grimorio alla mano o al campo, poi i tre dorsi che si mischiano (Shuffle) | Motore_Partita/effetti.py |
| cima_o_fondo | si | la carta vola verso il grimorio e sul mazzo la pillola oro ON TOP o ON THE BOTTOM col triangolo; il racconto dice dove (15 nov 2026, dalla lista del grimorio) | Motore_Partita/effetti.py |
| contrasta | si | la freccia dentro la pila sulla magia presa di mira, poi la magia al cimitero dalla pila | Motore_Partita/effetti.py |
| copia_magia | si | la copia in pila porta la pillola COPY (isCopy dell'oggetto, 15 nov 2026) | Motore_Partita/effetti.py |
| copia_pedina | si | la pedina nasce dalla carta in pila e scorre in campo | Motore_Partita/effetti.py |
| dai_abilita_fino | si | un'abilita' data fino a fine turno: se e' una parola chiave la pillola verde (C2), se no il testo corto sulla carta (A2), finche' Arena la tiene (15 nov 2026) | Motore_Partita/effetti.py |
| dai_flashback | si | Arena scrive il permesso «puoi giocarla» (Qualification 47) anche per le carte giocabili dal cimitero: stanno nella fila PLAYABLE accanto alla mano e ci volano dal cimitero | Motore_Partita/effetti.py |
| dai_mana | si | come aggiungi_mana | Motore_Partita/effetti.py |
| dai_parole | si | le parole chiave date: pillole verdi «+Flying» sul bordo sinistro della carta (14 nov 2026, C2) | Motore_Partita/effetti.py |
| dal_cimitero_in_mano | si | la carta vola dal cimitero alla mano | Motore_Partita/effetti.py |
| dalla_mano_in_campo | si | la carta vola dalla mano al campo | Motore_Partita/effetti.py |
| danno | si | la goccia col -N su chi lo prende; nel combattimento la spada su chi lo infligge | Motore_Partita/effetti.py |
| danno_fedelta | si | la goccia sul planeswalker, la fedelta' nel pallino | Motore_Partita/effetti.py |
| danno_forza | si | la goccia su chi lo prende e la spada col numero su chi lo infligge, anche fuori dal combattimento se e' sul tavolo (15 nov 2026) | Motore_Partita/effetti.py |
| distribuisci_segnalini | si | i segnalini distribuiti: i pallini sulle carte cambiano e la carta si accende d'oro | Motore_Partita/effetti.py |
| distruggi | si | la freccia, poi la carta grigia col teschio va al cimitero | Motore_Partita/effetti.py |
| distruggi_tranne_tipo | si | come distruggi; da 3 permanenti in su il racconto dice board wipe | Motore_Partita/effetti.py |
| diventa_copia | si | la carta mostra cio' che copia con la pillola COPY · originale (CopiedObject, 15 nov 2026) | Motore_Partita/effetti.py |
| diventa_tipo | si | la carta scivola nella sua fila nuova; la terra diventata creatura ha la pillola NOW A CREATURE | Motore_Partita/effetti.py |
| earthbend | si | TLA, dominare la terra: la terra diventa creatura coi segnalini (pallini blu) e la pillola NOW A CREATURE | Motore_Partita/Set/TLA/meccaniche.py |
| earthbend_ritorna | si | TLA, la terra piegata che muore torna in campo tappata: vola dal cimitero al campo | Motore_Partita/Set/TLA/meccaniche.py |
| emblema | si | la pillola viola EMBLEM · carta sotto i conti del giocatore, in hover la carta che l'ha creato (oggetti Emblem della zona Command, 15 nov 2026) | Motore_Partita/effetti.py |
| empower_jace | si | la pedina Jace e i suoi segnalini di fedelta' (pallino blu); il potenziamento e' la carta che entra o cresce | Motore_Partita/effetti.py |
| endure | si | TDM, resistere: segnalini +1/+1 (pallini blu) o la pedina Spirito che esce dalla pila | Motore_Partita/Set/TDM/meccaniche.py |
| esilia | si | la freccia, poi la carta vola in esilio | Motore_Partita/effetti.py |
| esilia_cima | si | la carta vola dal grimorio all'esilio; se e' giocabile (impulse) sta in oro con PLAYABLE accanto alla mano | Motore_Partita/effetti.py |
| esilia_e_lancia_copie | si | le carte volano in esilio, le copie vanno in pila con COPY e in campo restano con COPY (Improvisation Capstone) | Motore_Partita/effetti.py |
| esilia_fino_non_terra | si | le carte esiliate dalla cima del grimorio volano una alla volta nell'esilio | Motore_Partita/effetti.py |
| esilia_scelta_da_te | si | come esilia | Motore_Partita/effetti.py |
| esilia_se_muore | si | la carta va in esilio invece che al cimitero | Motore_Partita/effetti.py |
| fedelta_rapida | si | la fedelta' nel pallino del planeswalker | Motore_Partita/effetti.py |
| firebending | si | TLA: il mana aggiunto vola nella vaschetta MANA POOL e ci resta finche' si spende | Motore_Partita/Set/TLA/meccaniche.py |
| gira_faccia | si | la carta a due facce si gira al suo posto: si stringe, cambia faccia, si riapre (14 nov 2026) | Motore_Partita/effetti.py |
| guadagna | si | la vita che sale: il cuore verde col «+N» accanto al cerchio e il numero che sale (14 nov 2026) | Motore_Partita/effetti.py |
| in_fondo | si | vola verso il grimorio, ON THE BOTTOM sul mazzo | Motore_Partita/effetti.py |
| in_grimorio | si | vola verso il grimorio; ON TOP, ON THE BOTTOM o «Nth from the top» nel racconto | Motore_Partita/effetti.py |
| in_mano_esiliata | si | la carta esiliata che torna in mano vola dall'esilio alla mano | Motore_Partita/effetti.py |
| lancia_esiliata | si | le carte giocabili (dall'esilio e dal cimitero) come le dice Arena, in oro con PLAYABLE accanto alla mano di chi puo' giocarle (E1, 14 nov 2026) | Motore_Partita/effetti.py |
| livello_classe | si | TMT, la pillola oro LEVEL N sulla Classe (ClassLevel) | Motore_Partita/Set/TMT/meccaniche.py |
| lotta | si | le due creature si affrontano in un duello come nel combattimento (velo, si vengono incontro, gocce e spade dai danni veri), 15 nov 2026 | Motore_Partita/effetti.py |
| macina | si | le carte volano dal grimorio al cimitero | Motore_Partita/effetti.py |
| mescola_nel_grimorio | si | la carta vola verso il grimorio, poi i tre dorsi che si mischiano (Shuffle) | Motore_Partita/effetti.py |
| mobilize | si | TDM, mobilitare: le pedine nascono tappate e in attacco, con le frecce; a fine turno si spengono al loro posto | Motore_Partita/Set/TDM/meccaniche.py |
| moltiplica_fc | si | forza e costituzione nei pallini | Motore_Partita/effetti.py |
| non_blocca | si | la pillola rossa CAN'T BLOCK (o NO ATTACK/BLOCK) col cerchio barrato sulla carta, finche' vale (Qualification 31 e 30, 15 nov 2026) | Motore_Partita/effetti.py |
| non_bloccabile | si | la pillola blu UNBLOCKABLE con la freccia sulla carta (Qualification 32; 39 «1 BLOCKER MAX») | Motore_Partita/effetti.py |
| paga_vite | si | la goccia rossa col -N accanto al cerchio della vita (la vita persa senza danno) | Motore_Partita/effetti.py |
| parola_scelta | si | il fumetto bianco con la scelta in testa alla carta (C1) | Motore_Partita/effetti.py |
| pedina | si | la pedina vera (Scryfall) scorre in campo dalla carta in pila | Motore_Partita/effetti.py |
| perde | si | la goccia col -N sulla vita | Motore_Partita/effetti.py |
| permesso_gioca | si | le carte giocabili (dall'esilio e dal cimitero) come le dice Arena, in oro con PLAYABLE accanto alla mano di chi puo' giocarle (E1, 14 nov 2026) | Motore_Partita/effetti.py |
| permesso_questa | si | le carte giocabili (dall'esilio e dal cimitero) come le dice Arena, in oro con PLAYABLE accanto alla mano di chi puo' giocarle (E1, 14 nov 2026) | Motore_Partita/effetti.py |
| pesca | si | la carta vola dal grimorio alla mano (l'avversario: un dorso nel suo ventaglio) | Motore_Partita/effetti.py |
| pompa | si | forza e costituzione nei pallini blu | Motore_Partita/effetti.py |
| prendi_controllo | si | la carta che cambia lato scorre dal campo di prima all'altro (14 nov 2026) | Motore_Partita/effetti.py |
| prepara | si | la pillola viola PREPARED sulla carta (14 nov 2026, D3) | Motore_Partita/effetti.py |
| prolifera | si | i segnalini nuovi accendono la carta d'oro | Motore_Partita/effetti.py |
| prossima_incontrastabile | si | la pillola UNCOUNTERABLE sulla magia in pila (Qualification 10) | Motore_Partita/effetti.py |
| raddoppia_segnalini | si | i segnalini raddoppiati: i pallini di forza e costituzione cambiano numero e colore, la carta si accende d'oro | Motore_Partita/effetti.py |
| rianima_tutte | si | le creature tornano dal cimitero in campo, una alla volta | Motore_Partita/effetti.py |
| riflessa | si | l'abilita' riflessa va in pila quando scatta, con la freccia azzurra da chi la fa scattare se e' un'altra carta | Motore_Partita/effetti.py |
| rimbalza | si | la freccia, poi la carta vola in mano | Motore_Partita/effetti.py |
| rimetti_esiliate | si | le carte volano dall'esilio | Motore_Partita/effetti.py |
| ritardata | si | l'abilita' ritardata va in pila quando scatta, col nome della carta (i grpId finti 2 e 5 risalgono alla carta) | Motore_Partita/effetti.py |
| ritorna | si | la carta vola al suo posto | Motore_Partita/effetti.py |
| ritorna_esiliata | si | la carta vola dall'esilio | Motore_Partita/effetti.py |
| ritorna_esiliata_tua | si | come ritorna_esiliata | Motore_Partita/effetti.py |
| ritorna_tutte | si | le carte volano, una alla volta | Motore_Partita/effetti.py |
| rivela_fino | si | le carte rivelate escono dal grimorio, si mostrano grandi al centro con REVEALED e tornano (RevealedCardCreated, l'azione «rivela») | Motore_Partita/effetti.py |
| ruota_scelta | si | il fumetto bianco con la scelta in testa alla carta (C1) | Motore_Partita/effetti.py |
| sacrifica | si | la carta grigia col teschio va al cimitero (la pedina si spegne al suo posto) | Motore_Partita/effetti.py |
| sacrifica_oggetti | si | i permanenti sacrificati diventano grigi al loro posto e volano al cimitero, uno alla volta | Motore_Partita/effetti.py |
| sacrifica_questo | si | come sacrifica | Motore_Partita/effetti.py |
| sacrifica_ricordate | si | TDM, il sacrificio delle carte ricordate: volano al cimitero una alla volta | Motore_Partita/Set/TDM/meccaniche.py |
| sacrifica_ritardata | si | come sacrifica_oggetti, nel passo in cui avviene | Motore_Partita/effetti.py |
| scambia | si | lo scambio: ognuna scorre nel campo dell'altro, una alla volta (14 nov 2026) | Motore_Partita/effetti.py |
| scarta | si | la carta vola dalla mano al cimitero (la sua: un dorso) | Motore_Partita/effetti.py |
| scarta_poi_pesca | si | lo scarto vola dalla mano al cimitero, poi la pescata dal grimorio alla mano | Motore_Partita/effetti.py |
| scarta_salvo | si | lo scarto vola dalla mano al cimitero | Motore_Partita/effetti.py |
| scarta_scelta_da_te | si | come scarta | Motore_Partita/effetti.py |
| scegli_tipo | si | il fumetto bianco col tipo scelto in testa alla carta (C1) | Motore_Partita/effetti.py |
| scopri | si | le carte esiliate dalla cima volano nell'esilio e quella lanciata va in pila con FREE (CastingTimeOption, costo alternativo 149) | Motore_Partita/effetti.py |
| scry | si | le carte guardate escono dal mazzo a ventaglio nella meta' del tavolo di chi guarda, ognuna con TOP o BOTTOM, poi una alla volta tornano (S1, 14 nov 2026); le sue di dorso | Motore_Partita/effetti.py |
| segnalini | si | i segnalini in testa alla carta, la carta si accende d'oro | Motore_Partita/effetti.py |
| segnalini_della_fonte | si | come segnalini | Motore_Partita/effetti.py |
| sella | si | DFT: le creature che sellano si tappano, SADDLED sulla cavalcatura e SADDLING su chi la sella | Motore_Partita/Set/DFT/meccaniche.py |
| sprepara | si | la pillola PREPARED se ne va quando la copia e' lanciata | Motore_Partita/effetti.py |
| stappa | si | la carta si gira, una alla volta | Motore_Partita/effetti.py |
| station_carica | si | EOE e TRK, station: la creatura si tappa e i segnalini di carica compaiono in testa alla carta, viola col nome | Motore_Partita/meccaniche_comuni/station.py |
| stordisci | si | i segnalini di stordimento in testa alla carta | Motore_Partita/effetti.py |
| surveil | si | le tue: il ventaglio con TOP e GRAVEYARD (come lo scry); quelle dell'avversario (15 nov 2026, MultistepEffect SubCategory 11): lo stesso ventaglio, le tenute sopra coperte, quante dal testo dell'abilita' | Motore_Partita/effetti.py |
| tappa | si | la carta si gira, una alla volta | Motore_Partita/effetti.py |
| togli_abilita | si | la pillola rossa NO ABILITIES sulla carta (RemoveAbility «all» data da un'altra carta) | Motore_Partita/effetti.py |
| togli_segnalini | si | i segnalini spariscono dalla carta | Motore_Partita/effetti.py |
| togli_segnalini_scelti | si | come togli_segnalini | Motore_Partita/effetti.py |
| trama | si | la carta va in esilio con la pillola PLOTTED e sta nella fila PLAYABLE; lanciata, FROM PLOT o FREE sulla carta in pila | Motore_Partita/effetti.py |
| vinci | si | la schermata finale | Motore_Partita/effetti.py |
| warp_esilia | si | EOE, warp: la carta va in esilio a fine turno e sta nella fila FROM EXILE col bordo viola | Motore_Partita/Set/EOE/meccaniche.py |
| contrasta_salvo | parte | come contrasta (la freccia viola dentro la pila, TARGET, RESOLVES ON THE STACK); la scelta di pagare e' una richiesta all'altro giocatore che il log non scrive | Motore_Partita/effetti.py |
| dal_fuori | parte | la carta compare; da dove viene no: nelle partite registrate (al 15 nov 2026) nessuna carta e' mai arrivata da fuori partita (sideboard o Command) | Motore_Partita/effetti.py |
| esilia_e_cerca | parte | le carte volano; la ricerca no; le carte guardate non si vedono perche' Arena non le manda con una richiesta che dica quali sono (letto il 15 nov 2026 sulle ultime 150 partite: solo GroupReq di surveil, scry e mulligan) | Motore_Partita/effetti.py |
| esilia_finche | parte | la carta va in esilio, e quando Arena la mette sotto la fonte (DisplayCardUnderCard) sta dietro di lei; il ritorno quando la fonte lascia il campo e' un volo normale | Motore_Partita/effetti.py |
| esilia_tranne_fondo | parte | le carte volano; le carte guardate non si vedono perche' Arena non le manda con una richiesta che dica quali sono (letto il 15 nov 2026 sulle ultime 150 partite: solo GroupReq di surveil, scry e mulligan) | Motore_Partita/effetti.py |
| guarda_cima_prendi | parte | la carta presa vola in mano; le carte guardate no; le carte guardate non si vedono perche' Arena non le manda con una richiesta che dica quali sono (letto il 15 nov 2026 sulle ultime 150 partite: solo GroupReq di surveil, scry e mulligan) | Motore_Partita/effetti.py |
| prendi_tra_macinate | parte | le carte volano; le carte guardate non si vedono perche' Arena non le manda con una richiesta che dica quali sono (letto il 15 nov 2026 sulle ultime 150 partite: solo GroupReq di surveil, scry e mulligan) | Motore_Partita/effetti.py |
| recruit | parte | HOB, reclutare: la carta presa dal grimorio arriva in mano col volo; le carte guardate e rimesse sotto non si vedono; le carte guardate non si vedono perche' Arena non le manda con una richiesta che dica quali sono (letto il 15 nov 2026 sulle ultime 150 partite: solo GroupReq di surveil, scry e mulligan) | Motore_Partita/Set/HOB/meccaniche.py |
| riprendi_sorvegliata | parte | le carte volano; le carte guardate non si vedono perche' Arena non le manda con una richiesta che dica quali sono (letto il 15 nov 2026 sulle ultime 150 partite: solo GroupReq di surveil, scry e mulligan) | Motore_Partita/effetti.py |
| mana_in_piu | nonserve | come aggiungi_mana | Motore_Partita/effetti.py |
| paga | nonserve | un costo: si vedono le terre che si tappano | Motore_Partita/effetti.py |
| senza_leggenda | nonserve | una regola | Motore_Partita/effetti.py |
| terra_in_piu | nonserve | un permesso | Motore_Partita/effetti.py |

## Le annotazioni di Arena

si: 53  ·  parte: 0  ·  no: 0  ·  nonserve: 30

| Voce | Stato | Come lo mostra, o cosa manca | Volte nei log |
| :- | :- | :- | -: |
| TappedUntappedPermanent | si | la carta si gira | 39279 |
| ZoneTransfer | si | i voli fra le zone (vedi le categorie) | 32439 |
| UserActionTaken | si | le abilita' attivate vanno in pila col nome della carta; quelle di mana fanno volare il simbolo nella vaschetta MANA POOL; in Leak Finder anche i filtri | 30010 |
| AbilityInstanceCreated | si | l'abilita' va in pila (anche quella che si risolve nello stesso messaggio: un passo suo) | 27166 |
| ManaPaid | si | da ogni terra che paga esce il suo simbolo di mana e vola nella vaschetta MANA POOL di chi paga; poi, uno alla volta, i simboli vanno sulla carta (M1, 14-15 nov 2026) | 17560 |
| ResolutionComplete | si | la magia lascia la pila | 15710 |
| ResolutionStart | si | l'effetto della magia (fatti) | 15634 |
| NewTurnStarted | si | il turno nuovo, l'ombra che passa | 6198 |
| TriggeringObject | si | la freccia azzurra dalla carta che fa scattare l'innesco all'abilita' in pila (la fonte stessa no; chi e' gia' uscito dal campo no), 15 nov 2026 | 5345 |
| DamageDealt | si | goccia su chi riceve, spada su chi infligge | 5207 |
| LayeredEffectCreated | si | l'effetto si vede nei pallini di forza e costituzione (blu se piu' alti, rossi se piu' bassi) e nelle pillole delle abilita' date | 4892 |
| Counter | si | i segnalini (persistenti) | 4780 |
| ModifiedLife | si | il numero della vita; la perdita senza danno con la goccia | 4217 |
| CounterAdded | si | il segnalino nuovo, la carta d'oro | 4119 |
| AbilityWordActive | si | l'anello nell'angolo della carta col conto sulla soglia (5/7), verde quando e' attiva, e il nome sotto (W2, 14 nov 2026) | 3877 |
| TargetSpec | si | le frecce viola verso i bersagli | 3635 |
| ModifiedPower | si | il pallino della forza | 3608 |
| PowerToughnessModCreated | si | i pallini di forza e costituzione | 3506 |
| LayeredEffectDestroyed | si | i pallini tornano come stampati | 3367 |
| ModifiedToughness | si | il pallino della costituzione | 3188 |
| LayeredEffect | si | l'effetto si vede nei pallini di forza e costituzione (blu se piu' alti, rossi se piu' bassi) e nelle pillole delle abilita' date | 2825 |
| TemporaryPermanent | si | la clessidra arancio in alto a sinistra: se ne va a fine turno (14 nov 2026, B1) | 2664 |
| TokenCreated | si | la pedina scorre in campo | 2040 |
| Qualification | si | 47 la fila PLAYABLE; i divieti e i permessi sulla carta, pillole rosse e blu: NO UNTAP, CAN'T BLOCK, NO ATTACK/BLOCK, UNBLOCKABLE, 1 BLOCKER MAX, CAN ATTACK, ABILITIES OFF (15 nov 2026); i costi ridotti e gli effetti su tutto il tavolo no | 1048 |
| AddAbility | si | le parole chiave date come pillole verdi (C2); le altre abilita' date col loro testo corto sulla carta (A2, 14 nov 2026) | 1009 |
| RevealedCardCreated | si | la carta rivelata esce dal grimorio del suo proprietario, si mostra grande al centro con REVEALED, torna (14 nov 2026) | 948 |
| TokenDeleted | si | la pedina si spegne | 942 |
| MultistepEffectComplete | si | SubCategory 11: la fine del surveil dell'avversario, col ventaglio (15 nov 2026); gli altri interni | 860 |
| MultistepEffectStarted | si | SubCategory 11: il surveil dell'avversario, che Arena non ti chiede (15 nov 2026); gli altri interni | 856 |
| InstanceRevealedToOpponent | si | la tua carta della mano che l'avversario ha visto: bordo azzurro e la pillola con l'occhio SHOWN (15 nov 2026); Arena la scrive solo per le tue carte | 698 |
| DisplayCardUnderCard | si | le carte esiliate sotto di lei, sfalsate dietro la carta (14 nov 2026, A1) | 644 |
| CounterRemoved | si | il segnalino tolto (la fedelta' dei poteri) | 621 |
| CastingTimeOption | si | sulla carta in pila le pillole oro KICKED, X = N, EXTRA COST, FREE, FLASHBACK, FROM PLOT, PAID WITH LIFE (il costo alternativo dal testo della sua abilita'; senza testo niente scritta), 15 nov 2026 | 479 |
| Designation | si | PREPARED, DOOR UNLOCKED, PLOTTED, SOLVED, SUSPECTED, HARNESSED sulla carta (pillola viola) e la velocita' SPEED N accanto al giocatore; perso, la pillola se ne va; il tipo 23 sulle terre base Arena non dice cos'e' | 373 |
| Shuffle | si | il grimorio si rimescola: tre dorsi che si mischiano (14 nov 2026) | 370 |
| AbilityExhausted | si | la pillola grigia EXHAUSTED (exhaust) o USED THIS TURN (una volta per turno) sulla carta | 306 |
| Scry | si | il ventaglio S1 con TOP e BOTTOM (14 nov 2026) | 266 |
| GainDesignation | si | PREPARED, DOOR UNLOCKED, PLOTTED, SOLVED, SUSPECTED, HARNESSED sulla carta (pillola viola) e la velocita' SPEED N accanto al giocatore; perso, la pillola se ne va; il tipo 23 sulle terre base Arena non dice cos'e' | 263 |
| Attachment | si | l'aura e l'equipaggiamento stanno dietro la carta che li porta, sfalsati in alto col nome a vista; attaccati nel passo volano su di lei (15 nov 2026) | 242 |
| ChoiceResult | si | la scelta (tipo, colore, nome, modalita') in un fumetto bianco in testa alla carta, finche' resta in campo (C1, 14 nov 2026) | 232 |
| ModifiedType | si | la carta cambia fila se diventa creatura; la terra diventata creatura ha la pillola NOW A CREATURE | 229 |
| AttachmentCreated | si | il volo dell'aura sulla carta che la porta, e nel racconto «attached to» (15 nov 2026) | 208 |
| FaceDown | si | in campo a faccia in giu' la pillola grigia FACE DOWN (isFacedown); il proprietario ne vede il nome, l'altro un dorso | 167 |
| RemoveAbility | si | la pillola rossa NO ABILITIES sulla carta; la carta che cambia tipo da se' (Multiversal Passage) no | 135 |
| LoseDesignation | si | PREPARED, DOOR UNLOCKED, PLOTTED, SOLVED, SUSPECTED, HARNESSED sulla carta (pillola viola) e la velocita' SPEED N accanto al giocatore; perso, la pillola se ne va; il tipo 23 sulle terre base Arena non dice cos'e' | 125 |
| LossOfGame | si | la schermata finale | 111 |
| CardRevealed | si | la carta mostrata esce grande al centro con REVEALED come le rivelate, una volta sola anche quando Arena crea la copia rivelata | 70 |
| ModifiedColor | si | la pillola NOW WHITE · BLACK (il colore nuovo) sulla carta, 15 nov 2026 | 27 |
| ClassLevel | si | la pillola oro LEVEL N sulla Classe | 24 |
| ControllerChanged | si | la carta che cambia lato scorre da un campo all'altro (14 nov 2026) | 11 |
| CopiedObject | si | la carta in campo mostra cio' che copia (copyFromGrpid) con la pillola azzurra COPY · originale; diventandolo si gira come una carta a due facce | 9 |
| SaddledThisTurn | si | SADDLED sulla cavalcatura, SADDLING su chi l'ha sellata (pillole di stato) | 4 |
| CrewedThisTurn | si | CREWED sul veicolo, CREWING su chi l'ha equipaggiato (pillole di stato) | 3 |
| PhaseOrStepModified | nonserve | il passo: la striscia dei turni | 69433 |
| EnteredZoneThisTurn | nonserve | contabilita' di Arena | 33856 |
| ObjectIdChanged | nonserve | il replayer segue gli id | 27959 |
| AbilityInstanceDeleted | nonserve | l'abilita' lascia la pila | 27782 |
| ColorProduction | nonserve | il mana | 6996 |
| PlayerSelectingTargets | nonserve | la scelta in corso | 3610 |
| PlayerSubmittedTargets | nonserve | la scelta fatta: le frecce | 3535 |
| SyntheticEvent | nonserve | evento interno di Arena | 2036 |
| LoyaltyActivationsRemaining | nonserve | contabilita' | 1078 |
| ObjectsSelected | nonserve | quasi sempre senza le carte (affectedIds 0, solo il giocatore che sceglie: 138 su 141 nelle ultime 150 partite); quello che si sceglie si vede quando si sposta | 778 |
| RevealedCardDeleted | nonserve | la carta rivelata sparisce | 736 |
| DamagedThisTurn | nonserve | contabilita' | 536 |
| ShouldntPlay | nonserve | un suggerimento di Arena | 469 |
| LinkInfo | nonserve | interno | 302 |
| DelayedTriggerAffectees | nonserve | interno | 256 |
| ReplacementEffect | nonserve | si vede l'esito | 243 |
| PredictedDirectDamage | nonserve | una previsione di Arena | 155 |
| SuppressedPowerAndToughness | nonserve | interno | 148 |
| DisqualifiedEffect | nonserve | interno | 103 |
| ModifiedName | nonserve | nei log sono le Room: il nome della porta aperta, che ha gia' la pillola DOOR UNLOCKED | 72 |
| ModifiedCost | nonserve | si vedono le terre che pagano | 71 |
| TextChange | nonserve | come ModifiedName: la porta aperta di una Room (DOOR UNLOCKED) | 71 |
| MiscContinuousEffect | nonserve | effetti su tutta la partita (fasi in piu', carte massime in mano), non di una carta | 31 |
| ReplacementEffectApplied | nonserve | si vede l'esito | 20 |
| DynamicAbility | nonserve | interno | 15 |
| ManaDetails | nonserve | il mana | 13 |
| ReferencedObjects | nonserve | interno | 6 |
| GroupedIds | nonserve | interno | 4 |
| UseOrCostsManaCost | nonserve | interno | 2 |
| ChoosingAttachments | nonserve | la scelta in corso | 1 |

## Le categorie degli spostamenti di zona

si: 25  ·  parte: 0  ·  no: 0  ·  nonserve: 1

| Voce | Stato | Come lo mostra, o cosa manca | Volte nei log |
| :- | :- | :- | -: |
| Draw | si | pescata | 7420 |
| CastSpell | si | dalla mano alla pila | 6673 |
| Resolve | si | dalla pila al suo posto | 6246 |
| PlayLand | si | dalla mano al campo | 4705 |
| Exile | si | in esilio | 1340 |
| SBA_Damage | si | grigia col teschio, poi al cimitero | 1328 |
| Return | si | torna | 991 |
| Put | si | messa in campo | 822 |
| Discard | si | scartata | 614 |
| Sacrifice | si | sacrificata | 550 |
| Destroy | si | distrutta | 515 |
| Mill | si | macinata | 502 |
| SBA_ZeroLoyalty | si | il planeswalker senza fedelta' al cimitero | 199 |
| Surveil | si | dal grimorio al cimitero | 194 |
| SBA_ZeroToughness | si | morta | 121 |
| SBA_UnattachedAura | si | l'aura cade | 61 |
| Countered | si | dalla pila al cimitero, con la freccia della contromagia | 55 |
| SBA_Deathtouch | si | morta | 26 |
| SBA_LegendRule | si | al cimitero | 13 |
| Separate | si | le carte divise in mucchi volano dal grimorio alla mano o al cimitero; il racconto dice «put into hand from a pile» o «into the graveyard from a pile» (15 nov 2026) | 13 |
| Warp | si | in esilio (warp), poi FROM EXILE | 12 |
| ManifestLike | si | in campo a faccia in giu' con la pillola FACE DOWN | 8 |
| Copy | si | la copia compare con la pillola COPY | 2 |
| SBA_IllegalAttachment | si | l'aura o l'equipaggiamento che cade parte da sotto la carta che lo portava e va al cimitero (o resta in campo, l'equipaggiamento) | 2 |
| Bounce | si | in mano | 0 |
| nil | nonserve | lo spostamento si vede; Arena non scrive il motivo | 27 |

## Cosa non si vede ancora, dal piu' frequente nei log


## Le istruzioni del motore che il replayer non mostra


## Le parole chiave dei set (284)

Ogni parola chiave finisce in una o piu' istruzioni del motore: quello che il replayer mostra lo dicono le istruzioni. Una parola chiave nuova (un set nuovo) si guarda: se porta un'istruzione nuova, il censimento la segnala fra le istruzioni.

Nessuna parola chiave nuova.

## Il workflow per i set nuovi

1. Il motore impara il set (`py -I -X utf8 Motore_Partita/carte_set.py --costruisci`, le meccaniche nel posto privato del set).
2. `py -I -X utf8 Companion/Strumenti/censimento_replayer.py`: esce rosso con le istruzioni, le annotazioni, le categorie e le parole chiave nuove. Per ognuna si decide come la mostra il replayer (o che non serve) e si scrive la riga in `censimento_replayer.json`; le parole chiave guardate entrano con `--accetta-parole`. Una voce «no» che conta si porta a Autore: si decide insieme come mostrarla (la regola del bambino sordo: si capisce guardando, le scritte aiutano).
3. Le prime partite del set: `py -I -X utf8 Companion/Strumenti/caccia_glitch.py <id>` e le foto del replayer; ogni glitch nel registro `GLITCH_REPLAYER.md` col suo controllo.
4. Il censimento verde e la caccia verde prima del commit.
