# Designed sounds: motion-design effects

Whooshes, clicks, ticks, taps, pops, risers, hits and sub drops are **designed in the engine**, not picked from a
library. Each is a `sound` item on a track with its own controls, so one sound fits one move.

## The designs and what each control does

| Design | Controls |
|---|---|
| `whoosh` | `dur` (the move's start to its stop), `speed` curve, `panPath`, `brightness`, `size`, `doppler`, `tone` (whistle), `air`, `texture` |
| `click` | `pitch`, `material` (0 soft plastic … 0.5 glass … 1 metal), `tight`, `body`, `transient` (the snap), `air`, `bend` (above 0 a knock, below 0 a pop) |
| `riser` | `dur` (peaks at its end), `pitch`, `brightness`, `curve`, `tone`, `air`, `texture` |
| `hit` | `pitch`, `size`, `brightness`, `tail`, `drive` |
| `subDrop` | `dur`, `pitch` (where it lands), `drop` (octaves), `drive` |
| all | `volume`, `pan`, `width`, `seed` (another take of the same design) |
`inspect_operations` lists every field with its range; a field shows only for the designs that have it. `dur` may also end on a time or marker, as a note's can: `fx.sound("riser", at="#drop-2", dur={"to": "#drop"})` peaks on "drop" wherever it moves.
`inspect_operations` lists every field with its range; a field shows only for the designs that have it.

```python
ui = track("ui_whoosh")
ui.sound("whoosh", at=1.0, dur=0.66, speed=[[0, 1], [0.3, 0.4], [1, 0]], panPath=[[0, -0.9], [1, -0.5]], size=0.7)
ui.sound("click", at=3.475, material=0.3, pitch=1800, tight=0.7)
```

## Sounds from the picture's motion

`edit_sounds_from_motion samples=<file>` reads the picture's motion as data (per layer x, y, scale and opacity many
times a second; the 2D app hands it over, read-only) and places a sound on every event. Make the file in Rostrum2D:
`render_export format="motion"` (or Export › Motion samples), `layers=[…]` to choose which layers sound (default:
every layer and camera that moves on its own; a camera is `camera:<id>`). Several layers making the same gesture at
the same moment are one event, one sound as big as all of them; a slow drift (under 300 px/s) gets no whoosh.

| Event (read from the motion) | Sound placed |
|---|---|
| a move: start, fastest moment, stop, speed curve, from / to | a whoosh over exactly the move: its speed curve, its pan following the layer; faster = louder, brighter, more air and doppler; a bigger layer = a bigger sound. Leaving the frame at speed, it rings on past the edge |
| arriving hard (a snap stop or an overshoot): when it first reaches its place | a click there, harder for a harder landing |
| a scale snap (a title snapping in): its most sudden moment | a bright click, a short air lead-in, a small thump under it |
| a press (the scale dips and returns) | a soft press click at the deepest point, a lighter release click when it returns |
| a step (the opacity jumps on: a counter's digit) | a tight tick, each a different take |

These are a **starting point**: change any sound with `sound.set` (or the screen). Running the tool again after the
picture changes moves the sounds with it, and keeps what a person changed. The tracks play into a `ui` bus with a short
shared room and a light compressor, so the layers sit as one piece; change or bypass those effects like any other.

A busy picture (a storm of 70 cards) makes a crowd: sounds that overlap on one track are each turned down by
1/√(how many overlap), so together they play at about one sound's loudness, not many times it. The reply says the
largest cut; turn the track up (`track.set volume`) when the crowd should be bigger.

## Or recordings from your own library

`edit_sounds_from_motion` with `source="library"` places the same events with recordings from the user's own sound
folders instead (a Sonniss bundle, BOOM, their recordings), chosen by kind and shape for each event, as `clip`s.
Add a folder first with `inspect_library folder=…`. How the picks and placement work, and how to search the library
yourself: `inspect_guide 'library'`.

## Check it

- `look_events` with the sharp events' times (`expect`): clicks and ticks should sit within a frame. Check them on
  their own tracks (`render_mix` with `solo`), since a whoosh's swell can hide a click's start from the onset tool.
- A whoosh's loudest moment should match the move's fastest moment (the events answer `peak_at`).
- Listen with the picture: `look_video` and the muxed preview.
