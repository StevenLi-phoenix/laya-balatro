# Balatro: play one run

You play one full run of Balatro through a CLI. Goal: win the run. Start exactly one run, play it to the end
(a game over or `*** WON`), then stop. Do not edit files.

Command prefix (call it BAL): `/d/Documents/Codes/balatro-gameplay/laya-player/bal`

- `BAL new deck=<deck> stake=<stake> model=sonnet variant=bare` - start the run (once).
- `BAL show` - the current state, your hand with indices, and numbered options.
- `BAL play i j ..` / `BAL discard i j ..` - hand card indices (max 5 cards).
- `BAL do N '<expected option text>'` - take option N; pass its text in single quotes.
- `BAL use SLOT t1 t2` - use a consumable on hand cards. `BAL pick N t1 t2` - take pack item N (with targets).
- `BAL jokers 2 0 1` - reorder jokers by old slot index.

Final answer (short): deck, seed, won or lost, ante reached.
