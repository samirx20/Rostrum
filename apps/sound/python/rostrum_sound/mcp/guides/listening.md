# Listening without ears: the look tools

You cannot hear the render, so each look tool turns one aspect of it into numbers or a picture. Render first
(`render_mix`, then `inspect_job` until it is done); every look tool reads the last render unless you pass `wav`.

| Question | Tool | What to read |
|---|---|---|
| How loud is it, and does it build where it should? | `look_loudness` | integrated LUFS, true peak, the short-term curve (a sag or dip shows as a valley in the picture), clipped moments |
| Is one track buried or too loud? | `look_levels` | each stem's LUFS and dB under the loudest / the mix; flags |
| Do sounds land on time (a hit on a cut, a footstep on a frame)? | `look_events` with `expect` | each expected time's nearest onset and offset in ms; pass within `tolerance` |
| Is there hum, a whistle, or masking? | `look_spectrum` (with `marks`) | steady horizontal lines are hum; marks show where events should be |
| Does it lean left or right, or fall apart in mono? | `look_stereo` | balance per section, correlation, mono warnings |
| Is there boom where the picture has none? | `look_low_end` | each track's share under 150 Hz and 60 Hz |

What these cannot tell you: whether an instrument sounds real or sampled, whether phrasing is musical, whether a
recording sounds like the object on screen. Say so in your report; a person decides those by listening.

## Effects against a picture

- `look_video` `what: "sheet"` to see the whole clip, `"motion"` for sudden-stop candidates (impacts), `"frames"`
  around a time to check one event frame by frame.
- `inspect_cuts` cuts recordings into single sounds with facts (peak, attack, brightness, low-end share), cached,
  so you can pick a cut by its measurements and place it with a clip (`in` = the cut's start).
- After placing sounds, `look_events` with the event times as `expect` checks sync within a frame.
