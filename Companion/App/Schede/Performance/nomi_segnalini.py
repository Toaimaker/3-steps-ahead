"""I nomi dei segnalini di Arena (counter_type delle annotazioni AnnotationType_Counter), letti il 14 nov 2026 in sola lettura dalla tabella Enums
(Type CounterType) del database delle carte di Arena (Raw_CardDatabase_*.mtga), coi testi inglesi di Localizations_enUS. Servono al replayer di Performance
(i segnalini ben visibili sulle carte). Un tipo nuovo che manca si vede come «counter»: si rigenera rileggendo la tabella."""

NOMI = {
    1: '+1/+1', 2: '-1/-1', 3: 'Poison', 4: 'Wind', 5: 'Time', 6: 'Fade',
    7: 'Loyalty', 8: 'Wish', 9: 'Age', 10: 'Aim', 11: 'Arrow', 12: 'Arrowhead',
    13: 'Awakening', 14: 'Blaze', 15: 'Blood', 16: 'Bounty', 17: 'Bribery', 18: 'Carrion',
    19: 'Charge', 20: 'Control', 21: 'Corpse', 22: 'Credit', 23: 'Cube', 24: 'Currency',
    25: 'Death', 26: 'Delay', 27: 'Depletion', 28: 'Despair', 29: 'Devotion', 30: 'Divinity',
    31: 'Doom', 32: 'Dream', 33: 'Echo', 34: 'Elixir', 35: 'Energy', 36: 'Eon',
    37: 'Eyeball', 38: 'Fate', 39: 'Feather', 40: 'Filibuster', 41: 'Flame', 42: 'Flood',
    43: 'Fungus', 44: 'Fuse', 45: 'Glyph', 46: 'Gold', 47: 'Growth', 48: 'Hatchling',
    49: 'Healing', 50: 'Hoofprint', 51: 'Hourglass', 52: 'Hunger', 53: 'Ice', 54: 'Infection',
    55: 'Intervention', 56: 'Javelin', 57: 'Ki', 58: 'Level', 59: 'Luck', 60: 'Magnet',
    61: 'Mannequin', 62: 'Matrix', 63: 'May', 64: 'Mine', 65: 'Mining', 66: 'Mire',
    67: 'Muster', 68: 'Net', 69: 'Omen', 70: 'Ore', 71: 'Page', 72: 'Pain',
    73: 'Paralyzation', 74: 'Petal', 75: 'Petrification', 76: 'Phylactery', 77: 'Pin', 78: 'Plague',
    79: 'Polyp', 80: 'Pressure', 81: 'Pupa', 82: 'Quest', 83: 'Scream', 84: 'Scroll',
    85: 'Shell', 86: 'Shield', 87: 'Shred', 88: 'Sleep', 89: 'Sleight', 90: 'Slime',
    91: 'Soot', 92: 'Spell', 93: 'Spore', 94: 'Storage', 95: 'Strife', 96: 'Study',
    97: 'Theft', 98: 'Tide', 100: 'Tower', 101: 'Training', 102: 'Trap', 103: 'Treasure',
    104: 'Verse', 105: 'Vitality', 106: 'Wage', 107: 'Winch', 108: 'Lore', 109: '+1/+2',
    110: '+0/+1', 111: '+0/+2', 112: '+1/+0', 113: '+2/+2', 114: '-0/-1', 115: '-0/-2',
    116: '-1/-0', 117: '-2/-1', 118: '-2/-2', 119: 'Manifestation', 120: 'Gem', 121: 'Crystal',
    122: 'Isolation', 123: 'Hour', 124: 'Unity', 125: 'Velocity', 126: 'Brick', 127: 'Landmark',
    128: 'Prey', 129: 'Silver', 130: 'Egg', 131: 'Hit', 132: 'Knowledge', 133: 'Task',
    134: 'Coin', 135: 'Deathtouch', 136: 'First strike', 137: 'Flying', 138: 'Hexproof', 139: 'Lifelink',
    140: 'Menace', 141: 'Reach', 142: 'Trample', 143: 'Vigilance', 144: 'Foreshadow', 145: 'Incarnation',
    146: 'Soul', 147: 'Voyage', 148: 'Ghostform', 149: 'Night', 150: 'Indestructible', 151: 'Hone',
    152: 'Book', 153: 'Point', 154: 'Enlightened', 155: 'Harmony', 156: 'Void', 157: 'Ember',
    158: 'Ritual', 159: 'Valor', 160: 'Judgment', 161: 'Invitation', 162: 'Croak', 163: 'Bloodline',
    164: 'Suspect', 165: 'Acorn', 166: 'Hatching', 167: 'Stash', 168: 'Collection', 169: 'Rope',
    170: 'Ingenuity', 171: 'Phyresis', 172: 'Stun', 173: 'Oil', 174: 'Defense', 175: 'Experience',
    176: 'Slumber', 177: 'Rejection', 178: 'Burden', 179: 'Hope', 180: 'Influence', 181: 'Skewer',
    182: 'Bore', 183: 'Chorus', 184: 'Dread', 185: 'Finality', 186: 'Bloodstain', 187: 'Impostor',
    188: 'Unlock', 189: 'Fetch', 190: 'Loot', 191: 'Exalted', 192: 'Story', 193: 'Everything',
    194: 'Blight', 195: 'Supply', 196: 'Feeding', 197: 'Nest', 198: 'Possession', 199: 'Rev',
    200: 'Incubation', 201: 'Revival', 202: 'Fellowship', 203: 'Bait', 204: 'Wreck', 205: 'Decayed',
    206: 'Conqueror', 207: 'Fire', 208: 'Film', 209: 'Double strike', 210: 'Invasion', 211: 'Plan',
    212: 'Saurian', 213: 'Peace', 214: 'Promotion', 215: 'Haste', 216: 'Shadow', 217: 'Refine',
    218: 'PHCT218', 219: 'PHCT219', 220: 'PHCT220', 221: 'PHCT221', 222: 'PHCT222',
}


def nome(tipo):
    return NOMI.get(tipo, "counter")
