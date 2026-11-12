# L'app del Companion

Autore, 9 nov 2026: *«assicurati che nella cartella del companion ogni scheda sia una sottocartella e ogni funzione dentro
le schede sia una sottocartella nella propria sottocartella scheda … voglio un'app pulita in termini di build e codice»*.
Scelta presa con lui: **una cartella per scheda, un file per funzione** (una cartella per ogni funzione sarebbero centinaia
di cartelle con un file solo). Fino al 9 nov 2026 tutta la finestra stava in due file, `finestra_schede.py` (5.658 righe)
e `finestra_companion.py` (3.398 righe), più trenta file sciolti nella radice di `Companion/`.

## Dove sta cosa

```
Companion/
  Companion.bat  companion.py  percorsi.py  progetto.py    il motore che segue il Player.log (non si tocca: regola dei blindati)
  Drafter/  Suggeritore/  Comune/                          drafter e spalla, blindati
  Grafica/                                                 font, icone, simboli, loghi (percorsi.GRAFICA)
  Strumenti/                                               segnala, archivio, collaudo, controllo del codice, prove dell'app
  App/
    finestra.py          la finestra grande: la classe Finestra (costruzione in cinque sezioni, il giro), Companion.bat la apre
    Comune/              ambiente (cartelle e file di stato), tema (colori, font), icone, widget (tendine, spunte, pulsanti),
                         pagina_base (la pagina di una scheda e il grafico del win rate), dati_app (collezione, jolly, partite,
                         meta), capsule (le liste delle carte come in Arena), carta_tela (le carte disegnate sulla
                         tela della griglia, non una finestra per carta), tabella_tela (le tabelle disegnate,
                         con celle dichiarate), registro_errori, stemmi_icone
    Chat/                chat_partita (la chat), chat_testi (fasi, inglese, righe), diario, pescate, chat_finestra (la chat nella finestra)
    Schede/
      Meta/              pagina_meta, dati_meta, matchup_log (la banca dati delle partite), Deck HUD: hud_partita (la partita dal Player.log),
                         hud_mazzo (archetipo, carte probabili, T2-T4, istantanee, tu contro), vista_hud (la finestra e il pulsante)
      Drafter/           drafter_evento (Rare pick, calendario, Play limited, Closed session, record), drafter_mazzi (le tre fasi, i mazzi,
                         Select deck, Fix, overlay), deck_sheet, drafter_partita, dati_drafter, calendario_eventi, chiudi_draft,
                         pronto_limited, finestra_mazzi (la finestra a 3 colonne di prima)
      Performance/       pagina_performance (la tendina Mode), pagina_limited, pagina_standard
      Your_decks/        pagina_mazzi, gruppi_mazzi, finestra_mazzo, scheda_mazzo, mani_mazzo, esporta_mazzo,
                         mazzi_salvati, mazzi_arena, dati_mazzo, prezzi_carte
      Resources/         pagina_risorse, farmer, roadmap, roi, trend, roadmap_check, risorse, verifica_piani, premi_eventi
      Collection/        pagina_collezione, collezione_carte, collezione_viva, cuoci_carte, costruttore_mazzi (il builder), terre_auto
      Social/            finestra_social (la colonna), social (i dati)
      Help/              pagina_help (ogni scheda e i suoi comandi, gli aggiornamenti), aggiornamenti (il controllo: il manifest all'indirizzo di aggiornamenti.json)
    Overlay/             l'overlay della costruzione sopra Arena
    Prove/               le prove della finestra, una per scheda
```

