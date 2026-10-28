# Using the ears to check a mix

An agent cannot hear, so the `look_*` and `inspect_*` tools turn a render into numbers and pictures. This page is the
order to use them in when checking a whole mix; the table of every tool and what to read is inspect_guide `listening`.

## Render first

`render_mix` with `stems: true`, then `inspect_job` until done. Every look tool reads the last render unless you pass
`wav`; the ones that compare tracks (`look_sound` (`what: "levels"`), `look_sound` (`what: "clash"`), `look_sound` (`what: "low_end"`)) need the stems.

## A pass from the outside in

1. **Overall:** `look_sound` (`what: "loudness"`) with the brief's moments as `expect` (`[{"at": 31.5, "kind": "hit"}, {"at": 38, "kind": "climax"}]`). Its summary starts with the
   **faults** a listener would hear, each with its time, the number and what to change (a weak hit "1.0x a normal note, bright attack 1.0x" with the fix that number points to, a blurred
   stop, drums dropping early, a climax that holds only 2 s, a build already at the ceiling before the hit, one harmony held for 19 s, a dull top end or one that does not grow into the climax, a near-mono mix, a hit the
   limiter squashed 4.7 dB): fix those first (the table is in inspect_guide `listening`, *Faults*). Integrated loudness and true peak against the delivery target; the short-term curve
   shows whether the loud and quiet parts are where the piece needs them, and the summary names the loudest moment and
   its time (the loudest 3 s and 0.4 s, and the highest sample): check that the climax is where you meant; clipped moments are listed with times. On a render's mix it also draws where the master's glue and limiter turned the sound down
   (the engine's own gain curve, the worst moments with the dB reduced) and, with stems, names the tracks that drove each
   moment: lower those tracks where it works. A render that landed under the loudness target (the reply says how far) is fixed by `edit_loudness`, before any guess at `maxLimit` or volumes: it answers the exact edit, e.g. `edit_loudness {"apply": "best"}` (raise `maxLimit` a little, or tame the peaky track with a measured compressor).
   Under a voice-over, read **room for speech** in the same summary: "+6 dB" means a voice at the mix's loudness
   stands 6 dB over the music in 1–4 kHz, where words are understood (`speech_room.bands` gives each band).
2. **Balance:** `look_sound` (`what: "levels"`). Which track is far under or over the rest. A track you meant to be quiet is not a problem;
   one you meant to lead and is buried is. Each stem's `db_vs_mix` and the track's `volume_db` are side by side: to
   move a track N dB against the other tracks, set its volume to `volume_db` + N (`track.set` `{"volume": {"db": …}}`); the
   master's loudness target and limiter turn every stem up or down together, so the gaps between tracks you set stay. A float stem above 0 dBFS is fine in the file (it only clips if someone converts
   it to a 16 or 24-bit file); only a stem marked "clips" is cut flat.
3. **Fights:** `look_sound` (`what: "clash"`). Where one track buries another: both loud in the same frequency band at the same time, one
   standing at least 3 dB over the other (`min_over_db`). Spans come back ranked by how far one is buried (`buried_track`,
   `buried_by_db`). Two parts at the same level in a band are not a problem, so a balanced mix answers "no real problem"
   with an empty list. Act on the top spans between parts that matter (a voice and a pad). Its floor follows the mix
   (40 dB under the loudest band; the reply's `floor_db`), so the count does not change when the whole mix gets louder.
   On a dense mix, tighten with `within_db` 3 and a `floor_db` 10 dB above the one it used.
4. **Low end and mud:** `look_sound` (`what: "low_end"`). Each track's and the mix's share under 150 Hz, under 60 Hz and in the low mids
   (150–500 Hz); two tracks both heavy under 150 Hz usually fight, and several parts heavy in the low mids sound muddy.
   Compare the mix's numbers before and after a change.
5. **Width:** `look_sound` (`what: "stereo"`). Balance per section and mono warnings (parts that cancel when summed to mono).
6. **Timing:** `look_music` (`what: "beats"`) (whether the audio's beats fit the document's tempo, steadiness, onsets against the grid) and `look_music` (`what: "events"`) with `expect` for hits that must land
   on markers. Add `by_stem: true` to learn which track hits each marker, in one call. A time that passes can still be
   barely there: give it a kind (`{"at": 36, "kind": "stop"}`) and read the faults.
7. **Notes:** `look_music` (`what: "harmony"`) for key, chords and written-note facts (it reads the notes: run it before rendering too); `look_music` (`what: "pitch"`) with `track` for whether every written note is there and in its octave (judged on each note's attack, so ringing parts read right; the first line says the track's register), and on a one-voice part, late, out-of-tune or wrong notes.
8. **Problems in a recording:** `look_sound` (`what: "spectrum"`) (hum lines, steady tones with note names, marks at times),
   `look_sound` (`what: "cleanup"`) for before / after of a cleaned clip.

## Changing and checking again

Change one thing, render, and look again with the same tool. Compare the numbers between renders: the ears say what
moved, not what is right. Keep the earlier render's reply to compare against.

## What the ears cannot tell you

Whether an instrument sounds real, whether phrasing is musical, whether a sound fits the picture, whether the mix feels
right. Report those as open for a person to judge by listening, with the file path.
