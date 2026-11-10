"""Le tabelle PRODUCE/VUOLE dello scout: cosa una carta produce e cosa vuole, lette dal testo con le espressioni regolari.
Stavano dentro scout_sinergie.py; dal 9 nov 2026 stanno qui, in un posto solo, perche' le legge anche la rete delle sinergie del
Companion (Card view, `Companion/App/Schede/Your_decks/rete_sinergie.py`) e importare lo scout fa partire un suo giro intero.
La regola dello scout resta (Autore, 21 set 2026): ogni sinergia trovata a mano che il bot non vede diventa una riga qui.
tags(c) vuole c["type"] e c["oracle"] (il formato di Regole/standard_carte.json)."""
import re

# ---------- 1. tag: cosa una carta PRODUCE e cosa VUOLE ----------
PRODUCE = [
    ("counter", r"put (?:a|an|one|two|three|x|that many|\w+) \+1/\+1 counter"),
    ("token", r"create (?:a|an|one|two|three|x|that many|\w+) .*?token"),
    ("lifegain", r"gains? (?:\d+|x|that much) life|lifelink"),
    ("lifeloss", r"loses? (?:\d+|x|that much|half|twice) .*?life"),
    ("noncreature", r"^(?:instant|sorcery|enchantment|artifact)(?! creature)"),
    ("demon", r"\bdemon\b"), ("dragon", r"\bdragon\b"), ("zombie", r"\bzombie\b"), ("elf", r"\belf\b"),
    ("lizard", r"\blizard\b"), ("cat", r"\bcat\b"), ("angel", r"\bangel\b"), ("vampire", r"\bvampire\b"), ("faerie", r"\bfaerie\b"),
    ("etb", r"when this creature enters|when [\w' ,-]+ enters,"),
    ("discard_self", r"discard a card|discard (?:one or more|two) cards"),
    ("mill_self", r"mill (?:a|two|three|four|x|that many) card"),
    ("sac_outlet", r"sacrifice (?:a|another) creature"),
    ("dies", r"when this creature dies|whenever a(?:nother)? (?:nontoken )?creature you control dies"),
    ("mana", r"\{t\}: add \{|add (?:one|two) mana"),
    ("landfall_land", r"search your library for (?:a|up to \w+) basic land|put (?:it|them) onto the battlefield"),
    ("draw", r"draw (?:a|two|three|x|that many) card"),
    ("blink", r"exile .*?(?:you control|you own).*?return (?:it|them|that card|those cards) to the battlefield"),
    ("bounce_own", r"return (?:up to one )?(?:other )?target .*?you control to its owner's hand"),
    ("evasion", r"\bflying\b|can't be blocked|\bmenace\b"),
    ("equipment", r"^artifact . equipment|equip \{"), ("vehicle", r"\bvehicle\b|crew \d"),
    ("artifact", r"^(?:legendary )?artifact"), ("enchantment", r"^(?:legendary )?enchantment"),
    ("instant_sorcery", r"^(?:instant|sorcery)"), ("treasure", r"treasure token"), ("food", r"food token"),
    ("prowess_body", r"\bprowess\b"), ("deathtouch", r"\bdeathtouch\b"),
    ("outlaw", r"\b(?:assassin|mercenary|pirate|rogue|warlock)\b"), ("speed", r"start your engines"),
    ("damage_face", r"deals? (?:\d+|x) damage to (?:any target|each opponent|target player|target opponent)"),
    ("swarm", r"create (?:two|three|four|x|that many|a number of) .*?tokens?|offspring|mobilize|amass|for each creature you control, create|token that's a copy"),
    ("pesca_evento", r"draw (?:a|two|three|x|that many) card"),
    ("vita_evento", r"you gain \d+ life|gain that much life|lifelink"),
]
VUOLE = [
    ("counter", r"whenever (?:you put|one or more) \+1/\+1 counter|for each \+1/\+1 counter|with (?:a|one or more) \+1/\+1 counter|creature with a \+1/\+1 counter"),
    ("token", r"whenever (?:a|one or more) tokens? .*?enters|tokens? you control|for each (?:creature )?token|sacrifice a token"),
    ("lifegain", r"whenever you gain life|if you gained life|you've gained life|gained (?:\d+ or more )?life this turn"),
    ("lifeloss", r"whenever an opponent loses life|if an opponent would lose life|whenever a player loses life"),
    ("noncreature", r"whenever you cast a noncreature spell|noncreature spells you cast"),
    ("demon", r"if you control a demon|demons? you control"), ("dragon", r"dragons? you control|another dragon"),
    ("zombie", r"zombies you control|another zombie"), ("elf", r"elves you control|another elf|elf you control"),
    ("lizard", r"lizards? you control|with one or more lizards"), ("cat", r"cats you control|another (?:nontoken )?cat"),
    ("angel", r"angels? you control|another angel"), ("vampire", r"vampires? you control|another vampire"),
    ("faerie", r"faeries? you control|with one or more faeries|another faerie"),
    ("etb", r"exile .*?(?:you control|you own).*?return|return (?:up to one )?(?:other )?target .*?you control to its owner's hand|whenever (?:a|another) creature you control enters|whenever one or more (?:other )?creatures you control enter"),
    ("discard_self", r"whenever you discard|if you discarded|whenever one or more cards are put into your graveyard from anywhere|threshold|delirium|descend"),
    ("mill_self", r"threshold|delirium|descend|creature cards? in your graveyard|from your graveyard"),
    ("sac_outlet", r"whenever you sacrifice|whenever a creature you control dies|when this creature dies"),
    ("dies", r"sacrifice (?:a|another) creature|as an additional cost .*?sacrifice"),
    ("mana", r"\{x\}|\{[4-9]\}|\{\d\}\{[wubrg]\}\{[wubrg]\}"),
    ("landfall_land", r"landfall|whenever a land you control enters|lands you control|for each land"),
    ("draw", r"whenever you draw|second card each turn|no maximum hand size"),
    ("blink", r"when this creature enters|when [\w' ,-]+ enters,"),
    ("bounce_own", r"when this creature enters|when [\w' ,-]+ enters,"),
    ("evasion", r"whenever .*?deals combat damage to a player|whenever this creature deals combat damage"),
    ("equipment", r"equipped creature|whenever .*?equipment .*?enters|equipment you control"),
    ("vehicle", r"vehicles? you control|whenever .*?vehicle"),
    ("artifact", r"artifacts? you control|whenever an artifact|affinity for artifacts|for each artifact"),
    ("enchantment", r"whenever an enchantment you control enters|enchantments? you control|eerie|constellation"),
    ("instant_sorcery", r"instant (?:and|or) sorcery|whenever you cast an instant or sorcery|prowess|magecraft|opus"),
    ("treasure", r"treasures? you control|sacrifice a treasure|for each treasure"), ("food", r"foods? you control|sacrifice a food"),
    ("prowess_body", r"^instant|^sorcery"), ("deathtouch", r"fights?|deals damage equal to its power"),
    ("outlaw", r"outlaws? you control|whenever you cast an outlaw|other outlaws"), ("speed", r"max speed|your speed|if you have max speed"),
    ("damage_face", r"whenever an opponent loses life|whenever .*?deals damage to an opponent"),
    ("swarm", r"creatures you control get \+|for each (?:other )?creature you control|whenever (?:a|one or more|another) (?:creature )?tokens? .*?enters|whenever you attack with (?:two|three) or more|number of creatures you control|each creature you control"),
    ("pesca_evento", r"whenever you draw a card"),
    ("vita_evento", r"whenever you (?:would )?gain(?:ed)? \d* ?life"),
]
PR = [(t, re.compile(p, re.I | re.M)) for t, p in PRODUCE]
VU = [(t, re.compile(p, re.I | re.M)) for t, p in VUOLE]


def tags(c):
    txt = (c["type"] + "\n" + c["oracle"]).lower()
    return {t for t, p in PR if p.search(txt)}, {t for t, p in VU if p.search(txt)}