Una pagina grande e' una classe sola divisa in **mixin**, un file per funzione: `PaginaRisorse` e' `pagina_risorse.py` piu'
`Farmer` (farmer.py), `Roadmap`, `Roi`, `RoadmapCheck`, `Trend`; `PaginaStandard` (Performance) eredita la finestra di un
mazzo da Your_decks (`FinestraMazzo`, `SchedaMazzo`, `ManiMazzo`, `EsportaMazzo`), che usano anche Your decks e Meta.
**La finestra grande** e' la classe `Finestra` di `finestra.py`: `__init__` chiama le cinque sezioni della costruzione
(`_costruisci_finestra`, `_chat`, `_colonna`, `_schede`, `_avvio`), il giro (`giro`, `giro_corpo`, `lavoro_dati`, `lavoro_risorse`)
sta li'; il resto sono mixin nella cartella di chi li usa: `ChatFinestra` (Chat/chat_finestra.py), `DrafterEvento`,
`DrafterMazzi`, `DeckSheet`, `DrafterPartita` (Schede/Drafter/). Fino al 9 nov 2026 era la funzione `avvia()` di 1.627
righe con 66 funzioni annidate: le variabili condivise sono diventate attributi (`self.x`), quelle di una sola sezione
restano locali. `avvia()` crea la finestra e accende il ciclo di Tk.

I registri delle pagine dei mazzi stanno su `FinestraMazzo`: `IN_VISTA` (chi ha la finestra del mazzo aperta) e `MAZZI`
(la pagina Your decks, dove il builder salva).

## Le regole del codice

1. **I nomi dei moduli sono unici** in tutte le cartelle del sys.path: si importano per nome (`import risorse as RS`,
   `from tema import CI as C`). `percorsi.py` mette nel sys.path da solo ogni cartella di `App/` che ha dei `.py`: una
   scheda nuova non va scritta da nessuna parte.
2. **Un modulo che si lancia** comincia con la testa che sale fino a `percorsi.py` (copiala da un file di `Prove/`); un
   modulo che si importa e basta non ne ha bisogno.
3. **Import espliciti, niente `import *`, niente giri**: un modulo di una scheda importa da `Comune/`, `Chat/` e dai dati
   della sua scheda; le pagine non si importano a vicenda (se serve, il pezzo comune va in un modulo di dati o in un mixin).
4. **Le immagini** si leggono da `percorsi.GRAFICA` (`ambiente.ASSET`), mai da un percorso relativo al file.
5. **Un programma lanciato dalla finestra** si trova con `percorsi.programma("x.py")`, mai con un percorso scritto a mano.
6. **Prima di ogni commit**: `py -I -X utf8 Companion/Strumenti/controllo_codice.py` (nomi non definiti, import inutili,
   moduli che non si trovano, nomi doppi; esce 1) e `py -I -X utf8 Companion/Strumenti/prove_app.py` (tutte le prove
   dell'app; esce 1 su un rosso). Il controllo ha la sua prova negativa: `controllo_codice.py --prova`.

## Le prove

| Comando | Cosa prova |
| :--- | :--- |
| `Companion/App/Prove/prova_dati.py` | i dati di ogni pagina, stampati, senza finestra |
| `Companion/App/Prove/prova_meta.py` | la scheda Meta fuori schermo |
| `Companion/App/Prove/prova_sezioni.py` | Your decks: Arena decks, Wishlist, Deck building, il builder |
| `Companion/App/Prove/prova_mazzi.py` | la scheda Your decks fuori schermo |
| `Companion/App/Prove/prova_collezione.py` | la scheda Collection fuori schermo |
| `Companion/App/Prove/prova_risorse.py` | Resources in una finestra nascosta: tendine, spunte, goal, roadmap, Roadmap check |
| `Companion/App/Prove/prova_performance.py` | Performance in una finestra nascosta |
| `Companion/App/Prove/prova_help.py` | Help fuori schermo: le sezioni, i comandi del Board, gli aggiornamenti col pulsante e il pallino |
| `Companion/App/Prove/prova_account.py` | l'app pubblica con due account di Arena in un log finto: ognuno i suoi dati, All accounts, il cambio in Arena (10 nov 2026) |
| `Companion/App/Prove/prova_finestra.py` | la finestra grande: chat, inglese, pescate, posizione, solo i limited, Cercatore |
| `Companion/App/Comune/tabella_tela.py --prova` | le tabelle su tela: misure, fasce, evidenzia, allarga, clic e accensione di una riga (11 nov 2026) |
| `Companion/App/Comune/carta_tela.py --prova` | le carte sulla tela della griglia: elementi, eventi smistati, distruggi (11 nov 2026) |
| `Companion/Strumenti/prove_app.py` | tutte queste piu' le prove dei moduli di dati, dell'overlay, il collaudo della finestra e il banco della spalla |

Tutte con `py -I -X utf8`. Le finestre di prova stanno fuori schermo o trasparenti, mai davanti a Autore.

## Il motore grafico: misurare prima di cambiare

Lo scatto viene da quante finestre di Windows l'app ridipinge (ogni widget di Tk e' una finestra), non da Python. Una griglia, un elenco o una tabella nuovi si
disegnano su una tela sola (elementi coi tag, `carta_tela.CartaTela` per le carte), non con widget messi nella tela con `create_window`. Prima e dopo ogni
cambio grafico: `py -I -X utf8 Companion/Strumenti/metro_grafico.py` (la finestra vera, trasparente, sullo schermo; mai con Arena aperta) e
`metro_griglie.py`. Misure e strade scartate: `Note/Motore_Grafico_App.md`.
Un contenuto che si rifa' (il builder a ogni carta, la finestra del mazzo a ogni mazzo) non distrugge i widget vecchi dentro il clic: `widget.svuota(contenitore)`
li stacca subito e `widget.smonta` li distrugge dopo, a pezzi (i pezzi in attesa hanno `via = True`: chi scorre i widget li salta). Una tela che si
impagina con la finestra non chiede la sua larghezza (`width=1`) e disegna all'ultima misura (`capsule.Liste.elenco`). Sulla scheda video (`tela_gpu`) gli
sprite cancellati e rifatti si riprendono dalla riserva e i domini vuoti restano: cancellare tutto e ridisegnare costa la meta' di prima.

