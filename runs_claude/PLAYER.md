# Balatro player brief (read this first, then play ONE run)

You play one full run of real Balatro (running on this PC) through a CLI bridge. Goal: win (beat the Ante 8 boss).
The orchestrator tells you the deck, stake, model and effort. Do not edit files; only run the CLI. Start exactly one
run (`new`), never enter endless mode, never start a second run. Stop at `GAME OVER` or `*** WON`.

## Commands (use the wrapper; it handles cd and utf-8)

`/d/Documents/Codes/balatro-gameplay/laya-player/bal <command>` (call it BAL below)

- `BAL new deck=b_xxx stake=1 model=<haiku|sonnet|...> effort=<high|-> ` - start the run once, with the labels you were given.
- `BAL show` - state text, HAND (index: card), JOKERS, PACK, numbered OPTIONS.
- `BAL play i j .. expect=KKK33` / `BAL discard i j ..` - hand card indices (max 5). ALWAYS add `expect=` with the ranks you intend (T = 10, ? = a face-down card, order free): it refuses on an index slip (a Sonnet Magic run lost its last hand by typing wrong indices). A played hand cannot be undone.
- `BAL pick N t1 t2` for any targeted tarot/spectral from a pack (the `do` form fails for those).
- `BAL do N "<expected option text>"` - take listed option N. Always pass the expected text in single quotes (it may contain
  parentheses or $); options re-index after every action and the guard refuses a mismatch. Never chain two `do` without reading the output.
- `BAL use SLOT t1 t2` - consumable on hand-card targets. `BAL pick N t1 t2` - pack item N. `BAL jokers 2 0 1` - reorder jokers.

Every command prints the new state, so a separate `show` is rarely needed. Decide from the state text only.

## Rules

- Quote option text with SINGLE quotes, e.g. `BAL do 3 'buy joker X $5'`: in double quotes bash expands `$5` to nothing and the guard rejects.
- Hand indices shift after each draw: re-read before every play/discard.
- Before every sell/buy re-read the current option list: the guard only checks the text you typed, so selling the wrong joker is not caught.
- Many actions return "timed out" but applied: check the state before retrying. On a pipe/bridge error wait a few seconds and `show`; after 5 failures stop and report.
- If the game crashed or was closed (pipe error that does not clear): run `BAL recover` (relaunches Balatro and continues the saved run, usually from the start of the current blind), then `BAL show` and keep playing the SAME run; never `new`.
- `new` returns `LOCKED` for decks not unlocked in this save (b_checkered, b_erratic): stop and report.
- After the final winning hand `cash_out CANNOT_USE_NOW` can appear; ignore it.

