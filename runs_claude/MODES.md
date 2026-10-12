# All-modes campaign (Haiku subagents, started 2026-10-09)

User: "让 subagent haiku 玩所有的 balatro 的 modes 并通关".
One Haiku agent = one run attempt (the game has one pipe client, so runs are serial).
2026-10-10: Haiku went 1/8, Sonnet 0/3 (all lost at Ante 5). Plan now (user 2026-10-10: Haiku and Sonnet unlimited, Opus limited, no Fable): keep attempting each deck on White Stake with a fresh random seed until it wins, alternating Haiku/Sonnet agents (no attempt cap); Black first (a Black win may unlock Checkered). Agents: Haiku with effort=high from the next launch on (user, 2026-10-10); the first Black attempt 2 ran without it. Compare win rate/tokens after ~2 runs.
Order: every deck on White Stake → stakes 2..8 per deck (each stake unlocks from the previous win) → challenges.
Red and Green on White Stake were already won before this campaign.
Locked in this save (new_game returns LOCKED): b_erratic (needs a high-stake win, see sources). b_checkered unlocked 2026-10-10 by the Black win.

| mode | attempts | result | notes |
| --- | --- | --- | --- |
| b_blue / White | 1 | lost (seed BYEVZF24) | Ante 6 The Mouth 17,875 / 40,000; Two Pair L5 + Straight L4, only 5 weak jokers; Mouth zeroes an off-type hand silently |
| b_yellow / White | 1 | WON (seed VL6LYEMH) | Ante 8 Amber Acorn 100,000; Two Pair L8 (Uranus), Spare Trousers + Cavendish + Card Sharp + Burglar + Ramen. Buffoon pack with full joker slots only offers skip: sell a joker first |
| b_black / White | 1 | lost (seed H4YLM4WP) | Ante 8 Big Blind 26,615 / 75,000 (3 hands/round); Pair L5 + Two Pair L7, Constellation/Acrobat/Photograph/Stuntman/Raised Fist/Loyalty Card; only one real xMult scaler |
| b_magic / White | 1 | lost (seed S58BP5PL) | Ante 1 boss The Club 176 / 600; flush plan died to the clubs debuff, only The Tribe + Acrobat, $1 left, spent last money on Acrobat |
| b_nebula / White | 1 | lost (seed UGF4VCR5) | Ante 4 The Mouth 1,836 / 10,000; first hand was a Pair (misread as straight) which locked the blind; skipped Ante 4 small+big for Uncommon tags but never visited a shop to claim them |
| b_ghost / White | 1 | lost (seed LJ9U6PQB) | Ante 4 Big Blind ~2,000 / 7,500; Pair L2 / Trips L2 / Straight L2 spread thin, low-impact jokers (Walkie, Wily, Baron, Card Sharp), no scaling |
| b_abandoned / White | 1 | lost (seed CYY9V3B5) | Ante 5 boss The Wheel 10,677+ / 22,000; Straight L6 + Runner/Scholar/Ramen/Erosion/Loyalty Card, no second xMult scaler |
| b_zodiac / White | 1 | lost (seed 6DNW9R5Z) | Ante 5 Small Blind 8,048 / 11,000; Full House L6 + Blue Joker/Supernova/Odd Todd/Wrathful/Shoot the Moon; sold the wrong joker (Bull instead of Odd Todd) |
| b_painted / White | 1 (Sonnet) | lost (seed F5P6ZMPS) | Ante 5 boss The Serpent 17,134 / 22,000; 4 joker slots, +mult/+chips only (Smiley, Scary, Abstract, Mad), no xMult; Jumbo Buffoon Pack opened with full slots: pick -> SLOTS_FULL, lost The Idol; The Tooth drained cash to $3 |
| b_anaglyph / White | 1 (Sonnet) | lost (seed BPPD797F) | Ante 5 boss The Needle (1 hand) ~<11,000; Flush L7 + The Tribe/Odd Todd/Ancient Joker/Droll/Walkie Talkie; sold Supernova+Blackboard, bought Grabber (+1 hand) instead of saving for xMult; Ancient Joker suit and owned tags are not in the state text |
| b_plasma / White | 1 (Sonnet) | lost (seed JTNNTPD8) | Ante 5 Big Blind 31,587 / 33,000 (missed by 1,413 on the last hand); Full House L6 + Misprint/Mystic Summit/Odd Todd/Flower Pot/Space Joker, one xMult source |
| b_black / White | 2 (Haiku) | lost (seed HCYGMTSB) | Ante 5 boss The House 15,400 / 22,000; Blue/Green/Photograph/Banner/Half Joker/Shoot the Moon, all flat mult, no xMult |
| b_black / White | 3 (Haiku, effort=high) | lost (seed 5VIIS382) | Ante 3 Big Blind (The Window) ~1,086+ / 3,000; spent 3 discards chasing a spade flush, $0 going in, Loyalty Card never triggered, Gros Michel destroyed |
| b_black / White | 4 (Haiku, effort=high) | lost (seed 7JX8EREQ) | Ante 6 boss The Pillar 32,396 / 40,000; Straight L3 + Devious Joker/Fibonacci/Shoot the Moon, last hand only ~2.5k; no free joker slot after Ante 3. Black 0/4 |
| b_blue / White | 2 (Haiku, effort=high) | lost (seed KPP4RTKA) | Ante 5 boss The Wall 39k / 44,000 (wall boss: 44k); Jolly/Ramen/Banner/Half Joker/Supernova, one xMult (Ramen); rerolled to $0 in Ante 1 and missed Shortcut/Green Joker; own score estimates ran 15-25% off |
| b_magic / White | 2 (Haiku, effort=high) | lost (seed 8NYEF5KW) | Ante 4 boss The Plant (faces debuffed) ~8.4k / 10,000; face-card jokers only (Smiley/Scary Face/Photograph), skipped Small Blind for a Boss Tag that rerolled the boss into The Plant |
| b_nebula / White | 2 (Haiku, effort=high) | WON (seed 22BVH6N6) | Ante 8 Crimson Heart 100,000; Two Pair L21 (Telescope + Uranus/Celestial packs + Black Hole), Photograph/Clever/Supernova/Card Sharp/Abstract; 190 commands, 1,597 s |
| b_ghost / White | 2 (Haiku, effort=high) | lost (seed YWBGUXBI) | Ante 4 boss The Mark 3,754 / 10,000; Full House L6 only + flat-mult jokers (Blue/Mad/Even Steven/Swashbuckler/Supernova), no xMult, money $1-16 |
| b_abandoned / White | 2 (Haiku, effort=high) | lost (seed HY992379) | Ante 5 boss The Water (0 discards) ~16.7k / 22,000; Shortcut + Crazy + Blueprint straights carried Ante 2-5, but Banner/Ramen depend on discards and planets were spread over Straight/Pair/Full House/4oak at L2 |
| b_zodiac / White | 2 (Haiku, effort=high) | WON (seed JF6PF8C5) | Ante 8 Amber Acorn 100,000; Straight L12 (Saturn + Black Hole, Planet Merchant/Tycoon) + Acrobat/Fibonacci/Shortcut/Photograph/Swashbuckler |
| b_painted / White | 2 (Haiku, effort=high) | lost (seed IE7KGDMK) | Ante 5 boss The Club 16,909 / 22,000; Photograph/Swashbuckler/Fibonacci/Sly Joker, no xMult; planets spread over Uranus/Venus/Earth/Jupiter; last hands leaned on debuffed clubs |
| b_anaglyph / White | 2 (Haiku, effort=high) | lost (seed 8CX1P8TZ) | Ante 5 boss The Goad (spades debuffed) ~9.1k / 22,000; Straight only L4, one xMult (Loyalty Card), Smiley/Raised Fist/Fibonacci; ~8 rerolls and 5 packs found no xMult |
| b_plasma / White | 3 (Haiku, effort=high) | lost (seed NYL3U9TA) | Ante 8 boss Verdant Leaf (all cards debuffed until a joker is sold) ~44k / 200,000; Two Pair L9 (Telescope), Blueprint+Odd Todd/Supernova/Banner/Splash, no xMult; game screen confirmed GAME OVER although the CLI reported won=True (bug, fixed) |
| b_blue / White | 3 (Haiku, effort=high) | lost (seed TKZHDV8F) | Ante 4 Big Blind 1,601 / 7,500; Full House L5 + Sly/Clever/Ancient/Photograph/Flower Pot, scarce Earth planets, $1-4 for Ante 2-3 after two Small-Blind skips, ~1 hit per blind |
| b_black / White | 5 (Sonnet) | WON (seed Z9DGZ9CQ) | Ante 8 Verdant Leaf 100,000; Pair L8 (Mercury x7) + Ride the Bus (+40, never score a face card) + Burglar (6 hands, 0 discards) + Ramen/Jolly/Misprint/Mail-In Rebate; 178 commands, 2,024 s. Unlocked Checkered |
| b_checkered / White | 1 (Haiku, effort=high) | lost (seed B7KCS9M9) | Ante 7 boss The Fish 28,944 / 70,000; Flush L7 (Jupiter) + Fibonacci/Blueprint/Card Sharp/Odd Todd, no xMult besides Card Sharp, money <$12 after Ante 5 |
| b_checkered / White | 2 (Sonnet) | WON (seed 5XEA1QVE) | Ante 8 Crimson Heart 100,000 (67,840 + Card Sharp x3 flush); Flush L9 (Telescope + Black Hole + Jupiter), Photograph + Hanging Chad + Pareidolia (face-card x2 retriggered: x8) + Scary Face + Card Sharp; ~130 commands |
| b_magic / White | 3 (Haiku, effort=high) | lost (seed SDWCV9A9) | Ante 6 Big Blind 12,594 / 30,000; Full House L3 + Flush L4 (Fool->Jupiter) + Blueprint/Abstract/Card Sharp/Ancient/Walkie; $37 unspent, skipped planet packs without Jupiter, one xMult source |
| b_magic / White | 4 (Sonnet) | lost (seed 72JRVYKQ) | Ante 4 The Flint 897 / 10,000; **play-index slip on the last hand** (typed 0 1 2 5 6 instead of 0 1 2 6 7: lost a ~13k Full House with Blueprint+Acrobat x9), not a build failure. Burglar + Two Pair L6, Blueprint/Acrobat/Photograph; Hieroglyph voucher cost a hand |
| b_ghost / White | 3 (Sonnet) | WON (seed ZYCR5LL2) | Ante 8 Cerulean Bell 100,000 (57k + ~160k in 2 hands); Pair L14 (all planets + Burnt Joker), Blackboard (only black cards held, reds played as kickers) + Blueprint copy (x9) + Card Sharp + Loyalty Card timed for the boss + Swashbuckler |
| b_blue / White | 4 (Sonnet) | lost (seed N6BP418W) | Ante 2 Big Blind 1,050 / 1,200 (852 + lone Ace left); only 2 jokers (Scholar, Constellation) and $0-9, no planet found for a scaling hand, spent $4 on a Standard Pack and skipped two $5 jokers |
| b_abandoned / White | 3 (Sonnet) | WON (seed QVUU3KW9) | Ante 8 Violet Vessel 300,000; Straight L8 (Saturn) + held Steel cards x Mime (x5 with two) + Acrobat x3 on the last hand + Baseball Card/Card Sharp/Ramen; game was killed by Steam at Ante 4 and restored with continue_game |
| b_painted / White | 4 (Sonnet) | WON (seed 6Z2SDQQ2) | Ante 8 (Violet Vessel rerolled by a Boss Tag to Verdant Leaf 100,000); Two Pair L10 (Black Hole + ~8 Uranus), Misprint/Jolly (polychrome)/Stuntman (+250 chips)/Acrobat; bank a Two Pair for the LAST hand (Acrobat x3), burn earlier hands |
| b_blue / White | 5 (Sonnet, bare) | lost (seed 9XV9D51S) | Ante 4 boss The Eye 3,522 / 10,000; Four Fingers/Droll/Walkie Talkie/Square/Crafty; game process died at Ante 2 (pipe ended on a play), recovered with `recover`, hand had not been played; tokens 167.5k = both agents |
| b_magic / White | 5 (Sonnet, full) | WON (seed NIW5PAG5) | Ante 8 Verdant Leaf 100,000 (~120k); Flush L9 (2 Fools copying Jupiter in Ante 1) + Four Fingers + Card Sharp x3 + Acrobat x3 (last hand x9) + Blue/Lusty/Walkie; Hieroglyph; **sold Red Card mid-blind (new hand-phase sell option) to lift Verdant Leaf**; 190 commands |
| b_anaglyph / White | 3 (Sonnet, bare) | lost (seed Q1CVP69I) | Ante 8 boss Verdant Leaf ~10.9k / 100k (small 50k + big 75k cleared); polychrome Flower Pot/Walkie Talkie/Clever/Wrathful, Two Pair + Full House levelled; sold Blue Joker mid-blind to lift the debuff, then no four-suit hand; 180 commands |
| b_plasma / White | 4 (Sonnet, full) | lost (seed 9G1F5583) | Ante 5 boss The Mark 21,048 / 44,000; Straight L4 + Photograph/Even Steven/Mystic Summit/Dusk/Baseball Card, no real xMult (skipped Loyalty Card with full slots); The Mark hid faces and disabled Photograph; 145 commands |
| b_blue / White | 6 (Sonnet, full) | WON (seed MSF77SRR) | Ante 8 Amber Acorn 100,000; Red Card +87 mult (bought cheap packs just to skip them, +3 each) + Runner (+270 chips) + Straight L6 + Fibonacci/holo Scholar/Ramen; Grabber + Paint Brush; 189 commands |
| b_anaglyph / White | 4 (Sonnet, full) | lost (seed JNQWVKUV) | Ante 3 boss The Fish 2,647 / 4,000; Full House L6 + Banner/Juggler/Runner/Flower Pot, only 4 jokers; skipped Ante 3 Small for an Uncommon Tag that gave low-value jokers; hands 2-4 face-down; 62 commands |
| b_plasma / White | 5 (Sonnet, bare) | lost (seed S9P4R67S) | Ante 4 Small Blind < 10,000; Ramen/Half Joker/Fibonacci/Walkie Talkie/Smiley Face + Hieroglyph; 83 commands |
| b_anaglyph / White | 5 (Sonnet, bare) | lost (seed 4ZS658BD) | Ante 5 boss The Needle (1 hand) just short of 11,000 with Four Jacks + glass 7; Even Steven/Ramen/Zany/Splash/Popcorn; 119 commands |
| b_plasma / White | 6 (Sonnet, full) | WON (seed RTH7SSRN) | Ante 8 Amber Acorn 200,000; Straight L13 (Saturn + The Fool) + Shortcut/Crazy + chip jokers Odd Todd/Banner/Blue (Plasma balances chips+mult, so chips are as good as mult) + Wasteful/Recyclomancy/Grabber/Paint Brush; 162 commands |
| b_anaglyph / White | 6 (Sonnet, full) | lost (seed 6E8LCMZ5) | Ante 2 Small Blind 708 / 800; trips-only conditional jokers (Wily/Zany) + Runner/Square, no planets; chased 4-card draws on the last hand; 32 commands |
| b_anaglyph / White | 7 (Sonnet, bare) | lost (seed 5AC1YQ32) | Ante 6 Small Blind 7,254 / 20,000; Madness alone (x6, it destroys the other jokers) + Straight L6; missed the straight with 0 discards; one mis-indexed play at Ante 5; 123 commands |
| b_anaglyph / White | 8 (Sonnet, full) | lost (seed V4XP865T) | Ante 8 Big Blind ~72.6k / 75,000 (2.4k short); Straight L7 + The Order (x3)/Devious/Odd Todd/Even Steven/holo Abstract, one xMult; used all discards hunting straights; a Buffoon Tag pack opened with 5/5 jokers was wasted (no sell offered inside a pack); 207 tool uses |
| b_anaglyph / White | 9 (Sonnet, bare) | lost (seed BHYISRN3) | Ante 4 boss The Wheel 7,032+ / 10,000; Crafty/Lusty/Space/Fibonacci/Wily, no xMult; 85 commands |
| b_anaglyph / White | 10 (Sonnet, full) | lost (seed NN1GX4S8) | Ante 7 Big Blind 44,663 / 52,500; black Flush L7 via Smeared + Blackboard (x3 holding all black) + Gluttonous/Abstract/Photograph, ~35k per flush; **sold a joker inside a Jumbo Buffoon pack (new) and it worked**; 209 tool uses |
| b_anaglyph / White | 11 (Sonnet, bare) | lost (seed Y9WUK2IW) | Ante 6 Big Blind ~2.8k / 30,000; Lusty/Juggler/Droll/Flower Pot/Cavendish; 126 commands |
| b_anaglyph / White | 12 (Sonnet, full) | lost (seed MBHEMK5H) | Ante 7 Big Blind 36,386 / 52,500; Two Pair L7 + Full House L5, Flower Pot x Card Sharp x The Trio + Abstract/Blue (~15-21k per hand); Hieroglyph + Grabber; 241 tool uses |
| b_anaglyph / White | 13 (Sonnet, bare) | lost (seed W3WYMTUZ) | Ante 5 boss The Eye 16,610 / 22,000; Jolly/Supernova/Banner/Smiley/Odd Todd, no xMult; 126 commands |
| b_anaglyph / White | 14 (Sonnet, full) | lost (seed M7HY5NR8) | Ante 7 Big Blind ~50k / 52,500 (~2.5k short); Straight L8 (Telescope) + Shortcut/Crazy/Devious/Abstract/Ramen, ~25k flat per straight, Ramen the only xMult; 146 tool uses |
| b_anaglyph / White | 15 (Sonnet, bare) | WON (seed 8K8TE1AX) | Ante 8 Cerulean Bell 100,000; Two Pair L8 (Uranus) + Cavendish + Blueprint (copying Cavendish) + Card Sharp (second Two Pair x3) + Jolly/Banner; 152 commands |

