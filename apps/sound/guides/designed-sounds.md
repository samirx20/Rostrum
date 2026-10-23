# Designed sounds, and scoring motion

Rostrum makes no whooshes, swishes or "transition" sounds, and will not. A move on screen is answered with **music**
(an instrument) or a **real recorded sound**, or with nothing. Silence beats a mediocre sound.

## Answering a move with instruments

| What happens in the picture | An answer, with instruments |
|---|---|
| Something builds toward a landing | A string rise, a cymbal swell or a piano run that ends on the landing's marker |
| Something lands | A hit or a note on the beat of the marker: a struck bell, a low piano note, a drum stroke |
| A title or logo appears | One held note or chord, a bell or soft keys, starting on its marker |
| A big change of scene | A cymbal swell into it, or a held silence just before it |
| Small moves (cards sliding, counters ticking) | Often nothing. Let the music carry them |

Sync with **named markers** ("logo lands", "drop"), never copied times. Put the note's start on the marker
(`at="#logo-lands"`), and a rise's end on it (`dur={"to": "#logo-lands"}`), so the sound stays on its moment when 2D
re-times. Write the parts with `inspect_guide 'writing-parts'`; check the timing with `look_events` and listen with the
picture (`look_video`).

## Designs that are still in the engine

`click`, `riser`, `hit` and `subDrop` are made from settings. Sam judges them by ear, so reach for instruments first
and use these only where an instrument does not fit.

| Design | Controls |
|---|---|
| `click` | `pitch`, `material` (0 soft plastic ... 0.5 glass ... 1 metal), `tight`, `body`, `transient` (the snap), `air`, `bend` (above 0 a knock, below 0 a pop) |
| `riser` | `dur` (peaks at its end), `pitch`, `brightness`, `curve`, `tone`, `air`, `texture` |
| `hit` | `pitch`, `size`, `brightness`, `tail`, `drive` |
| `subDrop` | `dur`, `pitch` (where it lands), `drop` (octaves), `drive` |
| all | `volume`, `pan`, `width`, `seed` (another take of the same design) |

`inspect_operations` lists every field with its range. `dur` may end on a time or marker, as a note's can:
`fx.sound("riser", at="#drop-2", dur={"to": "#drop"})` peaks on "drop" wherever it moves.

```python
fx = track("hits")
fx.sound("hit", at="#logo-lands", size=0.6)
fx.sound("click", at="#button-press", material=0.3, pitch=1800, tight=0.7)
```

There is no `whoosh` design. An old song that has one still opens, but rendering it stops with: "this song has a
whoosh, which Rostrum no longer makes; remove it or replace it". `inspect` lists it as a problem. Remove it, or replace
it with a string rise, a cymbal swell or a piano run.

## Sounds from the picture's motion

`edit_sounds_from_motion samples=<file>` reads the picture's motion as data (per layer x, y, scale and opacity many
times a second; the 2D app hands it over, read-only). Make the file in Rostrum2D: `render_export format="motion"` (or
Export > Motion samples), `layers=[...]` to choose layers (default: every layer and camera that moves on its own; a
camera is `camera:<id>`).

**It adds nothing by itself.** It lists the events it found (a move with its start, fastest moment and stop; a hard
landing; a scale snap; a press; a step) and, for each, a musical answer or "nothing": a hit or note on the landing, a
rise built from an instrument for a long move, no sound for a small drift. You, or the agent, choose which to add.
What it adds is music or a real recorded sound, placed on the event's time. Run it again after the picture changes:
placed sounds move with it and keep what a person changed.

## Or recordings from your own library

`edit_sounds_from_motion` with `source="library"` answers the events you choose with recordings of real things from
the user's own sound folders (a Sonniss bundle, BOOM, their recordings), chosen by kind and shape, as `clip`s.
Add a folder first with `inspect_library folder=…`. How the picks and placement work, and how to search the library
yourself: `inspect_guide 'library'`.

**Layering both:** give a designed sound and library clips on one track the same `group` name
(`sound("click", at=2.0, group="door")` next to `layer("door", […], at=2.0)`). They are then one sound: `sound.set` or
`clip.set` moving or re-levelling one moves them all; `clip.set_one` changes just one clip.

## Check it

- `look_events` with the sharp events' times (`expect`): clicks and ticks should sit within a frame. Check them on
  their own tracks (`render_mix` with `solo`), since a swell can hide a click's start from the onset tool.
- A rise should peak on its marker, and a hit's onset sit on it (the events answer `peak_at`).
- Listen with the picture: `look_video` and the muxed preview.