## La storia dei due moduli di prima

Il testo in testa ai due file che il 9 nov 2026 sono diventati questa cartella, come era: i nomi dei file e dei comandi
sono quelli di allora.

### finestra_schede.py

```text
Le schede dei tipi di gioco nella colonna destra della finestra grande (Autore, 17 ott 2026 ~21:00: «a sx la chat, a
destra i dati, si esplora per schede, le schede stanno in alto come in Maya e ogni scheda porta a una tipologia di gioco
che aggiorna la parte destra: dati di winrate, meta dei mazzi ecc»).

La barra delle schede e la scheda «In corso» (record e mazzo inviato) stanno in finestra_companion.py; qui le pagine dei tipi
di gioco, una classe per pagina, e i dati che leggono:
- Quick Draft e Premier Draft: le tue partite del set (Untapped), il calendario del formato (Regole/calendario_set.json),
  il meta delle coppie (Espansioni/<SET>/Quick/Quick_Draft.md: vinte del Quick e del Premier, trofei del Quick), i tuoi
  draft (un clic apre il mazzo su Untapped) e, per il Quick, il campo degli avversari.
- Standard: le tue partite classificate (Ladder, col rango) e libere (Play) da Untapped, e il meta di Untapped al rango
  platinum (Note/meta_untapped.json, scritto da Motore/meta_untapped.py) con le carte che possiedi.
Il codice delle tre schede di prima («Il set», «Calendario», «Classifica») e' lo stesso, diviso per formato.

Dal 17 ott 2026 ~22:30 (Autore: «nelle schede quick, premier e standard voglio dati sui mazzi che uso io di piu', grafici
che mi dicono quanto vinco o perdo»; «sono finestre di dati, qui non serve la chat») queste pagine prendono tutta la larghezza
della finestra, su due colonne: a sinistra i tuoi numeri e i tuoi mazzi piu' usati (per coppia di colori nel draft, per nome
del mazzo in Standard) col win rate; a destra l'andamento, e il meta. Colori: vinte azzurro #24baff, perse rosso #d9534f
(barre del win rate), controllati per i daltonici (OKLab, Machado 2009): distanza 33,5 a vista normale, 29,6 protanopia, 24,1
deuteranopia (soglia 8); il verde/rosso dava 7,4 in deuteranopia.
L'andamento e' un grafico cartesiano (Autore, 17 ott 2026 ~23:00: «il grafico lo voglio cartesiano, no a barre»): in
orizzontale le partite una dopo l'altra, in verticale il saldo, vinte meno perse dall'inizio; la linea sale a ogni vittoria e
scende a ogni sconfitta. Nel draft tutte le partite del set, con una tacca dove comincia ogni draft; in Standard la
classificata. Dal 17 ott 2026 ~23:15 (Autore: «i grafici stanno in alto e occupano lo spazio delle due colonne, belli
evidenti; mettici anche gli step in cui si passa da una lega a un'altra»; «i trofei li indichi con il simbolo delle coppe»):
il grafico sta in alto a tutta larghezza e si chiama «Win rate» (stesso giorno: «i grafici non devono chiamarsi quanto
vinci quanto perdi, metti win rate se proprio, e togli la frase vinte meno perse»): la linea e' il win rate dall'inizio,
partita dopo partita, con la linea del 50% marcata; una linea verticale col nome della lega dove passi da una lega all'altra (Bronze,
Silver, Gold...) e dove comincia una stagione nuova; una coppa sopra la linea alla fine di ogni draft da 7 vinte; i trofei
nelle tabelle e nei numeri sono coppe.
Dal 17 ott 2026 ~23:30 (Autore: «nei tuoi numeri voglio: % winrate, partite totali, partite vinte, partite perse, trofei,
rapporto vinte/perse, dati su gemme ottenute, su buste ottenute, su rare e mitiche ottenute; menu a tendina: tutti i dati o
solo quelli di una determinata espansione»): i numeri sono una griglia di 3 x 3; gemme, buste, rare e mitiche sono i premi
veri letti dai log di Arena (Companion/premi_eventi.py, dal 22 set 2026: prima non ci sono log), le partite e i trofei tutto
lo storico. In cima a ogni pagina il menu «Espansione» (tutte, o un set) filtra numeri, mazzi, grafico e i tuoi draft; il
meta resta quello del set in corso. In Standard l'espansione e' il periodo del set (come lo divide la copia delle partite).
Leggibilita' (Autore, 17 ott 2026 ~23:40: «i nomi dei dati devono stare sopra i dati ed essere scritti in bianco stampatello
maiuscolo», «tutto deve essere strutturato come UX a portata di tutti, dati facili da individuare, righe ben organizzate, ben
allineate e facili da leggere»): ogni numero e' un riquadro col nome sopra in maiuscolo bianco e il dato sotto; ogni elenco e'
una tabella a griglia con le intestazioni in maiuscolo bianco sopra le colonne e le righe a fasce alterne.
Dal 18 ott 2026 (Autore: «in quick draft la scheda i tuoi mazzi non serve; grafico a sinistra e dati a destra; i draft
possono essere messi tutti in questo tab, che invece di quick draft si chiamera' limited; un menu a tendina sceglie
l'espansione, uno accanto sceglie il formato di limited, tutti i limited di Arena»): la scheda «Limited» sostituisce
«Quick Draft» e «Premier Draft»; menu Espansione e Formato (FORMATI_LIMITED, piu' i tipi trovati nelle partite); a sinistra
il grafico e il calendario, a destra i tuoi numeri e il meta. Standard resta com'era.
Dal 18 ott 2026 (Autore: «lo stile tendine piu' semplice, simile a quello di un sito di riferimento»; «lo sfondo dei grafici con linee e
riempimenti alterni molto leggeri»): le tendine sono la classe Tendina,  scuro; i grafici hanno fasce orizzontali
alterne ogni 10% e linee leggerissime, il 50% piu' marcato.
Dal 18 ott 2026 (Autore: «in standard voglio la stessa impaginazione, solo che la lista dei mazzi ha un menu a tendina:
i miei mazzi, quelli del meta e quelli da farming, e un altro menu a tendina per il meta di ogni formato»): Standard ha
l'impaginazione di Limited (grafico a sinistra, numeri e mazzi a destra) e la scheda «Mazzi» con due tendine, «Mostra»
(i tuoi mazzi, il meta) e «Formato».
Il meta degli altri formati e il farming (18 ott 2026): il meta di Alchemy, Explorer, Historic, Timeless e Brawl viene da
Note/meta_untapped_<formato>.json, scritto da Motore/meta_formati.py (stessa API pubblica di Untapped, rango platinum,
coda Bo1). Fuori da Standard Untapped non da' il win rate gratis: al suo posto la colonna «forza», la posizione per il valore
con cui la tier list gratis ordina gli archetipi (spiegato in meta_formati.py). Lo Standard Brawl non ha meta su Untapped:
la tendina lo dice. «Farming» (i tuoi mazzi che hanno vinto gemme e buste negli eventi costruiti a premi) entra nella
tendina «Mostra» solo quando nei log c'e' almeno un premio di un evento costruito: i premi da premi_eventi (EventReward e
EventPayEntry per corso, col nome del mazzo del corso), il formato costruito dell'evento dalla copia delle partite di
Untapped (super_format 2), la lista dall'ultima partita di quel mazzo in quell'evento. Una fonte pubblica dei mazzi migliori
evento per evento non esiste (Note/Meta_Formati_E_Farming.md): il farming e' solo il tuo, misurato.
Loghi delle leghe (Autore, 18 ott 2026: «sui grafici i loghi delle leghe identici a quelli di Arena»): le icone ufficiali
di Arena, scaricate col suo ok dalla tabella dell'articolo di Draftsim sul ranking (draftsim.com/mtg-arena-ranking-system,
file rank_<constructed|limited>_<lega>_t1.png) e risalvate in Companion/finestra/leghe/<constructed|limited>_<Lega>.png;
sul grafico il logo della lega sta sulla linea, sulla vetta dove l'hai raggiunta (6 nov 2026), una retrocessione sotto la linea; ↺ stagione nuova e' una linea tratteggiata.
Il dettaglio di un mazzo (Autore, 18 ott 2026: «l'elenco dei mazzi in standard rendilo cliccabile: sulla sinistra quando
seleziono un mazzo i dati e i grafici cambiano e parlano di quel mazzo: elenco carte, se e' craftabile, copia incolla lista su
Arena, quanto ha farmato, quando e' stato craftato»; «l'elenco formato deve darli tutti»): un clic su un mazzo (tuo o del
meta) sostituisce il grafico a sinistra con la scheda del mazzo. La lista viene dal codice del mazzo dell'ultima partita
(Untapped, Companion/Comune/deckstring.py) o dalla lista del meta; le carte che hai da Collezione/collezione_nomi.json; i jolly
dall'ultimo inventario nei log di Arena; la rarita' da Collezione/arena_cards_cache.json; i premi degli eventi giocati con quel
mazzo da premi_eventi.premi_mazzo. Arena non scrive quando un mazzo e' stato creato: il dato vero piu' vicino e' la data
della prima partita giocata con quel mazzo, e si chiama cosi'. La tendina Formato elenca tutti i formati costruiti di Arena;
le partite tue sono riconosciute solo in Standard (super_format 2): negli altri formati la tendina dice che le tue partite
non ci sono (Modern su Arena non esiste).
Nell'interfaccia non si citano le fonti dei dati (Autore, stesso giorno: «non citare le fonti»): le fonti stanno qui sopra.
L'interfaccia e' in inglese (Autore, 4 nov 2026: «scriviamo tutta l'app in inglese»): qui si traducono i testi, le chiavi dei dati restano. La scheda Risorse (Autore, 4 nov 2026: «quanto gold viene farmato ogni mese in media / quanto gold e gemme vengono
reinvestite e in cosa / quanti pack e carte ottenute ogni mese / quante wc ottenute ogni mese / i dati possono essere filtrati
per settimana / mese e anno»): i dati e come si leggono in Companion/risorse.py, dai Player.log, dal 22 set 2026. L'assetto e' il
suo, dello stesso giorno: in cima le tendine Periodo, Quale e Risorsa e la spunta Oro in gemme; sotto il grafico a tutta larghezza e, sempre
sotto il grafico, le sezioni Risorse, Spese e Jolly, che rispondono tutte all'incrocio delle tendine («togliamo la sezione season e spostiamo
come le altre sezioni anche jolly sotto il grafico e rispondera' all'incrocio delle tendine»). Le icone di oro, gemme e buste
sono quelle del progetto open source MTGA Tool (github.com/mtgatool/mtgatool-desktop, src/assets/images: gold, gem, booster; GPL-3.0),
scaricate col suo ok il 4 nov 2026 in Companion/finestra/risorse/; quella delle carte, due carte a V, e' disegnata da noi.

    py -I -X utf8 Companion/finestra_schede.py --prova            i dati di ogni pagina, stampati, senza finestra
    py -I -X utf8 Companion/finestra_schede.py --prova-collezione la scheda Collection fuori schermo: filtri, pagine, azzera
    py -I -X utf8 Companion/finestra_schede.py --prova-mazzi      la scheda Your decks fuori schermo
    py -I -X utf8 Companion/finestra_schede.py --prova-risorse    la scheda Resources in una finestra nascosta, ogni tendina e ogni obiettivo
```