**2026-10-12: every unlocked deck has now won White Stake (14/14; Erratic still locked).** Next: stakes 2..8.

Agent brief and lessons: [PLAYER.md](PLAYER.md). Machine-readable log: `runs.jsonl` (one row per finished run: run_id, model, effort,
deck, stake, seed, ante, won, commands, duration_s, tokens), `moves.jsonl` (every command, tagged with run_id/model/effort).
Tables: `./bal report` (per mode), `./bal report model` (per model/effort). After a run, orchestrator: `./bal annotate tokens=N tool_uses=N`.

## Ablation: bare brief (PLAYER_BARE.md: commands only, no rules/lessons), Sonnet, decks already won

User asked 2026-10-11 what happens without the harness. Same model, one run per deck; compare with the full brief (variant none) later. Results: `./bal report model` (variant shows as `-/bare`).

| deck | result | notes |
| --- | --- | --- |
| b_red | WON (seed NW6T86AW) | Ante 8 Violet Vessel ~321k; Half Joker + Jolly + Stuntman + The Trio + Cavendish, Pair/Trips + Black Hole; lost Popcorn by opening a Buffoon pack with full slots, picked the wrong pack item (item index vs option index) |
| b_yellow | lost (seed BZV5PF93) | Ante 5 boss The Window 21,640 / 22,000 (short by ~360, last draw gave only 3 Kings); flush build: Droll/Baron/The Duo/Odd Todd/Turtle Bean |
| b_nebula | lost (seed W6G2U6GA) | Ante 8 boss Amber Acorn ~52.8k / 100k (jokers face down and shuffled: Supernova ended after xMult jokers, Loyalty Card x4 not placed); Two Pair L6 + Blue/Supernova/The Duo/Ramen/Loyalty Card. `bal jokers` crashed on hidden jokers (fixed) |
| b_zodiac | WON (seed 38RNAWBF) | Ante 8 Amber Acorn 100,000; Straight L12 (Saturn + Telescope) + Fortune Teller/Crazy/Blue Joker/Mystic Summit/polychrome Ride the Bus |
| b_black | WON (seed FRRU15BY) | Ante 8 Amber Acorn 100,000 (52.7k, 81k, then the kill); Half Joker/Odd Todd/Scary Face/Banner/Red Card (+42)/Gros Michel/Ramen + Grabber; skipped Ante 8 small+big so Gros Michel survived |
| b_checkered | lost (seed P5JJRBRG) | Ante 8 boss Violet Vessel ~150k / 300k (small+big cleared); Flush L14 (Jupiter) + Crafty/Droll/Loyalty Card/Shoot the Moon/Burglar, only Loyalty Card as xMult (rarely fired). Paused at Ante 2 and resumed by a second agent (tokens 126.8k cover only the second half) |
| b_ghost | WON (seed EMAPFRDL) | Ante 8 Violet Vessel 300,000; final hand a Straight (A glass + 2-5); Gluttonous Joker/Hanging Chad/Ancient Joker/Cavendish/Even Steven; 192 commands, 1,573 s |
| b_abandoned | lost (seed 4MX69V1F) | Ante 7 boss The Wheel 26,510 / 70,000 (small+big cleared); Even Steven/Onyx Agate/Juggler/Hack/Ride the Bus, no xMult; 157 commands, 1,405 s |

