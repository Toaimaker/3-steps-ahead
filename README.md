# 3 Steps Ahead · free MTG Arena deck tracker and deck builder (open beta 0.1.93)

A free desktop companion for MTG Arena on Windows (Mac: experimental, see below). It reads your own Arena log (Player.log) and shows your decks with their real record,
on the play and on the draw, a card-by-card analysis of why they win and lose, a deck builder over your collection with a mana base calculator,
a board to lay out synergies, your collection with format legality, your ranked history and a plan for gold and gems.

Unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. See NOTICE.md.

## Install (Windows 10/11)

1. Download **3-Steps-Ahead-Setup.exe** from the [latest release](https://github.com/Toaimaker/3-steps-ahead/releases/latest/download/3-Steps-Ahead-Setup.exe) and run it. Everything is inside: no Python to install, no admin rights.
   The setup is not signed yet: if Windows says "Windows protected your PC", click *More info → Run anyway*.
2. In Arena: *Options → Account → Detailed Logs (Plugin Support)* on.
3. Start 3 Steps Ahead from the Start menu or the desktop. The first start downloads about 125 MB of public card data.

To uninstall: Windows Settings → Apps. Your decks and boards stay in the app folder's Log_Arena unless you delete it.

From source (developers): unzip the release zip, install Python 3.11, run `Install.bat` once, then `3 Steps Ahead.bat`.

## Mac (experimental, not tested on a real Mac yet)

1. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/macos/) (it includes Tk).
2. Download the release zip, unzip it, open the folder. Right-click **Install.command** → *Open* (the first time macOS asks because the file is not signed), wait for "Done".
3. In Arena: *Options → Account → Detailed Logs (Plugin Support)* on.
4. Right-click **3 Steps Ahead.command** → *Open*. The first start downloads about 125 MB of public card data.

On Mac the Board is drawn without the graphics card, and the deck-building overlay over Arena is Windows only.
If something does not work, tell us on Discord with your macOS version: the Mac build is new.

## What's in the beta

Meta, Your decks (with Analysis and the Board), Performance, Resources, Collection, Help.
The in-game drafter and live advice are not in the beta yet.

## Privacy

Your log stays on your PC. Sharing game data is off unless you say yes on first start; see PRIVACY.md.

## Updates

The Help tab checks for new versions and shows a download button.

## Support

The app is in beta and 100% free, for everyone: no plans, nothing locked. If it helps you, you can support the project with €2.99, whenever you like: the support page is coming soon.

## Credits

Card data and images from Scryfall. Premier Draft history and color-pair matchups from the [17Lands public datasets](https://www.17lands.com/public_datasets),
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), aggregated by 3 Steps Ahead. Not affiliated with or endorsed by Scryfall, Untapped.gg or 17Lands.
Card type symbols from the [Mana font](https://github.com/andrewgioia/mana) by Andrew Gioia.