### finestra_companion.py

```text
La finestra del companion,  scuro (12 ott 2026).

Non tocca il companion: legge il suo diario (Log_Arena/companion_AAAAMMGG.txt) e lo mostra in due colonne.
- A sinistra la partita come una mini chat: un consiglio per riga, quadratino verde per il tuo turno e rosso
  per il suo; quando il companion corregge il consiglio dello stesso turno («GIOCA ORA») la riga vecchia
  si barra e arriva «cambio idea».
- A destra i dati, per schede (Autore, 17 ott 2026 ~21:00: «si esplora per schede, le schede stanno in alto come in
  Maya e ogni scheda porta a una tipologia di gioco che aggiorna la parte destra»). La barra sta sotto la testata, la chat
  non cambia. «Drafter» (fino al 18 ott 2026 «In corso»): il record del draft in corso, una coppa per ogni vinta e un teschio per ogni persa; il voto del
  mazzo inviato al cancello (Log_Arena/mazzo_inviato.json, scritto da controlla_mazzo --json: tier, vittorie attese,
  percentile, avvisi di mana, esito del cancello) e, prima del cancello, i 3 mazzi proposti da rating_mazzi in tre
  colonne (Log_Arena/mazzi_costruzione.json). «Quick Draft», «Premier Draft», «Standard»: i tuoi numeri, il calendario e il meta dei mazzi del tipo di gioco
  (Companion/finestra_schede.py). Nessuna finestra del companion resta sopra le altre.

Si puo' tenere accesa accanto al companion: non scrive niente e non clicca niente.
Uso:  py -I -X utf8 Companion/finestra_companion.py            (finestra)
      py -I -X utf8 Companion/finestra_companion.py --tuoi     (si apre sulla classifica dei tuoi draft)
      py -I -X utf8 Companion/finestra_companion.py --campo    (si apre sul campo: gli avversari come gruppo)
      py -I -X utf8 Companion/finestra_companion.py --prova    (legge il diario di oggi e i dati, stampa, esce)
      py -I -X utf8 Companion/finestra_companion.py --scheda performance  (si apre su una scheda: corso, performance, limited, standard, risorse)
      py -I -X utf8 Companion/finestra_companion.py --diario FILE   (collaudo: legge quel diario, per esempio quello di un replay)
```