## Lessons (from runs in MODES.md)
- Won (Nebula, Haiku): Two Pair to L21 (Telescope voucher guarantees the planet of your most-played hand; Uranus/Celestial packs/Black Hole), Photograph x2 + Card Sharp x3 on the repeated hand type; the first Two Pair of a blind scored 20-50k, the second finished it.
- A planet bought in the shop sits in a consumable slot: apply it with `use`. A Mega pack with 2 picks needs two separate `pick` calls.
- Won (Yellow): one hand type (Two Pair) levelled to L8 with its Planet cards + several xMult jokers (Cavendish, Card Sharp, Ramen) + a +mult scaler.
- Ante 8 blinds need ~75k-100k+: have MULTIPLE xMult jokers by Ante 4-5 (Black lost with one). Don't spread Planets over several hand types (Ghost lost at Ante 4 with Pair/Trips/Straight all L2).
- Buy sturdy generic scoring jokers first; check the upcoming boss before committing to a suit (Magic lost Ante 1 to The Club debuffing its clubs); keep a few dollars.
- Before playing on a hand-type-locking boss (The Mouth), verify the exact hand type: a straight needs 5 consecutive ranks. Nebula locked itself to Pair by misreading J-10-9-9.
- Skip tags only pay out in a shop; do not skip when the next stop is a boss, and do not skip just to skip.
- Quote the expected option text in the shell when it has parentheses, e.g. `do 3 "take card 9♥(mult)"`.
- Before every sell/buy re-read the current option list: the guard only checks the text you typed, so selling the wrong joker (Zodiac sold Bull instead of Odd Todd) is not caught.
- Boss The Needle allows ONE hand: only a big single hand wins it (extra hands from Grabber/Burglar are useless there); plan scoring per single hand from Ante 4.
- Do not build only on face-card jokers (Smiley/Scary Face/Photograph): The Plant debuffs all faces. A Boss Tag rerolls the boss and can make it worse; check what it does to your build first.
- Discard-dependent jokers (Banner, Ramen, Burglar) collapse on The Water (0 discards); have a scorer that works without discards by Ante 4-5.
- Won (Zodiac, Haiku): Straight to L12 (every planet into Straight) + Acrobat x3 on the final hand + Fibonacci/Shortcut/Photograph.
- The Psychic: a play of fewer than 5 cards scores 0 and uses a hand. With Shortcut a straight may skip at most one rank per link (A-K-10-9-8 skips J and Q: not a straight). Ramen decays 0.01 per discard and is destroyed at X1.
- Verdant Leaf (Ante 8 boss): all cards are debuffed until you SELL a joker; `sell joker` options are listed during the blind too (since 2026-10-11), so sell your weakest joker before the first hand. Debuffed hands still score their base hand level + jokers: a levelled hand (Pair L8, ~37k) beats it, but a weak build (Two Pair L9 without xMult, Plasma) does not.
- Won (Black, Sonnet): Burglar (+3 hands, no discards) + Ride the Bus (never score a face card: play the pair plus junk/faces as non-scoring kickers) + Pair planets; Handy/Investment/Polychrome tags paid. Before skipping for a joker-pack tag, sell a joker first (SLOTS_FULL wastes the free pack). Face-down boss cards can be deduced from the remaining-deck counts in the state text.
- Won (Checkered, Sonnet): Flush L9 via Telescope (every Celestial pack has Jupiter) + Photograph x2 retriggered by Hanging Chad (x8) with Pareidolia (all cards are faces) + Scary Face + Card Sharp; lead with a real K/Q/J as the first played card. Spending down to ~$25 keeps interest.
- Won (Ghost, Sonnet): Pair to L14 (every planet + Burnt Joker) + Blackboard (hold only spades/clubs; discard held reds first, play reds as kickers) + Blueprint left of it (x9) + Card Sharp. Loyalty Card fires on every 6th hand since purchase: steer the hand count (or skip blinds) so the x4 lands on a boss; its counter and The Idol's target show only as "?" in the state text.
- Won (Abandoned, Sonnet): Straight L8 + Steel cards held in hand (Chariot/Standard packs) retriggered by Mime (two held steels = x5) + Baseball Card (x1.5 per uncommon joker) + Acrobat x3 on the last hand: burn hands 1-3 with 1-card plays, play the real hand last. Selling a NEGATIVE joker removes its own slot (no free slot). The CLI has no boss-reroll command, so Director's Cut/Retcon vouchers are wasted.
- Won (Painted, Sonnet): Two Pair L10 (Black Hole + Uranus only) + Acrobat x3: bank a Two Pair for the LAST hand, burn earlier hands as pair/high card (under The Mouth an off-type burn hand scores 0 but still uses a hand). Stuntman +250 chips is worth -2 hand size. If the Ante 8 boss is Violet Vessel (300k), skipping the Big Blind for a Boss Tag rerolls it (to Verdant Leaf 100k here); the reroll happens with no extra command.
- Amber Acorn (Ante 8 boss) flips all jokers face down and shuffles them at the start of the blind: additive jokers (Supernova) must sit before xMult ones, so set the order in the shop before the boss and expect it to be shuffled; Loyalty Card timing is lost. `BAL jokers` now works with hidden jokers.
- Joker pack (Buffoon/Jumbo/Mega, bought or from a tag) with full joker slots: pick returns SLOTS_FULL. Since 2026-10-12 `sell joker` options are listed INSIDE an open pack too: sell your weakest joker there, then pick. After the final winning hand `cash_out CANNOT_USE_NOW` can appear; ignore it.