## Control: full brief (PLAYER.md), Sonnet, same 8 decks

Tagged `variant=full` so `./bal report model` separates it from the earlier full-brief runs on harder decks. PLAYER.md is frozen during the control (new lessons are queued and added after the 8 runs).

| deck | result | notes |
| --- | --- | --- |
| b_red | lost (seed 2VRVVA5L) | Ante 7 Big Blind ~48k / 52,500; Pair via Half Joker + The Duo + Burglar (~8-10k per hand) + Abstract/Gros Michel, Trips L8 unused; Hieroglyph + Paint Brush vouchers; one xMult only |
| b_yellow | WON (seed VYYHMQQ8) | Ante 8 Cerulean Bell 119k / 100k; Straight L9 (Saturn + The Fool) + The Order (x3) / Acrobat / Devious / Abstract / Turtle Bean / negative Crafty; Turtle Bean +5 hand size beat The Water; 194 commands, 1,356 s |
| b_nebula | lost (seed L9B2D82L) | Ante 3 boss The Goad 3,596 / 4,000; skipped Ante 3 Small+Big for Rare/Holo tags and arrived with Bull/Flash Card/negative Smiley, Two Pair L5, ~$3; 55 commands |
| b_zodiac | WON (seed 2987GT1A) | Ante 8 Crimson Heart 100,000; Flush L10 (Star tarots + Jupiter) + Mystic Summit/Photograph/Hanging Chad (face card first: ~46k)/Card Sharp/Troubadour + Grabber; 243 commands, 1,993 s |
| b_black | lost (seed XGUYZ1R4) | Ante 7 Big Blind ~5.3k+ / 52,500 (missed Full House on the last two hands); Full House L7 + 2x Mystic Summit (Invisible Joker)/Zany/Wily/Misprint/foil Acrobat, Acrobat the only xMult; 170 commands |
| b_checkered | lost (seed ZLAS4JID) | Ante 8 boss Cerulean Bell ~48.6k best hand / 100k (small+big cleared); Flush L15 + Blackboard (x3, hearts flush holding spades ~60k) + Blue/holo Green/Raised Fist/Space Joker; the Bell forced card broke the Blackboard hold; 178 commands |
| b_ghost | lost (seed 2PJZZXBB) | Ante 8 boss Verdant Leaf ~23k / 100k (small+big cleared); single-even-card engine Stuntman/Hanging Chad/Even Steven/Wee Joker + Constellation, all card-triggered so Verdant Leaf zeroed it; CLI has no sell-during-blind option; 191 commands |
| b_abandoned | lost (seed DDEPM641) | Ante 4 boss The Wall ~12.4k / 20,000; Half Joker 2-card pairs + Supernova/Crafty/Mystic Summit/Scholar, no xMult, Flush L3 only; 90 commands |

