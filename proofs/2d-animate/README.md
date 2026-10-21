# Proof: 2D Animate — camera, motion blur / smears / trails, lip sync (Team Hem, H11, 2026-10-21)

**Question.** Can an agent, through the `rostrum-2d` MCP server only, (1) move a 2D camera through layers at different
depths, (2) get real motion blur, smears and echo trails driven by how things actually move, and (3) make a character
say a Sound voice line with mouth shapes worked out from the voice, keyed on the timeline?

**Verdict: pass with conditions.** All three work through MCP and render the same in preview and export. Conditions:
very fast moves at 12 blur samples show visible steps; the mouth in the proof is small on screen; a Sound voice line is
named by its WAV + words, not yet by its line id.

## Setup

- Driver: `mcp_session.py` (copy of `proofs/2d-character/mcp_session.py`; project
  `C:\Users\Sam\.rostrum\waves\scratch\hem-H11-proof\project`, item from `ROSTRUM_ITEM`), run under `heavy.ps1 … gpu`.
- `camera_film.py` + `camera_calls.json` (item `parallax`): 4 s, hills at depth 3, sun at depth 6, trees at depth 1,
  ground and posts at depth −0.4, a title locked to the screen; the camera pans 760 → 1300 px, pushes in 1 → 1.35 and rolls to −3°.
- `motion_film.py` + `motion_calls.json` (item `motion`): 3 s, shutter 180° with 12 samples; a whip with a smear, a
  bouncing ball with a 6-copy trail, a spinner.
- `lipsync_film.py` + `lipsync_calls.json` (item `talk`): the H10 character, framed waist-up, with nine drawn mouth
  shapes on the head; says Priyam's line 1 ("Every city keeps one hour for itself.") from
  `C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\voice-over-on-cue.stems\vo.wav` (2.5–9 s). The script's
  `lipsync(...)` call runs the phone model once (cached), then writes hold keys on the mouth layers. Sound muxed with
  ffmpeg (command in `LIPSYNC_NOTES.md`).

## Results (`C:\Users\Sam\.rostrum\waves\results\stage2\2d-animate\`)

| File | What |
|---|---|
| `camera-parallax-4s.mp4` | the camera shot |
| `camera-parallax-contact-sheet.png` | 12 frames |
| `camera-frame-0.0s.png`, `-2.0s.png`, `-3.97s.png` | stills |
| `motion-3s.mp4` | whip, ball, spinner, with motion blur |
| `motion-contact-sheet.png` | 12 frames |
| `motion-ball-trail-0.4s.png`, `motion-whip-smear-trail-0.6s.png`, `motion-spinner-blur-1.5s.png`, `motion-all-1.75s.png` | stills at fast moments |
| `lipsync-talk-with-sound.mp4` | the character saying the line, with the voice |
| `lipsync-contact-sheet.png` | 24 frames, 0.5–3.5 s |
| `lipsync-frame-0.3s.png`, `-1.5s.png`, `-2.6s.png`, `-4.6s.png` | stills |

## What I saw (honest)

- **Camera:** reads as depth. Near posts slide fast, trees half as fast, hills and sun barely; the title never moves;
  the push-in grows near layers more than far ones; the roll tilts the world, not the title. `look_motion` and
  `look_at` place layers where they show on screen (checked against the frames: the "never on screen" list was right).
- **Motion blur:** the spinner's arms blur along their arc and the hub stays sharp. At 12 samples a very fast whip
  shows faint separate copies at the ends of the blur; more samples (16–32) smooth it at a cost (below).
- **Trail:** the ball's echoes fade back along the bounce path; they follow the real motion (copies are the layer at
  earlier times).
- **Smear:** the whip stretches behind itself at its fastest frames and is a plain bar when still.
- **Lip sync:** words land at 0.66–4.32 s ("every" 0.66–0.90 … "itself" 3.46–4.32); the mouth opens on vowels, closes
  between words, puckers on "one / hour", rests in pauses. It reads in sync when played with the sound. The mouth is
  small at this framing (one head among a full frame): for a talking shot, frame closer or draw bigger shapes.

## Numbers

- Motion blur, 1080p frame of the motion scene (warm): sharp 10 ms; 8 samples 32 ms; 16 samples 53 ms; 32 samples 99 ms.
- Exports: camera 120 frames 4.8 s; motion 90 frames (12 samples) 4.7 s; lip sync 195 frames 6.8 s.
- Phone model (wav2vec2 fp16, DirectML when available): 6.5 s of voice aligned in 5.6 s including load; released after;
  second use from the cache in 0.0 s.

## Not done / open

- A Sound voice line can't be named by its line id yet (the Sound package isn't in the 2D environment); `source` is the
  take's WAV and the words. Lip-sync timing by shared marker ("line 1") is a follow-up.
- Camera: Blitz frosted glass under a moving camera not checked; groups' children take their group's depth.
- Smear measures the layer's own motion (put it on the group when only the group moves); text length along the motion is estimated.

## Attribution rows

See `LIPSYNC_NOTES.md` › Attribution rows (onnxruntime-directml MIT, flatbuffers Apache-2.0, protobuf / sympy / mpmath
BSD-3, the wav2vec2 model Apache-2.0, CMUdict BSD-2). Camera and motion add no dependency.