## Lessons from the 2026-10-12 runs (merged from LESSONS_QUEUE.md)
- The #1 cause of losses: still one (or zero) xMult joker at Ante 5. By Ante 4-5 own 2+ xMult sources (Cavendish, Card Sharp, The Order/Duo/Trio, Blueprint copying an xMult, Loyalty Card, Acrobat); flat +chips/+mult builds cap near 10-25k per hand.
- Card Sharp + Acrobat: play the main hand on hand 1, again on hand 2 (x3), and on the last hand (x9). Loyalty Card + Blueprint left of it = x16 every 6th hand: count hands and reorder with `BAL jokers` (works mid-blind) so it lands on the boss.
- The Fool copies the last planet used: buy/use a planet, then The Fool, for a cheap extra level. Telescope makes every Celestial pack contain your most-played hand's planet.
- One-hand-type builds die to The Eye (no repeated hand types). Straight and Straight Flush are different types; keep a second levelled type or an unconditional xMult by Ante 6. Photograph/face builds die to The Plant: have a non-face fallback by Ante 7.
- The Needle allows ONE hand: never gamble on a draw there; use held planets first and keep a made hand that clears the target.
- Plasma Deck: score is roughly ((chips+mult)/2)^2, so flat +chips jokers (Bull, Runner, Odd Todd, Banner, Blue Joker) are as good as +mult.
- Red Card + buying cheap packs just to skip them = +3 mult per skip. Fibonacci prefers low straights (A-5, 2-6).
- Cerulean Bell: the forced card must be in every play AND every discard (discarding it re-rolls it); it breaks held-card setups like Blackboard. The Fish: discard first (discard draws are face up), play the big hand first. The Arm lowers the played hand's level. The Ox zeroes your money when you play your most-played hand.
- Debuffed cards still count toward the hand type (they only lose their own chips/effects). Played cards score left to right in HAND order, not in the order you typed the indices: "first played card" = leftmost.
- Do not skip both Small and Big while the build is weak; a skip tag that opens a joker pack needs a free slot (sell inside the pack). Sell options are listed during blinds and inside open packs.
- Higher stakes: Small Blind pays $0 from Red Stake on; shop jokers marked [eternal] can never be sold (Black Stake+): only buy them if you want them forever. Credit Card lets you spend to -$20.

## Lessons from the Red/Black Stake runs (2026-10-12, second merge)
- Red Stake targets: Ante 3 ~4k, Ante 4 5k/7.5k/10k, Ante 5 ~11k/16.5k, Ante 6 Big 30k. Black Stake is higher still (Ante 5 20k/30k/40k). A levelled hand with only flat jokers caps ~4k; one x2/x3 plus flat jokers caps ~25-30k. By Ante 3 buy ANY xMult joker (keep $10+ and reroll for it); by Ante 5 own two.
- Joker order matters: +mult jokers LEFT of xMult jokers. `BAL jokers ...` only works during a blind (WRONG_PHASE in shop / blind select).
- Before every play, re-scan the whole hand for the best hand type (a Red Stake run lost holding trips while playing a Pair).
- Skipping Small (pays $0 at Red Stake) also skips that shop: only skip for a tag you will use (Economy, Polychrome, a pack tag with a free slot), never for junk Voucher/Rare tags.
- 2-3 card builds (Half Joker) die to The Psychic (exactly 5 cards); have a levelled 5-card hand by Ante 6.
- The Wheel / face-down cards: keep a made hand before spending discards; never guess face-down ranks; discard them (replacements come face up). In `expect=` a face-down card is `?`.
- No discards left: playing 1-4 junk cards draws replacements (dig for a missing rank); keep the final hand for Dusk.
- Magic Deck: buy and use a planet, then both starting Fools copy it = main hand +3 levels in the first shop.
- Four Fingers + The Duo: 4 suited cards + an off-suit card pairing one of them = a Flush containing a Pair (x2). Skip planets for hand types your xMult cannot combine with.
- Wild cards count as clubs for Blackboard/Onyx Agate; play red cards as kickers to keep the held hand black.
- Ghost wins: Burglar + Mystic Summit + Green Joker (no discards keeps Summit on); Shortcut + Telescope + Saturn every shop to Straight L13, with Card Sharp.
- Tool: one `BAL do` per tool message (indices shift after each action); play/discard take at most 5 cards.

## Final answer (short)

Mode, seed, won or lost, ante reached, final jokers, main hand type, any tooling problem. The CLI already logs the
run (run_id, model, effort, commands, duration) to runs.jsonl; the orchestrator adds tokens afterwards.
