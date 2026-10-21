# Using the ears to check a mix

An agent cannot hear, so the `look_*` and `inspect_*` tools turn a render into numbers and pictures. This page is the
order to use them in when checking a whole mix; the table of every tool and what to read is inspect_guide `listening`.

## Render first

`render_mix` with `stems: true`, then `inspect_job` until done. Every look tool reads the last render unless you pass
`wav`; the ones that compare tracks (`look_levels`, `look_clash`, `look_low_end`) need the stems.

## A pass from the outside in

1. **Overall:** `look_loudness`. Integrated loudness and true peak against the delivery target; the short-term curve
   shows whether the loud and quiet parts are where the piece needs them; clipped moments are listed with times. On a render's mix it also draws where the master limiter turned the sound down
   (a curve, the worst moments with the dB reduced) and names the tracks that drove each moment. That part is measured from
   the stems, so it is a close estimate, not the engine's exact curve: lower those tracks where it works.
2. **Balance:** `look_levels`. Which track is far under or over the rest. A track you meant to be quiet is not a problem;
   one you meant to lead and is buried is. A float stem above 0 dBFS is fine in the file (it only clips if someone converts
   it to a 16 or 24-bit file); only a stem marked "clips" is cut flat.
3. **Fights:** `look_clash`. Which two tracks share a frequency band at the same time, and by how much one stands over the
   other. Act on clashes between parts that matter (a voice and a pad), not every overlap. On a dense mix, tighten with
   `within_db` 3 and `floor_db` -35.
4. **Low end:** `look_low_end`. Each track's share under 150 Hz and 60 Hz; two tracks both heavy there usually fight.
5. **Width:** `look_stereo`. Balance per section and mono warnings (parts that cancel when summed to mono).
6. **Timing:** `look_beats` (steadiness, onsets against the grid) and `look_events` with `expect` for hits that must land
   on markers. Add `by_stem: true` to learn which track hits each marker, in one call.
7. **Notes:** `inspect_harmony` for key, chords and written-note facts; `look_pitch` on one stem for wrong or out-of-tune notes.
8. **Problems in a recording:** `look_spectrum` (hum lines, steady tones with note names, marks at times),
   `look_cleanup` for before / after of a cleaned clip.

## Changing and checking again

Change one thing, render, and look again with the same tool. Compare the numbers between renders: the ears say what
moved, not what is right. Keep the earlier render's reply to compare against.

## What the ears cannot tell you

Whether an instrument sounds real, whether phrasing is musical, whether a sound fits the picture, whether the mix feels
right. Report those as open for a person to judge by listening, with the file path.
