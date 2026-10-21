# Proof P-SFX — effects that match the picture

**Question.** P-SND's effects pass for the door close-up scored 30/100 ("nothing like what the picture
shows"). Why, and what does an agent need to make small, close, precise foley that fits the picture?

**Verdict: pass with conditions.** The redo is built from the picture, so its sounds are the right
objects, at the right size, softness and timing. Sam's ears decide whether it is good. The conditions:
close foley of the exact objects still isn't available under clean licences (we need to record our own),
and the sound-match model can't hear how hard something is hit, or tell a whoosh from cloth.

## Results (Sam: watch and listen)

All in `C:\Users\Sam\.rostrum\waves\results\stage1\p-sfx\`:

| File | What it is |
|---|---|
| `effects-20s-redo-with-picture.mp4` | **The redo on the clip.** Compare with `C:\Users\Sam\.rostrum\waves\results\stage1\p-snd\effects-20s-door-with-picture.mp4` |
| `effects-20s-redo.wav` | The redo alone (48 kHz) |
| `event-sheet.png` | What the agent saw: for each of 27 events, the frames around it, what touches what, the material, how hard, how close, and the sound that implies |
| `old-vs-new-spectrograms.png` | Old pass on top, redo below, plus both loudness curves |
| `spectrogram-old-with-events.png`, `spectrogram-new-with-events.png` | Each one with the picture's contact moments marked |
| `effects-20s-redo-takes.json` | Every cut placed: time, event, kind, the recording, in-point, length, sound-match score, licence, author, link |

## Why the old pass missed (checked, not assumed)

1. **The agent never saw the picture. Confirmed.** Checked frame by frame (`eyes/README.md`), 8 of
   the 20 rows in the old event list were wrong:
   - **The door never moves.** So there should be no creak and no "door flex".
   - **Nothing hits hard.** The hardest contact is a soft palm pat, and there is no clank at 16 s.
   - **The fast moves are hands and sleeves right at the lens.** They should sound like soft cloth,
     not whooshes.
   - **The ring and padlock are still by 17.6 s.** The old pass put a held low tone under 16–20 s.
2. **Takes picked by category name. Confirmed, with numbers.** We scored the old pass's own takes
   with the sound-match model, against the same descriptions as the new cuts. Its padlock takes
   ("impact.tin-medium") scored a median 0.03 as "a small brass padlock rattling against an iron ring";
   the model heard them as fingertip taps on wood. Its door creak scored 0.00 as "a hand sliding on wood".
3. **The free libraries lacked close foley. Partly true.** The old library had no padlock, no knocker
   ring and no hands on wood. Member *sources* found 261 clean takes (230 CC0, 31 CC-BY), with real
   padlocks, knockers, finger taps and cloth (`SOURCES.md`). But no one has recorded the exact things
   this shot needs: an iron ring dropping onto its plate, a hanging padlock swaying, a palm on a
   panelled door.

## What was built

| Tool | What it answers | Where |
|---|---|---|
| **eyes** | Where does something move, and when does it suddenly stop? (optical flow, frame by frame). Frame strips around any time, a contact sheet, and a written event sheet checked against frames by eye | `eyes/` (`python -m eyes motion|frames|sheet|events`) |
| **match** | Does this take sound like "a small brass padlock rattling against an iron ring"? Scores takes against a description, and against contrast descriptions (LAION-CLAP). Includes a zero-shot eval | `match/`, licences in `MODELS.md` |
| **pool** | Cuts every long recording into single sounds, each starting on its transient. Measures each: peak, noise floor, attack, brightness, length | `redo/pool.py`, kinds in `redo/kinds.py` |
| **score** | Scores the whole pool, and the old pass's takes, in one model load | `redo/score.py` |
| **pick + door_redo** | For each event-sheet line, picks a cut and places it. The sound-match score says *what* a cut is. Measured facts say if it fits the frame (sharp start, brightness range, length). Level is set from the force word. Each cue lists its event number | `redo/pick.py`, `redo/door_redo.py` |
| **listen** (Priyam's, reused) | Onsets against cue times, per-stem levels, spectrograms with marks, comparison | `proofs/sound/listen` |

Run order (from `proofs/sound-sfx`):
1. `python -m redo.pool pool.json` (main venv)
2. `heavy.ps1 run … gpu <model venv python> -m redo.score pool.json pool_scored.json` (needs `HF_HOME` and `HF_HUB_OFFLINE=1`, as in `match/README.md`)
3. `python -m redo.door_redo pool_scored.json out.wav --picks takes.json --stems dir`

## Numbers

| | Old pass (P-SND) | Redo |
|---|---|---|
| Events taken from | a list of times | 27 events with object, material, force and distance, each checked against frames |
| Sounds placed | 47 | 51 cues, cut from 23 recordings (9 cuts reused, each at least 3 s from its last use) |
| Sound-match score of the placed takes (median, "own description vs the other kinds and the wrong sounds") | padlock 0.03, ring 0.68, palm 0.64, sleeve 0.98 | **0.84 over all cues**, lowest 0.45 (one fingertip tap) |
| Sync of sharp sounds to their cue | 8 of 10 at 0 ms, 2 at 30–44 ms | **37 of 37 within one frame (40 ms), 35 within 20 ms, median 3.7 ms** |
| Loudness | −20.2 LUFS, −1.3 dBTP | −27.3 LUFS, −2.1 dBTP. Quiet on purpose: soft events in a quiet room. Room tone −53 LUFS |
| Sub-bass (< 60 Hz), whole file | −30.8 dB | −60.0 dB (**29 dB less**: no low hits or booms) |
| Low (60–250 Hz) | −27.8 dB | −43.2 dB (15 dB less) |
| Top end (> 6 kHz) | −39.9 dB | −38.6 dB (about the same: the small metal detail stays) |
| After 17.6 s (nothing moves) | held low tone, ring creaks | room tone only |
| Model run | — | CLAP scores 712 cuts in 34 s; GPU peak 1.03 GB, RAM 1.5 GB; released after each run |

**How well the sound-match model hears** (`match/eval_set.json`: 52 library takes, 10 labels; chance is 10%):
- **Overall:** it picked the right label 69% of the time; the right label was in its top 3 92% of the time.
- **Easy for it:** glass, whoosh, door, paper and pour were 100%.
- **Weak where this shot needs it:**
  - Small metal hits: 2 of 6, mostly heard as glass.
  - Small wood hits: 2 of 6, heard as metal.
  - Cloth: 0 of 5, heard as whoosh.

So it is useful for "is this a padlock or a tin can", but it can't catch a whoosh used as a sleeve
(it scored the old "whoosh.cloth" takes 0.997 as a sleeve) or a heavy hit used as a soft pat (0.92).
Force, scale and "is this cloth or air" have to come from the picture (eyes) and measured facts (level,
brightness, attack), as `redo/pick.py` does. Padding short takes with silence beat looping them
(69% vs 67%; metal 2/6 vs 0/6).

## What the agent checked without ears, and what it can't tell

**Checked:**
- **Onsets against cues.** All within one frame.
- **Levels per track.**
  - Metal −26 LUFS, wood −32, cloth −35, room −53.
  - The first try put 86% of the mix's sub-bass in the wood track. It was fixed with a high-pass and
    a lower level for the pats.
- **Brightness of padlock cuts.** The first try picked tinkly small-chain cuts at 11–13 kHz. These are
    now capped at 8 kHz, so the padlock cues come from real padlock recordings (3.5–8 kHz).
- **Hum in the room recording.** A 100–150 Hz line in the room tone was high-passed at 160 Hz.
  A faint trace remains about 50 dB below the loudest sound.
- **Sound-match score of every placed cut** (`effects-20s-redo-takes.json`).

**Can't tell:**
- whether the clinks sound like *iron and brass* rather than keys or chain (the closest real takes are
  padlock handling, a knocker and a finger ring dropped on a table, used for the tiny skin-on-metal touches);
- whether the layering of the swings sounds natural or busy (51 cues in 20 s, most of them very quiet);
- whether the 128 kbps Freesound previews sound lossy at this level;
- whether −27 LUFS is the right loudness for Sam's playback.

## Video-to-audio models

None can ship (`MODELS.md`):
- **MMAudio:** non-commercial weights.
- **HunyuanVideo-Foley:** a custom Tencent licence with territory limits.
- **ThinkSound:** "no commercial use".
- **FoleyCrafter:** its base model is CC-BY-NC-SA.
- **Kling-Foley:** no licence.
- **MultiFoley:** not released.

None fits 4 GB either, so none was tried. **Meta PE-AV** (Apache-2.0) is the one shippable
video-aware model: it scores audio against the *video itself* rather than generating sound. It's
worth a later proof (small version is about 1.7 GB of GPU memory in half precision).

## What the Sound app needs for effects work (feeds the Sound app build)

1. **Eyes on the picture, as an operation.**
   - What it gives: frame strips around a time, motion and "sudden stop" candidates, and a contact sheet.
   - Event sheet: a stored event sheet (object, material, action, force, distance, confidence) that
     cues point to by event number. The project's shared markers are the natural home for it.
2. **A cut pool, not a takes list.**
   - Recordings cut into single sounds on their transients, with measured facts (peak, floor,
     attack, brightness).
   - Computed once and cached: the "analyse once, store as data" rule.
3. **A sound-match score stored per cut,** used together with fact rules, never alone:
   - The model can't hear force, scale or cloth vs air.
   - Licence: LAION-CLAP weights are Apache-2.0, but trained partly on non-commercial clips
     (**DECISION** below).
4. **Level from force.**
   - The agent writes "soft" / "very soft" against an event. The app sets the peak level per kind
     and keeps the whole mix's gain separate.
   - Today it's a table in `door_redo.py`, which should become data with a GUI control.
5. **Checks after every render:**
   - onsets against cues (pass within one frame);
   - per-track low-end share (flags a boom where the picture has none);
   - hum detection on beds;
   - the placed cuts' scores.
6. **A real close-foley library:** the exact objects, recorded dry and close. Free libraries don't
   have them.
7. **Engine notes:**
   - A per-sample start offset would remove the "start 5 ms early" workaround (cuts begin 5 ms before
     their transient).
   - A notch filter type would remove hum without thinning the bed.

## Attribution rows

Dependencies (dev only, nothing ships yet):

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| LAION-CLAP `laion/larger_clap_general` (weights) | snapshot ada0c23 | Apache-2.0 (training data partly non-commercial, see MODELS.md) | proofs/sound-sfx/match | model | dev only | Keep the licence and notice | https://huggingface.co/laion/larger_clap_general |
| Hugging Face transformers (+ tokenizers, safetensors, huggingface_hub) | 5.20.2 | Apache-2.0 | proofs/sound-sfx/match | Python package | dev only | Keep the notice | https://github.com/huggingface/transformers |
| PyTorch (+ torchaudio) | 2.11.0+cu128 | BSD-3-Clause | proofs/sound-sfx/match | Python package | dev only | Keep the notice | https://pytorch.org |
| OpenCV (opencv-python-headless) | 4.x | Apache-2.0 | proofs/sound-sfx/eyes | Python package | dev only | Keep the notice | https://opencv.org |

Sound takes used in the redo. CC-BY ones need their credit shown. CC0 ones are listed for the record.
Full list of all 261 downloads: `SOURCES.md`.

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| "StiffClothRubbing.wav" by HerbertBoland | Freesound 28297 | CC-BY-4.0 | proofs/sound-sfx redo | sound file | dev only | Credit "HerbertBoland (freesound.org)" | https://freesound.org/people/HerbertBoland/sounds/28297/ |
| "Padlock (SoundAction 005)" by alexarje | Freesound 718103 | CC-BY-4.0 | proofs/sound-sfx redo | sound file | dev only | Credit "alexarje (freesound.org)" | https://freesound.org/people/alexarje/sounds/718103/ |
| "247 - Acoustic Memory - FabricFoley_08.wav" by AcousticMemory | Freesound 371676 | CC-BY-3.0 | proofs/sound-sfx redo | sound file | dev only | Credit "AcousticMemory (freesound.org)" | https://freesound.org/people/AcousticMemory/sounds/371676/ |
| "FingerTapsWoodLongLoop01.wav" by Otakua | Freesound 219933 | CC-BY-3.0 | proofs/sound-sfx redo | sound file | dev only | Credit "Otakua (freesound.org)" | https://freesound.org/people/Otakua/sounds/219933/ |
| 19 CC0 recordings (Freesound, BigSoundBank, OpenGameArt; listed in `effects-20s-redo-takes.json`) | — | CC0-1.0 | proofs/sound-sfx redo | sound files | dev only | Nothing (courtesy credit for BigSoundBank) | see SOURCES.md |

## DECISION (for Sam, via the manager)

LAION-CLAP and almost every open audio model have permissive weights (Apache-2.0) but were trained
partly on clips licensed for non-commercial use only. **May the Sound app ship such weights?** The
common reading is that only the weights' own licence binds, but this is legally unsettled. Until
decided, the sound-match tool stays a development tool. Without it the app still has eyes, the cut
pool and fact rules, but loses the "is this a padlock?" check.
