# Listening without ears: the look tools

You cannot hear the render, so each look tool turns one aspect of it into numbers or a picture. Render first
(`render_mix`, then `inspect_job` until it is done); every look tool reads the last render unless you pass `wav`.

| Question | Tool | What to read |
|---|---|---|
| Is every part where I meant it, before rendering? Which tracks start on each marker? | `look_arrangement` | a picture of the written song (a row per track: notes by pitch, drum hits, clips; bars, sections, markers) and, per marker, the tracks that start on it and each track's nearest start in ms and beats. Reads the document, so no render is needed |
| How loud is it, and does it build where it should? | `look_loudness` | integrated LUFS, true peak, the short-term curve (a sag or dip shows as a valley in the picture), clipped moments, where the limiter worked and which tracks drove it |
| Is one track buried or too loud? | `look_levels` | each stem's LUFS, dB under the loudest / the mix, and the track's volume in dB (move a track N dB: volume + N); flags (a float stem over 0 dBFS is held, not clipped) |
| Do sounds land on time (a hit on a cut, a footstep on a frame)? | `look_events` with `expect` | each expected time's nearest onset and offset in ms; pass within `tolerance`; with `by_stem`, which stem hits each time |
| Is there hum, a whistle, or masking? | `look_spectrum` (with `marks`) | `hum_lines` are the steady lines that are unwanted (flat level, on 50 / 60 Hz multiples or still there when the music stops); `tones` lists every steady line with its note name, so a held note shows as a note, not hum; marks show where events should be |
| Does it lean left or right, or fall apart in mono? | `look_stereo` | balance per section, correlation, mono warnings |
| Is there boom where the picture has none, or mud? | `look_low_end` | each track's and the mix's share under 150 Hz, under 60 Hz and in the low mids (150–500 Hz, where parts piling up sound muddy) |
| What is the tempo, is it steady, do sounds sit on the beat or the document's tempo map? | `look_beats` (`stems: true` for every stem) | BPM and `steadiness`, beat and downbeat guess, per onset the ms from the nearest 1/4 beat (+ = late) against the audio's own beats and the document's grid; picture: waveform, beats, onsets coloured green / orange / red |
| Is a melody on the right notes, in time and in tune? | `look_pitch` with `track` | notes heard (name, cents off, vibrato, drift) and each written note marked ok / wrong_note / wrong_octave / late / early / out_of_tune / missing; picture: curve over the written notes. One line at a time: use a single-voice stem |
| Do two tracks fight for the same frequencies? | `look_clash` (needs stems) | spans: when, which Hz band, which two tracks, dB each stands over the other; picture: time × band map coloured by pair. The floor follows the mix (reply's `floor_db`); tighten with `within_db` 3 and a `floor_db` 10 dB higher if a dense mix lights up everywhere |
| What key and chords is it in, and are the written notes playable and clean? | `inspect_harmony` | key (document key map, notes or audio), chord per bar or beat, and plain-fact checks on the written notes: out of the instrument's range, close intervals under the low limit, voices crossing, upper voices over an octave apart, notes out of key |

Read the numbers as measurements: onset detection itself reads a soft sound 10–30 ms after it starts, the chord from audio is a best
match to common shapes (a mix with drums and a melody on top reads rougher than the notes written in the document), and a
key estimate cannot always tell a major key from its relative minor (the tool says when both fit).

What these cannot tell you: whether an instrument sounds real or sampled, whether phrasing is musical, whether a
recording sounds like the object on screen. Say so in your report; a person decides those by listening.

## Effects against a picture

- `look_video` `what: "sheet"` to see the whole clip, `"motion"` for sudden-stop candidates (impacts), `"frames"`
  around a time to check one event frame by frame.
- `inspect_cuts` cuts recordings into single sounds with facts (peak, attack, brightness, low-end share), cached,
  so you can pick a cut by its measurements and place it with a clip (`in` = the cut's start).
- After placing sounds, `look_events` with the event times as `expect` checks sync within a frame.
