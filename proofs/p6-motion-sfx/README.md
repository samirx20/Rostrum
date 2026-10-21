# P6 · Motion-design sound effects: designed, shaped by the motion

**Question.** Sam heard the slide-deck style effects (swishes, clicks) as cheap. Can designed sounds, shaped by the
picture's own motion and glued on one bus, beat one stock take dropped on every move?

**Verdict: pass with conditions, Sam to listen.** Every sound now has the shape of the move it follows. Each whoosh is
loudest within one frame of its card's fastest moment, and every click and tick lands within 0.1 ms of its event. With
the stock take, the whoosh peaks 0.2 to 0.36 s after the card's fastest moment, even after trimming the take's silent
start by hand. Conditions: it is untested by ear (the bar is Sam's ear against an Apple launch film), and the motion
reaches the Sound app through a sampler in this proof until Rostrum2D hands it over itself.

## Why the old sound was cheap (checked, not assumed)

1. **One take for every move.** It was the same 1.85 s "Fast Swoosh" on a slow 0.66 s slide and on a 0.2 s flick. It
   is silent for 0.95 s and peaks 1.31 s in. Placed at the move's start, it peaked 0.3 to 1.0 s late, and the flick was
   over before it was heard. Takes overlapped into a smear at the exits.
2. **Basic packs.** The kenney clicks and ticks are single bare samples. Ten identical ticks sound copy-pasted.
3. **Not layered, not glued.** It was one sample per event, all centred, with no shared space.

## What was built (Package A)

- **Engine** (`apps/sound/engine/src/design/`): `whoosh.rs`, `click.rs`, `big.rs` (riser, hit, sub drop), and the one
  field table in `mod.rs`. The contract (`contract/designed.rs`) adds a track's `sounds` list, documented in
  ENGINE_CONTRACT.md › Designed sounds. A whoosh's `speed` curve drives its level, sweep and air, and `panPath` moves it
  with the object.
- **Sound document**: a `sound` item (`sound.add / add_many / set / remove`). Each design's own fields are valid only
  while that design is chosen (rule of individuality). A value outside a design's own range is refused.
  `Engine.check_names` compares the Python table with the engine's `describe`.
- **Motion → sound** (`rostrum_sound/motion/`): `read.py` reads the motion data and finds moves (with their speed
  curve), landings, snaps, presses and steps. `score.py` gives each one a matched sound as a starting point, plus the
  `ui` glue bus (short room, light compressor). MCP tool: `edit_sounds_from_motion`. Guide: `designed-sounds`.
- **Library recordings:** none used in the new score. The designed sounds beat the installed kenney and freesound
  UI takes because they take the move's shape and timing, which a fixed recording can't. Sonniss GDC bundles were not
  downloaded.

## The proof (Package B)

Our own 10 s slide deck (`slides.py`, made through the rostrum2d script layer): a title snaps in, four cards slide in
(one slow and big from the left, a flick from the right, a snap with an overshoot, one rising), a counter ticks 0 to 9,
a button is tapped, and all four cards leave.

| File | What |
|---|---|
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-motion\slides-old-sfx.mp4` (+ `.wav`) | The old way: one stock take per event (freesound 171321 whoosh trimmed to its start, kenney click / tick / mouse click) |
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-motion\slides-new-sfx.mp4` (+ `.wav`) | The new way: designed sounds from the motion, glued on the ui bus |
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-motion\slides-silent.mp4` | The picture alone |

Both mixes are at −16 LUFS.

### What to listen for

| Time | Picture | Old | New |
|---|---|---|---|
| 0.3 s | title snaps in | a bare click | a bright click with a breath of air before it and a small thump under it |
| 1.0 s | big card slides in from the left, slowing | a whoosh that arrives late, centred | a darker, fuller whoosh, already at speed as it enters, fading as the card settles, moving from left to centre |
| 2.6 s | small card flicks in from the right | the same whoosh, late and long | a short, bright cut on the right, over in 0.2 s |
| 3.4 s | card snaps in and overshoots | the same whoosh | a fast, bright whoosh, and a click at the moment it hits its place |
| 4.2 s | card rises from below | the same whoosh | a softer whoosh that peaks in the middle of the rise |
| 5.0–6.8 s | counter ticks | ten identical ticks, about 25 ms late | ten tight glassy ticks on the frame, each slightly different |
| 7.48 s | button tapped | one mouse click | a soft press, then a lighter, higher release |
| 8.2–9.4 s | cards leave | four late whooshes smeared together | four whooshes rising to the edge and flying off, each on its own side |

### Sync (measured with `check_sync.py`; one frame = 33 ms)

- **New, sharp sounds:** worst 0.1 ms on 14 events. This was measured on the click and tick tracks alone, because in
  the full mix a whoosh's swell hides a click's start from the onset tool.
- **New, whooshes:** the loudest moment is within 6 to 31 ms of the card's fastest moment.
- **Old, whooshes:** 206 to 356 ms late on the entrances, with the take trimmed to its first sound.

### Timings and machine

The engine build took 66 s the first time and 13 to 15 s after a change. Rendering a 10 s mix takes 0.4 to 0.5 s on
the CPU, with no GPU and no model. The 2D render ran once through `heavy.ps1` (gpu).

## Files

`slides.py` and `make_video.py` (the deck), `sample_motion.py` (the motion as data, through Rostrum2D's own
evaluator, read-only), `score_old.py`, `score_new.py`, `mux.py`, `check_sync.py`.

## Attribution rows

No new dependencies. The old-way score uses installed library takes for comparison only (nothing shipped):
freesound 171321 "Fast Swoosh" by swidmark (CC0-1.0, https://freesound.org/people/swidmark/sounds/171321/), kenney-interface `click_002.ogg` and
`tick_004.ogg`, kenney-ui `mouseclick1.ogg` (CC0).
