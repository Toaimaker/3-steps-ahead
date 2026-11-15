# Il censimento del replayer

Generato da `py -I -X utf8 Companion/Strumenti/censimento_replayer.py`. Non si scrive a mano: si scrive la tabella `censimento_replayer.json`.

Autore, 14 nov 2026: *«fai un censimento tra il motore del gioco e quello che oggi il replayer non valuta, dobbiamo trovare un workflow anche per le future espansioni che ci tenga allineati nei comportamenti»*.

Ogni cosa che puo' succedere in una partita, dalle istruzioni del motore e da quello che Arena scrive nei log, con quello che il replayer ne mostra: **si** (animato, si capisce guardando), **parte** (si vede l'esito ma non il gesto, o solo nel racconto), **no** (invisibile), **nonserve** (non cambia niente sul tavolo). I log: le ultime 400 partite.

## Le istruzioni del motore

si: 76  ·  parte: 29  ·  no: 9  ·  nonserve: 4

| Voce | Stato | Come lo mostra, o cosa manca | Dove |
| :- | :- | :- | :- |
| aggiungi_mana | si | il simbolo del mana vola dalla fonte nella vaschetta MANA POOL sotto le terre di chi paga, poi dalla vaschetta alla carta (15 nov 2026); la riserva che resta a galla sta nella vaschetta | Motore_Partita/effetti.py |
| amass | si | HOB, ammassare: la pedina Esercito nasce dalla pila e i segnalini +1/+1 colorano di blu i pallini | Motore_Partita/Set/HOB/meccaniche.py |
| attacca | si | il combattimento: tappa, frecce, duelli | Motore_Partita/effetti.py |
| aumenta_velocita | si | DFT: la pillola arancio SPEED N accanto al giocatore, MAX a 4 (V3) | Motore_Partita/Set/DFT/meccaniche.py |
| base | si | forza e costituzione nei pallini (blu o rossi rispetto allo stampato) | Motore_Partita/effetti.py |
| blight | si | ECL, i segnalini -1/-1: i pallini di forza e costituzione diventano rossi e la carta si accende d'oro | Motore_Partita/Set/ECL/meccaniche.py |
| contrasta | si | la freccia dentro la pila sulla magia presa di mira, poi la magia al cimitero dalla pila | Motore_Partita/effetti.py |
| copia_pedina | si | la pedina nasce dalla carta in pila e scorre in campo | Motore_Partita/effetti.py |
| dai_abilita_fino | si | un'abilita' data fino a fine turno: se e' una parola chiave la pillola verde (C2), se no il testo corto sulla carta (A2), finche' Arena la tiene (15 nov 2026) | Motore_Partita/effetti.py |
| dai_mana | si | come aggiungi_mana | Motore_Partita/effetti.py |
| dai_parole | si | le parole chiave date: pillole verdi «+Flying» sul bordo sinistro della carta (14 nov 2026, C2) | Motore_Partita/effetti.py |
| dal_cimitero_in_mano | si | la carta vola dal cimitero alla mano | Motore_Partita/effetti.py |
| dalla_mano_in_campo | si | la carta vola dalla mano al campo | Motore_Partita/effetti.py |
| danno | si | la goccia col -N su chi lo prende; nel combattimento la spada su chi lo infligge | Motore_Partita/effetti.py |
| danno_fedelta | si | la goccia sul planeswalker, la fedelta' nel pallino | Motore_Partita/effetti.py |
| distribuisci_segnalini | si | i segnalini distribuiti: i pallini sulle carte cambiano e la carta si accende d'oro | Motore_Partita/effetti.py |
| distruggi | si | la freccia, poi la carta grigia col teschio va al cimitero | Motore_Partita/effetti.py |
| distruggi_tranne_tipo | si | come distruggi; da 3 permanenti in su il racconto dice board wipe | Motore_Partita/effetti.py |
| earthbend_ritorna | si | TLA, la terra piegata che muore torna in campo tappata: vola dal cimitero al campo | Motore_Partita/Set/TLA/meccaniche.py |
| endure | si | TDM, resistere: segnalini +1/+1 (pallini blu) o la pedina Spirito che esce dalla pila | Motore_Partita/Set/TDM/meccaniche.py |
| esilia | si | la freccia, poi la carta vola in esilio | Motore_Partita/effetti.py |
| esilia_cima | si | la carta vola dal grimorio all'esilio; se e' giocabile (impulse) sta in oro con PLAYABLE accanto alla mano | Motore_Partita/effetti.py |
| esilia_fino_non_terra | si | le carte esiliate dalla cima del grimorio volano una alla volta nell'esilio | Motore_Partita/effetti.py |
| esilia_scelta_da_te | si | come esilia | Motore_Partita/effetti.py |
| esilia_se_muore | si | la carta va in esilio invece che al cimitero | Motore_Partita/effetti.py |
| fedelta_rapida | si | la fedelta' nel pallino del planeswalker | Motore_Partita/effetti.py |
| gira_faccia | si | la carta a due facce si gira al suo posto: si stringe, cambia faccia, si riapre (14 nov 2026) | Motore_Partita/effetti.py |
| guadagna | si | la vita che sale: il cuore verde col «+N» accanto al cerchio e il numero che sale (14 nov 2026) | Motore_Partita/effetti.py |
| in_mano_esiliata | si | la carta esiliata che torna in mano vola dall'esilio alla mano | Motore_Partita/effetti.py |
| lancia_esiliata | si | le carte giocabili (dall'esilio e dal cimitero) come le dice Arena, in oro con PLAYABLE accanto alla mano di chi puo' giocarle (E1, 14 nov 2026) | Motore_Partita/effetti.py |
| macina | si | le carte volano dal grimorio al cimitero | Motore_Partita/effetti.py |
| mobilize | si | TDM, mobilitare: le pedine nascono tappate e in attacco, con le frecce; a fine turno si spengono al loro posto | Motore_Partita/Set/TDM/meccaniche.py |
| moltiplica_fc | si | forza e costituzione nei pallini | Motore_Partita/effetti.py |
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
| raddoppia_segnalini | si | i segnalini raddoppiati: i pallini di forza e costituzione cambiano numero e colore, la carta si accende d'oro | Motore_Partita/effetti.py |
| rianima_tutte | si | le creature tornano dal cimitero in campo, una alla volta | Motore_Partita/effetti.py |
| rimbalza | si | la freccia, poi la carta vola in mano | Motore_Partita/effetti.py |
| rimetti_esiliate | si | le carte volano dall'esilio | Motore_Partita/effetti.py |
| ritorna | si | la carta vola al suo posto | Motore_Partita/effetti.py |
| ritorna_esiliata | si | la carta vola dall'esilio | Motore_Partita/effetti.py |
| ritorna_esiliata_tua | si | come ritorna_esiliata | Motore_Partita/effetti.py |
| ritorna_tutte | si | le carte volano, una alla volta | Motore_Partita/effetti.py |
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
| scry | si | le carte guardate escono dal mazzo a ventaglio nella meta' del tavolo di chi guarda, ognuna con TOP o BOTTOM, poi una alla volta tornano (S1, 14 nov 2026); le sue di dorso | Motore_Partita/effetti.py |
| segnalini | si | i segnalini in testa alla carta, la carta si accende d'oro | Motore_Partita/effetti.py |
| segnalini_della_fonte | si | come segnalini | Motore_Partita/effetti.py |
| sprepara | si | la pillola PREPARED se ne va quando la copia e' lanciata | Motore_Partita/effetti.py |
| stappa | si | la carta si gira, una alla volta | Motore_Partita/effetti.py |
| station_carica | si | EOE e TRK, station: la creatura si tappa e i segnalini di carica compaiono in testa alla carta, viola col nome | Motore_Partita/meccaniche_comuni/station.py |
| stordisci | si | i segnalini di stordimento in testa alla carta | Motore_Partita/effetti.py |
| surveil | si | le tue: il ventaglio con TOP e GRAVEYARD (come lo scry); quelle dell'avversario (15 nov 2026, MultistepEffect SubCategory 11): lo stesso ventaglio, le tenute sopra coperte, quante dal testo dell'abilita' | Motore_Partita/effetti.py |
| tappa | si | la carta si gira, una alla volta | Motore_Partita/effetti.py |
| togli_segnalini | si | i segnalini spariscono dalla carta | Motore_Partita/effetti.py |
| togli_segnalini_scelti | si | come togli_segnalini | Motore_Partita/effetti.py |
| vinci | si | la schermata finale | Motore_Partita/effetti.py |
| warp_esilia | si | EOE, warp: la carta va in esilio a fine turno e sta nella fila FROM EXILE col bordo viola | Motore_Partita/Set/EOE/meccaniche.py |
| airbend | parte | TLA, dominare l'aria: la carta vola in esilio; la fila FROM EXILE la prende solo se il testo lo dice (grado C), il costo {2} non si vede | Motore_Partita/Set/TLA/meccaniche.py |
| cerca | parte | la carta vola dal grimorio alla mano o al campo; il grimorio che si rimescola non si vede | Motore_Partita/effetti.py |
| cima_o_fondo | parte | la carta vola verso il grimorio; sopra o sotto non si distingue | Motore_Partita/effetti.py |
| contrasta_salvo | parte | come contrasta; la scelta di pagare non si vede | Motore_Partita/effetti.py |
| copia_magia | parte | la copia compare in pila; il legame con l'originale no | Motore_Partita/effetti.py |
| dal_fuori | parte | la carta compare; da dove viene (fuori dalla partita) no | Motore_Partita/effetti.py |
| danno_forza | parte | la goccia su chi lo prende; la spada di chi infligge solo nei duelli | Motore_Partita/effetti.py |
| diventa_tipo | parte | la carta scivola nella sua fila nuova (un veicolo con equipaggio, una terra che diventa creatura); il perche' no | Motore_Partita/effetti.py |
| earthbend | parte | TLA, dominare la terra: la terra diventa creatura coi segnalini (pallini blu), ma resta nella fila delle terre senza un gesto che lo dica | Motore_Partita/Set/TLA/meccaniche.py |
| empower_jace | parte | la pedina Jace e i suoi segnalini; il potenziamento in se' no | Motore_Partita/effetti.py |
| esilia_e_cerca | parte | le carte volano; la ricerca no | Motore_Partita/effetti.py |
| esilia_e_lancia_copie | parte | le carte volano e le copie vanno in pila; il legame no | Motore_Partita/effetti.py |
| esilia_finche | parte | la carta va in esilio; che torni quando la fonte lascia il campo no | Motore_Partita/effetti.py |
| esilia_tranne_fondo | parte | le carte volano | Motore_Partita/effetti.py |
| firebending | parte | TLA, dominare il fuoco: il mana aggiunto sta nella vaschetta MANA POOL quando Arena lo scrive nella riserva (15 nov 2026; non visto su una partita TLA) | Motore_Partita/Set/TLA/meccaniche.py |
| guarda_cima_prendi | parte | la carta presa vola in mano; le carte guardate no | Motore_Partita/effetti.py |
| in_fondo | parte | la carta vola verso il grimorio | Motore_Partita/effetti.py |
| in_grimorio | parte | la carta vola verso il grimorio | Motore_Partita/effetti.py |
| lotta | parte | le gocce su tutte e due; il duello animato solo nel combattimento | Motore_Partita/effetti.py |
| mescola_nel_grimorio | parte | la carta vola verso il grimorio; il rimescolare no | Motore_Partita/effetti.py |
| paga_vite | parte | la vita scende; il pagare non ha un segno suo | Motore_Partita/effetti.py |
| prendi_tra_macinate | parte | le carte volano | Motore_Partita/effetti.py |
| recruit | parte | HOB, reclutare: la carta presa dal grimorio arriva in mano col volo; le carte guardate e rimesse sotto non si vedono | Motore_Partita/Set/HOB/meccaniche.py |
| riflessa | parte | l'abilita' riflessa va in pila se il log la scrive | Motore_Partita/effetti.py |
| riprendi_sorvegliata | parte | le carte volano | Motore_Partita/effetti.py |
| ritardata | parte | l'abilita' ritardata va in pila quando scatta | Motore_Partita/effetti.py |
| scopri | parte | le carte esiliate dalla cima volano nell'esilio e quella lanciata va in pila; che il lancio sia gratis lo dice solo il racconto | Motore_Partita/effetti.py |
| sella | parte | DFT, sellare: le creature che sellano si tappano (girano una alla volta); il legame con la cavalcatura non si vede | Motore_Partita/Set/DFT/meccaniche.py |
| trama | parte | la carta va in esilio e sta nella fila FROM EXILE | Motore_Partita/effetti.py |
| dai_flashback | no | niente segna che una carta del cimitero si puo' rilanciare | Motore_Partita/effetti.py |
| diventa_copia | no | la carta cambia immagine di colpo | Motore_Partita/effetti.py |
| emblema | no | gli emblemi non sono sul tavolo | Motore_Partita/effetti.py |
| livello_classe | no | TMT, il livello della classe (ClassLevel): il replayer non mostra il livello raggiunto | Motore_Partita/Set/TMT/meccaniche.py |
| non_blocca | no | il divieto di bloccare non si vede | Motore_Partita/effetti.py |
| non_bloccabile | no | il non poter essere bloccata non si vede | Motore_Partita/effetti.py |
| prossima_incontrastabile | no | non si vede | Motore_Partita/effetti.py |
| rivela_fino | no | le carte rivelate non si vedono (il log le scrive: RevealedCardCreated) | Motore_Partita/effetti.py |
| togli_abilita | no | le abilita' tolte non si vedono | Motore_Partita/effetti.py |
| mana_in_piu | nonserve | come aggiungi_mana | Motore_Partita/effetti.py |
| paga | nonserve | un costo: si vedono le terre che si tappano | Motore_Partita/effetti.py |
| senza_leggenda | nonserve | una regola | Motore_Partita/effetti.py |
| terra_in_piu | nonserve | un permesso | Motore_Partita/effetti.py |

## Le annotazioni di Arena

si: 30  ·  parte: 17  ·  no: 10  ·  nonserve: 26

| Voce | Stato | Come lo mostra, o cosa manca | Volte nei log |
| :- | :- | :- | -: |
| TappedUntappedPermanent | si | la carta si gira | 39279 |
| ZoneTransfer | si | i voli fra le zone (vedi le categorie) | 32439 |
| AbilityInstanceCreated | si | l'abilita' va in pila (anche quella che si risolve nello stesso messaggio: un passo suo) | 27166 |
| ManaPaid | si | da ogni terra che paga esce il suo simbolo di mana e vola nella vaschetta MANA POOL di chi paga; poi, uno alla volta, i simboli vanno sulla carta (M1, 14-15 nov 2026) | 17560 |
| ResolutionComplete | si | la magia lascia la pila | 15710 |
| ResolutionStart | si | l'effetto della magia (fatti) | 15634 |
| NewTurnStarted | si | il turno nuovo, l'ombra che passa | 6198 |
| DamageDealt | si | goccia su chi riceve, spada su chi infligge | 5207 |
| Counter | si | i segnalini (persistenti) | 4780 |
| ModifiedLife | si | il numero della vita; la perdita senza danno con la goccia | 4217 |
| CounterAdded | si | il segnalino nuovo, la carta d'oro | 4119 |
| AbilityWordActive | si | l'anello nell'angolo della carta col conto sulla soglia (5/7), verde quando e' attiva, e il nome sotto (W2, 14 nov 2026) | 3877 |
| TargetSpec | si | le frecce viola verso i bersagli | 3635 |
| ModifiedPower | si | il pallino della forza | 3608 |
| PowerToughnessModCreated | si | i pallini di forza e costituzione | 3506 |
| ModifiedToughness | si | il pallino della costituzione | 3188 |
| TemporaryPermanent | si | la clessidra arancio in alto a sinistra: se ne va a fine turno (14 nov 2026, B1) | 2664 |
| TokenCreated | si | la pedina scorre in campo | 2040 |
| AddAbility | si | le parole chiave date come pillole verdi (C2); le altre abilita' date col loro testo corto sulla carta (A2, 14 nov 2026) | 1009 |
| RevealedCardCreated | si | la carta rivelata esce dal grimorio del suo proprietario, si mostra grande al centro con REVEALED, torna (14 nov 2026) | 948 |
| TokenDeleted | si | la pedina si spegne | 942 |
| MultistepEffectComplete | si | SubCategory 11: la fine del surveil dell'avversario, col ventaglio (15 nov 2026); gli altri interni | 860 |
| MultistepEffectStarted | si | SubCategory 11: il surveil dell'avversario, che Arena non ti chiede (15 nov 2026); gli altri interni | 856 |
| DisplayCardUnderCard | si | le carte esiliate sotto di lei, sfalsate dietro la carta (14 nov 2026, A1) | 644 |
| CounterRemoved | si | il segnalino tolto (la fedelta' dei poteri) | 621 |
| Shuffle | si | il grimorio si rimescola: tre dorsi che si mischiano (14 nov 2026) | 370 |
| Scry | si | il ventaglio S1 con TOP e BOTTOM (14 nov 2026) | 266 |
| ChoiceResult | si | la scelta (tipo, colore, nome, modalita') in un fumetto bianco in testa alla carta, finche' resta in campo (C1, 14 nov 2026) | 232 |
| LossOfGame | si | la schermata finale | 111 |
| ControllerChanged | si | la carta che cambia lato scorre da un campo all'altro (14 nov 2026) | 11 |
| UserActionTaken | parte | le abilita' attivate: in Performance (filtri), nel replayer solo se vanno in pila | 30010 |
| TriggeringObject | parte | chi ha fatto scattare un innesco: non c'e' una freccia | 5345 |
| LayeredEffectCreated | parte | l'effetto si vede nei pallini di forza e costituzione | 4892 |
| LayeredEffectDestroyed | parte | i pallini tornano | 3367 |
| LayeredEffect | parte | come LayeredEffectCreated | 2825 |
| Qualification | parte | «puoi giocare questa carta» (tipo 47) e' la fila PLAYABLE; gli altri permessi e divieti (non bloccabile, non blocca, non si stappa...) non si vedono | 1048 |
| CastingTimeOption | parte | kicker, modi, costi alternativi: solo nel racconto | 479 |
| Designation | parte | PREPARED, DOOR UNLOCKED, PLOTTED, SOLVED, SUSPECTED, HARNESSED sulla carta (D3); la velocita' SPEED N accanto al giocatore (V3); il tipo 23 sulle terre no | 373 |
| GainDesignation | parte | come Designation | 263 |
| Attachment | parte | l'aura e l'equipaggiamento stanno fra gli altri permanenti, non accanto a chi incantano | 242 |
| ModifiedType | parte | la carta cambia fila se diventa creatura | 229 |
| AttachmentCreated | parte | solo nel racconto («attached to») | 208 |
| FaceDown | parte | la carta a faccia in giu' e' un dorso; cosa sia per chi la possiede no | 167 |
| LoseDesignation | parte | come Designation: la pillola se ne va | 125 |
| CardRevealed | parte | nel racconto; la carta grande al centro c'e' quando Arena crea la carta rivelata (RevealedCardCreated) | 70 |
| CopiedObject | parte | la copia compare; il legame no | 9 |
| CrewedThisTurn | parte | il veicolo passa fra le creature; chi l'ha equipaggiato no | 3 |
| ObjectsSelected | no | le carte scelte (cerca, scegli) non si vedono | 778 |
| InstanceRevealedToOpponent | no | la carta della mano mostrata all'avversario non si vede | 698 |
| AbilityExhausted | no | l'abilita' esausta (exhaust) non e' segnata | 306 |
| RemoveAbility | no | le abilita' tolte non si vedono | 135 |
| ModifiedName | no | il nome cambiato non si vede | 72 |
| TextChange | no | il testo cambiato non si vede | 71 |
| MiscContinuousEffect | no | effetti continui vari | 31 |
| ModifiedColor | no | il colore cambiato non si vede | 27 |
| ClassLevel | no | il livello di una Classe non si vede | 24 |
| SaddledThisTurn | no | sellato (saddle) non si vede | 4 |
| PhaseOrStepModified | nonserve | il passo: la striscia dei turni | 69433 |
| EnteredZoneThisTurn | nonserve | contabilita' di Arena | 33856 |
| ObjectIdChanged | nonserve | il replayer segue gli id | 27959 |
| AbilityInstanceDeleted | nonserve | l'abilita' lascia la pila | 27782 |
| ColorProduction | nonserve | il mana | 6996 |
| PlayerSelectingTargets | nonserve | la scelta in corso | 3610 |
| PlayerSubmittedTargets | nonserve | la scelta fatta: le frecce | 3535 |
| SyntheticEvent | nonserve | evento interno di Arena | 2036 |
| LoyaltyActivationsRemaining | nonserve | contabilita' | 1078 |
| RevealedCardDeleted | nonserve | la carta rivelata sparisce | 736 |
| DamagedThisTurn | nonserve | contabilita' | 536 |
| ShouldntPlay | nonserve | un suggerimento di Arena | 469 |
| LinkInfo | nonserve | interno | 302 |
| DelayedTriggerAffectees | nonserve | interno | 256 |
| ReplacementEffect | nonserve | si vede l'esito | 243 |
| PredictedDirectDamage | nonserve | una previsione di Arena | 155 |
| SuppressedPowerAndToughness | nonserve | interno | 148 |
| DisqualifiedEffect | nonserve | interno | 103 |
| ModifiedCost | nonserve | si vedono le terre che pagano | 71 |
| ReplacementEffectApplied | nonserve | si vede l'esito | 20 |
| DynamicAbility | nonserve | interno | 15 |
| ManaDetails | nonserve | il mana | 13 |
| ReferencedObjects | nonserve | interno | 6 |
| GroupedIds | nonserve | interno | 4 |
| UseOrCostsManaCost | nonserve | interno | 2 |
| ChoosingAttachments | nonserve | la scelta in corso | 1 |

## Le categorie degli spostamenti di zona

si: 21  ·  parte: 4  ·  no: 1  ·  nonserve: 0

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
| Warp | si | in esilio (warp), poi FROM EXILE | 12 |
| Bounce | si | in mano | 0 |
| nil | parte | lo spostamento si vede, il motivo no | 27 |
| ManifestLike | parte | in campo a faccia in giu' (un dorso) | 8 |
| Copy | parte | la copia compare | 2 |
| SBA_IllegalAttachment | parte | l'equipaggiamento cade: si vede che resta, non il distacco | 2 |
| Separate | no | la carta divisa (split) non e' trattata a parte | 13 |

## Cosa non si vede ancora, dal piu' frequente nei log

- **ObjectsSelected** (778 volte): le carte scelte (cerca, scegli) non si vedono
- **InstanceRevealedToOpponent** (698 volte): la carta della mano mostrata all'avversario non si vede
- **AbilityExhausted** (306 volte): l'abilita' esausta (exhaust) non e' segnata
- **RemoveAbility** (135 volte): le abilita' tolte non si vedono
- **ModifiedName** (72 volte): il nome cambiato non si vede
- **TextChange** (71 volte): il testo cambiato non si vede
- **MiscContinuousEffect** (31 volte): effetti continui vari
- **ModifiedColor** (27 volte): il colore cambiato non si vede
- **ClassLevel** (24 volte): il livello di una Classe non si vede
- **SaddledThisTurn** (4 volte): sellato (saddle) non si vede

## Le istruzioni del motore che il replayer non mostra

- `dai_flashback` (Motore_Partita/effetti.py): niente segna che una carta del cimitero si puo' rilanciare
- `diventa_copia` (Motore_Partita/effetti.py): la carta cambia immagine di colpo
- `emblema` (Motore_Partita/effetti.py): gli emblemi non sono sul tavolo
- `livello_classe` (Motore_Partita/Set/TMT/meccaniche.py): TMT, il livello della classe (ClassLevel): il replayer non mostra il livello raggiunto
- `non_blocca` (Motore_Partita/effetti.py): il divieto di bloccare non si vede
- `non_bloccabile` (Motore_Partita/effetti.py): il non poter essere bloccata non si vede
- `prossima_incontrastabile` (Motore_Partita/effetti.py): non si vede
- `rivela_fino` (Motore_Partita/effetti.py): le carte rivelate non si vedono (il log le scrive: RevealedCardCreated)
- `togli_abilita` (Motore_Partita/effetti.py): le abilita' tolte non si vedono

## Le parole chiave dei set (284)

Ogni parola chiave finisce in una o piu' istruzioni del motore: quello che il replayer mostra lo dicono le istruzioni. Una parola chiave nuova (un set nuovo) si guarda: se porta un'istruzione nuova, il censimento la segnala fra le istruzioni.

Nessuna parola chiave nuova.

## Il workflow per i set nuovi

1. Il motore impara il set (`py -I -X utf8 Motore_Partita/carte_set.py --costruisci`, le meccaniche nel posto privato del set).
2. `py -I -X utf8 Companion/Strumenti/censimento_replayer.py`: esce rosso con le istruzioni, le annotazioni, le categorie e le parole chiave nuove. Per ognuna si decide come la mostra il replayer (o che non serve) e si scrive la riga in `censimento_replayer.json`; le parole chiave guardate entrano con `--accetta-parole`. Una voce «no» che conta si porta a Autore: si decide insieme come mostrarla (la regola del bambino sordo: si capisce guardando, le scritte aiutano).
3. Le prime partite del set: `py -I -X utf8 Companion/Strumenti/caccia_glitch.py <id>` e le foto del replayer; ogni glitch nel registro `GLITCH_REPLAYER.md` col suo controllo.
4. Il censimento verde e la caccia verde prima del commit.
