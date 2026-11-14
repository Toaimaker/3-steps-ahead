# Privacy notice · 3 Steps Ahead (beta)

_Last updated: 2026-11-14. Data controller: Francesco Latini. Contact: fun4graphic@gmail.com._

## What the app does on your PC

3 Steps Ahead is a desktop app for MTG Arena players. It reads the log file that Arena writes on your computer
(`%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log`) to show your games, decks, collection and resources.
It does not read Arena's memory, does not change Arena's files, and never clicks or types in the game.

Everything the app reads and computes stays in its own folder on your PC (`Log_Arena`), unless you choose to share game data.

## Data downloaded by the app

On first start and then about once a week the app downloads public card data: Scryfall bulk data (`api.scryfall.com`). The Arena
card database is read from the MTG Arena client installed on your PC, nothing is downloaded for it. If you link your public Untapped.gg profile, it also downloads your
collection and your games from Untapped.gg. These requests go from your PC to those services, under their own privacy terms.

## Sharing game data (off by default)

On first start the app asks whether you want to share game data to help improve it. If you say no, nothing is sent.
You can change your choice any time in the Help tab.

If you say yes, for each finished game the app sends:

- the event name, its format (Standard, Historic, limited...) and whether it is best-of-three, and the day (no time of day);
- your Arena rank when the game started (for example "Gold 3"), to compare decks league by league;
- the result, who started, how many mulligans, how many turns;
- your deck list, your kept opening hand, the opposing cards you saw.

It never sends your in-game name, your Arena account id, your opponents' names, or anything else from your PC.
Your account id is replaced by a one-way code (SHA-256 with a fixed app salt): the same code for all your games, so the data
is **pseudonymous**, not anonymous. Before sending, games wait in a queue you can read: `Log_Arena\condivisione\coda.jsonl`.

**Why**: to measure which cards, decks and choices win, and to improve the app's advice for everyone.
**Legal basis**: your consent (GDPR art. 6(1)(a)); you can withdraw it at any time in Settings, without affecting what was sent before.
**Where and how long**: on Cloudflare (Cloudflare, Inc., acting as our processor), in a D1 database restricted to the EU jurisdiction, for as long as the project runs; you can ask us to delete your games at any time.
**Your rights**: access, rectification, erasure, restriction, portability and objection (GDPR art. 15-21), by writing to the contact above
and quoting the code shown in Settings. You can also lodge a complaint with your data protection authority (in Italy: Garante per la protezione dei dati personali).

## Children

The app is not meant for children under 14.

## Changes

If this notice changes, the new version is published with the app and on its website, with the date above.
