# Scoring motion with instruments

Rostrum answers a move on screen with **music** (an instrument), a **real recorded sound**, or nothing. It makes no
whooshes, swishes, "transition" sounds or other made-up effects, and will not. Silence beats a mediocre sound.

## Answering a move with instruments

| What happens in the picture | An answer, with instruments |
|---|---|
| Something builds toward a landing | A string rise, a cymbal swell or a piano rise that ends on the landing's marker |
| Something lands | A note or a hit on the marker: a struck bell, a low piano note, a kick and cymbal hit |
| A title or logo appears | One held note or chord, a bell or soft keys, starting on its marker |
| A big change of scene | A cymbal swell into it, or a held silence just before it |
| Small moves (cards sliding, counters ticking) | Often nothing. Let the music carry them, or a soft glass-marimba tap |

These are ordinary parts on ordinary tracks: notes, chords and drum hits (`track.note`, `track.chord`, `track.hit`).
Write them with `inspect_guide 'writing-parts'`.

Sync with **named markers** ("logo lands", "drop"), never copied times. Put a note's start on the marker
(`at="#logo-lands"`), and a rise's end on it (`dur={"to": "#logo-lands"}`), so the sound stays on its moment when 2D
re-times. Check the timing with `look_events` and listen with the picture (`look_video`).

```python
bell = track("bell", model="tubularBell")
bell.note("G5", at="#logo-lands", dur=2.0, vel=0.7)
hits = track("hits", kit="synth")
hits.hit("kick", at="#logo-lands", vel=0.8)
hits.hit("cymbal", at="#logo-lands", vel=0.8)
```

## Sounds from the picture's motion

`edit_sounds_from_motion samples=<file>` reads the picture's motion as data (per layer x, y, scale and opacity many
times a second; the 2D app hands it over, read-only). Make the file in Rostrum2D: `render_export format="motion"` (or
Export > Motion samples), `layers=[...]` to choose layers (default: every layer and camera that moves on its own; a
camera is `camera:<id>`).

**It adds nothing by itself.** It lists the events it found (a move with its start, fastest moment and stop; a hard
landing; a scale snap; a press; a step) and, for each, the answers that fit: a struck bell note on the moment, a kick
and cymbal hit, a string swell or a cymbal roll rising into it, a piano run landing on it, a real recording from your
library, or nothing. You, or the agent, choose which to add. It writes them as instrument parts in the song's key
(`key="C major"`), on their own tracks, placed on the event's time. Run it again after the picture changes: placed
sounds move with it and keep what a person changed.

## Or recordings from your own library

`edit_sounds_from_motion` with `source="library"` answers the events you choose with recordings of real things from
the user's own sound folders (a Sonniss bundle, BOOM, their recordings), chosen by kind and shape, as `clip`s.
Add a folder first with `inspect_library folder=…`. How the picks and placement work, and how to search the library
yourself: `inspect_guide 'library'`.

**Layering recordings:** give several library clips on one track the same `group` name (`layer("door", […], at=2.0)`).
They are then one sound: `clip.set` moving or re-levelling one moves them all; `clip.set_one` changes just one clip.

## Older songs

Risers, reverse cymbals, sub drops and big impacts no longer ship in the library (PURPOSE.md: no synthetic transition
sounds; build with strings, a cymbal roll or a piano run). A song whose clip still uses one of those recordings opens, and
the Problems chip names the clip and the kind ("clip "c1" uses a cinematic.riser recording … that Rostrum no longer
offers"); the clip stays in the file and still plays until you replace it.

Rostrum used to make a few sounds from settings (a click, a hit, a riser, a sub drop). It no longer does. An older
song that still has one opens and says so on the Problems chip (and in every agent reply, and in `inspect_diagnose`), naming it, its time
and its track, for example: *fx: this song has a designed sound ("riser" at 2 s) that Rostrum no longer makes; it is
left out of the mix. Replace it with an instrument*. It stays in the file, unplayed; answer the move from the table above.

## Check it

- `look_events` with the sharp events' times (`expect`): hits and taps should sit within a frame. Check them on
  their own tracks (`render_mix` with `solo`), since a swell can hide a hit's start from the onset tool.
- A rise should peak on its marker, and a hit's onset sit on it (the events answer `peak_at`).
- Listen with the picture: `look_video` and the muxed preview.