**Ablation result (2026-10-11, Sonnet, same 8 decks, one run each):** bare 4/8 wins (avg ante 8.0, avg 219.1k tokens) vs full 2/8 (avg ante 6.9, avg 174.0k). Same decks won by both: Zodiac only. n=8 each is too small to call (Fisher exact p≈0.6), but the long lesson list is at least not clearly helping. Queued lessons from the control are in `LESSONS_QUEUE.md` (not merged). Next: hard White decks (Blue/Magic/Anaglyph/Plasma) alternating bare and full, which grows both samples while chasing the wins.

## Stakes 2..8 (started 2026-10-12)

Stake numbers: 2 Red (Small Blind pays $0), 3 Green, 4 Black, 5 Blue, 6 Purple, 7 Orange, 8 Gold. Alternating full/bare briefs, Sonnet.

| mode | attempt | result | notes |
| --- | --- | --- | --- |
| b_red / Red Stake (2) | 1 (Sonnet, full) | lost (seed 7Z1VGFT5) | Ante 6 boss The Manacle 34,332 / 40,000; Pair L7 + Half Joker/Sly/Even Steven/Mystic Summit/Gros Michel, no xMult at all (~11k per pair) |
| b_red / Red Stake (2) | 2 (Sonnet, bare) | lost (seed G6A1SAW5) | Ante 5 Big Blind 5,744 / 16,500; Supernova/Hanging Chad/Banner/Even Steven/Droll, Flush L2; spent all discards chasing a straight |
| b_red / Red Stake (2) | 3 (Sonnet, full) | lost (seed 3FXY16X7) | Ante 7 boss The Goad ~35k / 70,000; 2-card Pair via Half Joker + Joker Stencil (x2-x4) + Hallucination + The Duo + negative Wrathful, Pair L6 / Trips L7, ~17k per hand at Ante 7 |
| b_red / Red Stake (2) | 4 (Sonnet, bare) | lost (seed IYAP3M5T) | Ante 5 Small Blind 5,000 / 11,000; Crafty/Sly/Photograph/Red Card/Smiley, no xMult beyond Photograph |
| b_red / Red Stake (2) | 5 (Sonnet, full) | lost (seed 241PY1CJ) | Ante 5 boss The Tooth ~18-19k / 22,000; skipped every Small Blind (+ two Big Blinds) for tags; Four Fingers flush/straight + Mystic Summit/Supernova/Splash, no xMult, planets spread over Straight/Flush/SF (~5-6k per hand) |
| b_red / Red Stake (2) | 6 (Sonnet, bare) | lost (seed QPTUCQP3) | Ante 3 boss The Hook 3,760 / 4,000; only Sly Joker + Ramen |
| b_zodiac / Red Stake (2) | 1 (Sonnet, full) | lost (seed W1425P7I) | Ante 5 boss The Fish 10,594 / 22,000; trips/Full House with Zany/Wily/Blue/Rocket/Swashbuckler, no xMult (~6k per hand); skipped Ante 5 Small+Big. Found: buy options ignored Credit Card (fixed in game.py) |
| b_zodiac / Red Stake (2) | 2 (Sonnet, bare) | lost (seed B2E1BG6T) | Ante 4 Big Blind ~3.6k / 7,500; Banner x2 (Invisible Joker)/Photograph/Juggler/Loyalty Card |
| b_zodiac / Red Stake (2) | 3 (Sonnet, full) | lost (seed WZVG4Z5Z) | Ante 4 boss The Wall ~7.5-9k / 20,000; Raised Fist/Even Steven/Supernova/Golden/Splash, no xMult, planets spread; skipped Ante 4 Small+Big into the Wall against the brief |
| b_yellow / Red Stake (2) | 1 (Sonnet, bare) | lost (seed 71HN4417) | Ante 5 Small Blind ~8.4k / 11,000; Wily/Splash/Zany/Greedy/Misprint, no xMult |
| b_yellow / Red Stake (2) | 2 (Sonnet, full) | lost (seed H12WNWTT) | Ante 4 boss The Fish 9,212 / 10,000; Straight L4 + Droll/Crazy/Devious/Dusk/Obelisk (dead), $1 into the boss; Boss Tag rerolled The Arm into The Fish |
| b_yellow / Red Stake (2) | 3 (Sonnet, bare) | lost (seed 6Q3L19C2) | Ante 5 Big Blind ~15.7k / 16,500 (~800 short); Shoot the Moon/Mystic Summit/The Tribe/Joker/Juggler |
| b_plasma / Red Stake (2) | 1 (Sonnet, full) | **WON** (seed 8FL1LTT5) | Ante 8 Crimson Heart 200k with one Broadway Straight; Straight L15 + Runner/polychrome Space/Bull (chips = mult on Plasma)/Card Sharp/Acrobat; Grabber + Paint Brush + Palette + Seed Money. First Red Stake win (13th attempt overall) |
| b_plasma / Green Stake (3) | 1 (Sonnet, bare) | lost (seed YV7CTIBQ) | Ante 3 boss The Eye 8,942 / 10,400; Mail-In/Reserved Parking/Even Steven/Smeared, economy jokers, no scaling |
| b_plasma / Green Stake (3) | 2 (Sonnet, full) | **WON** (seed MTXKQRS6) | Ante 8 Cerulean Bell 400k with one Loyalty x4 hand copied by Blueprint (x16); Pair L12 + Banner/Drunkard/Odd Todd/Ride the Bus (+53)/negative Loyalty Card; counted hands so the 6th-hand Loyalty landed on bosses |
| b_plasma / Black Stake (4) | 1 (Sonnet, bare) | lost (seed 6JPJJ1A1) | Ante 4 boss The Goad ~23.7k / 32,000; Jolly/Fibonacci/Square/Half Joker/Gros Michel |
| b_plasma / Black Stake (4) | 2 (Sonnet, full) | lost (seed PIQBDINM) | Ante 4 boss The Needle (1 hand, 16,000); gambled on a 4-out straight, held Uranus/2 Jupiter unused; Hiker/Supernova/The Idol/Ice Cream/holo Perkeo |
| b_plasma / Black Stake (4) | 3 (Sonnet, bare) | lost (seed 4ZE32EXZ) | Ante 5 boss The Wall ~85k / 160,000; Odd Todd/Stuntman/Card Sharp/Jolly/Abstract |
| b_plasma / Black Stake (4) | 4 (Sonnet, full) | lost (seed BQ7HQXZB) | Ante 7 boss The Plant ~95k / 240,000 (faces debuffed); Photograph + Hanging Chad (x8 on a face-led hand, x16 with Red seal) + Cavendish + Throwback (10 skipped blinds) + Eternal holo Green Joker; face build had no non-face fallback |
| b_plasma / Black Stake (4) | 5 (Sonnet, bare) | lost (seed CQJZ3NMT) | Ante 6 Big Blind 66,153 / 108,000; Two Pair (Uranus) + Clever/Mad/Card Sharp, ~25k per hand |
| b_plasma / Black Stake (4) | 6 (Sonnet, full) | lost (seed W69BU3AV) | Ante 6 boss The Needle (1 hand, 72,000); Flower Pot x3 + Four Fingers straights (~45-70k when all 4 suits score), Straight L7; Eternal Riff-Raff blocked a slot (shop items now show [eternal]) |
| b_plasma / Black Stake (4) | 7 (Sonnet, bare) | lost (seed ZBVH9RZ3) | Ante 4 Small Blind 10,610 / 16,000; Raised Fist/Joker/Sly/Jolly |
| b_plasma / Black Stake (4) | 8 (Sonnet, full) | lost (seed S12CJF2C) | Ante 7 boss The Eye 130,257 / 240,000; Straight L8 + The Order with Blueprint (x9) + Shortcut/Burglar/Card Sharp, 80-125k per straight; one hand type cannot beat The Eye (did not use Straight Flush L6 as the second type) |
| b_plasma / Black Stake (4) | 9 (Sonnet, bare) | lost (seed PLEV2QWD) | Ante 4 Small Blind <16,000 |
| b_plasma / Black Stake (4) | 10 (Sonnet, full) | lost (seed EXS9YA5L) | Ante 5 Big Blind 40,974 / 60,000; Flush L8 (Black Hole) + 2 Eternal jokers (Half, Greedy) locking slots, Mad/Banner/Loyalty (never fired); Seltzer + Gros Michel spikes ran out; no xMult |
| b_plasma / Black Stake (4) | 11 (Sonnet, full) | lost (seed 9QR5LZMY) | Ante 4 Small Blind 8,069 / 16,000; The Trio only xMult, no levels; Ouija (-1 hand size) did not pay off |
| b_plasma / Black Stake (4) | 12 (Sonnet, full) | lost (seed 89V119KX) | Ante 2 boss The Water ~1,100 / 3,600; all hands L1, unbought planets, The Trio/Hack/Runner/Green; [eternal] tag confirmed visible in shop |
| b_plasma / Black Stake (4) | 13 (Sonnet, full) | lost (seed 57FPST9Y) | Ante 5 boss The Manacle ~46k / 80,000; Pair L7 + Banner/Shoot the Moon/Bull (all eternal)/Jolly/Delayed Gratification, no xMult; skipped Ante 5 Small+Big straight into the boss (CLI now marks the Big-Blind skip "next stop is the BOSS") |
| b_plasma / Black Stake (4) | 14 (Sonnet, full) | lost (seed 5YXTVSIH) | Ante 3 boss The Arm ~5.7k / 10,400; Gros Michel/Juggler/eternal holo Wrathful/Misprint/Devious, only Pair L2, no xMult |
| b_black / Red Stake (2) | 1 (Sonnet, full) | lost (seed ZX15U7ZI) | Ante 4 boss The Club ~6.9k / 10,000; Four Fingers flush/straight + Mystic Summit/Raised Fist/Vagabond/Juggler/Square, no xMult; skipped Ante 4 Big for a Meteor tag with $1 |
| b_ghost / Red Stake (2) | 1 (Sonnet, full) | **WON** (seed XMCCXZP7) | Ante 8 Verdant Leaf 100k; Pair L9 (Telescope) + Burglar (no discards) + Mystic Summit (always on) + Green Joker (+56) + Loyalty Card timed on bosses + foil Sly |
| b_ghost / Green Stake (3) | 1 (Sonnet, full) | lost (seed 497AB75S) | Ante 3 boss The Mouth 2,240 / 5,200; opened with a Straight under The Mouth and never redrew one; no planets used, flat-mult jokers only, $0-8 |
| b_ghost / Green Stake (3) | 2 (Sonnet, full) | lost (seed 1CT5R4VV) | Ante 5 Big Blind ~11.5k / 30,000; Pair L4 + Blackboard x3 + Flower Pot x3 + Supernova/Ride the Bus, $0-7 all run. Found: shop hid a $0 Negative joker with full slots (fixed in game.py) |
| b_ghost / Green Stake (3) | 3 (Sonnet, full) | **WON** (seed 939255GE) | Ante 8 Verdant Leaf 200k (sold Mystic Summit mid-blind); Straight L13 (Telescope + Saturn every shop) + Shortcut/Runner (+450)/Card Sharp/Ramen; played every blind |
| b_ghost / Black Stake (4) | 1 (Sonnet, full) | lost (seed 7MX1HTMN) | Ante 5 boss The Hook 5,314 / 40,000; Straight L7 + Baron (needs Kings held) + foil Devious/poly Erosion/Misprint/eternal Loyalty (bought too late), $3-12 all run |
| b_ghost / Black Stake (4) | 2 (Sonnet, full) | lost (seed 59Y353C8) | Ante 6 boss The Wall ~46k / 144,000 (small+big cleared); Straight L5 / SF L4 via Four Fingers + Sigil, Mystic Summit/Abstract/Misprint/eternal Loyalty, ~25k per hand; Loyalty x4 landed on the Big Blind not the Wall |
| b_ghost / Black Stake (4) | 3 (Sonnet, full) | lost (seed P6J77IH1) | Ante 5 Big Blind 1.2k / 30,000; one-type Straight build (L3) with a single xMult (The Order), eternal Odd Todd/Dusk filled slots; missed the straight draw |
| b_blue / Red Stake (2) | 1 (Sonnet, full) | lost (seed 9MV367V1) | Ante 7 boss The Psychic ~52k / 70,000; Blackboard + Onyx Agate club build, Half Joker 2-3 card Pair dead on Psychic, Acrobat; Flush L4 / Three L4 |
| b_blue / Red Stake (2) | 2 (Sonnet, full) | lost (seed 72NJTZNS) | Ante 3 boss The Wheel ~600 / 4,000; flat build (Supernova/Even Steven/Greedy/Green/Ride the Bus), no xMult; burned discards digging face-down cards |
| b_magic / Red Stake (2) | 1 (Sonnet, full) | lost (seed PXYP9S4Z) | Ante 4 Small Blind ~4.5k / 5,000; Straight L5 via planet + 2 starting Fools, Flower Pot/Juggler/Hiker/Even Steven, no reliable xMult; no 10 drawn |
| b_checkered / Red Stake (2) | 1 (Sonnet, full) | lost (seed W53YPZ3S) | Ante 6 Big Blind ~29.0k / 30,000; Flush L3 + Four Fingers + The Duo (4 suited + pairing off-suit card), Crafty/Dusk/Mail-In Rebate; only one x2, money under $10 from Ante 4 |
| b_checkered / Red Stake (2) | 2 (Sonnet, full) | lost (seed RH4AW88B) | Ante 5 Big Blind ~5.2k / 16,500; Half/Zany/Jolly + polychrome Faceless + Card Sharp, Three of a Kind L5; last hand played a Pair while holding trips; sold Ice Cream |
| b_nebula / Red Stake (2) | 1 (Sonnet, full) | lost (seed 6U8RLJQX) | Ante 8 boss Verdant Leaf ~87k / 100,000; Pair L10 via Telescope Mercury, Half Joker/Banner/Ramen/Acrobat; ~14k per pair, 43k Acrobat final; only one real xMult |
| b_nebula / Red Stake (2) | 2 (Sonnet, full) | lost (seed QVGCM69K) | Ante 6 boss The Head ~27.9k / 40,000; Straight L3 via Shortcut + Telescope, Mystic Summit/Popcorn/poly Riff-Raff/Ancient Joker; ~12-15k per straight, one xMult |
| b_nebula / Red Stake (2) | 3 (Sonnet, full) | **WON** (seed 95FU2CCJ) | Straight L14 via Telescope + Saturn + The Fool, Four Fingers/Devious/Supernova/Baseball Card/Acrobat; burned 1-card hands, kept a 5-card straight for Acrobat on Crimson Heart |
