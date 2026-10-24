# Rostrum2D lip sync: a character's mouth follows a voice (Team Hem, H11)

You draw a mouth in a few shapes (closed, open, wide, rounded …), one layer per shape. Lip sync listens to a voice
clip, works out which sound is said when, and keys the mouth layers so the right shape shows at the right moment. The
result is ordinary keys on the timeline: you can move, retime or change any of them by hand afterwards.

Code: `shared/core/rostrum_core/lipsync/` (shared with 3D: audio, phone model, aligner, shapes, timing, voice lines) and `python/rostrum2d/lipsync/` (the operation and script call). Python only; the engine just shows the keyed layers.

## The nine mouth shapes

The classic set (Preston Blair's, with the letter names Rhubarb Lip Sync uses). Draw any subset; more shapes read better.

| Shape | Looks like | Said on |
|---|---|---|
| **X** | rest, lips together, relaxed | silence |
| **A** | lips pressed shut | M, B, P |
| **B** | slightly open, teeth together | most consonants (T, D, K, S, N, R, TH …), "ee" |
| **C** | open | "eh", "a" in *cat*, "i" in *sit*, the short "uh" |
| **D** | wide open | "ah" in *father*, "i" in *fire*, "ow" in *how* |
| **E** | rounded, a little open | "aw" in *off*, "er" in *bird*, "oy" |
| **F** | puckered, small and round | "oo", "oh", W |
| **G** | top teeth on the lower lip | F, V |
| **H** | open, tongue up behind the teeth | L |

**When a shape has no layer**, the nearest one you did draw is shown instead, closest first (then their own fallbacks):

| Missing | Shows |
|---|---|
| X | A, then B |
| A | X, then B |
| B | C, then X |
| C | B, then D |
| D | C, then B |
| E | F, then C |
| F | E, then A |
| G | B, then A |
| H | B, then C |

So three drawings (X, A, D) already give a usable mouth; nine give the full range.

## How it hears the voice

1. **Phones.** A speech model (wav2vec2-lv-60-espeak-cv-ft, Apache-2.0) listens to the clip and gives, for every 1/50 s,
   how likely each speech sound is.
   - **With the words** (`text`, English): the words are looked up in the CMU Pronouncing Dictionary (BSD-2), and the
     known sounds are placed where the model hears them (forced alignment). This is the accurate way. A word the
     dictionary lacks is refused by name; give its sound with `pronounce={"rostrum": "R AA1 S T R AH0 M"}` (ARPAbet).
   - **Without the words:** the sounds the model hears on its own (any language, a little less exact).
2. **Computed once.** The phones are stored in the shared cache (kind `lipsync`), keyed by the audio file's content, the
   words, the clip range, the language and our engine version. Running again (a script re-run, a second operation, the
   inspect tool) reads the cache instantly. Change the words or the range and it is worked out again.
3. **Mouth cues.** Each sound becomes a shape (table above), then the timing tools below make it read on screen.
4. **Keys.** Each mouth layer gets plain `opacity` keys with the `hold` ease: 1 while its shape shows, 0 otherwise. At
   the clip's first cue every mouth layer gets a key; after that each change of shape keys only the two layers that swap.

## Timing tools

| Setting | Default | What it does |
|---|---|---|
| `lead_frames` (op: `leadFrames`) | 1 | Each shape starts this many frames before its sound. Mouths move ahead of what we hear; 1–2 frames feels right in most films. 0 = exactly on the sound. |
| `min_frames` (`minFrames`) | 1 | A shape shorter than this many frames gives its time to the shape before it. Shapes always start on a frame, so 1 only removes nothing-length flashes; 2 removes one-frame flickers (calmer, less exact). |
| `rest_gap` (`restGap`) | 0.25 s | A silence longer than this closes the mouth (X). Shorter pauses hold the mouth as it was. |
| `tail` | 0.08 s | How long a sound lasts past where the model last hears it (the model marks a sound in a frame or two; real sounds last longer). Larger = mouths stay open longer before resting. |

Times line up with the composition's frames: `at` (where the clip starts in the composition) is a frame, and every cue
starts on a frame of the composition.

## Using it

### A person (the screen)

Select the character's rig or group, choose **Lip sync**, pick the voice clip, type the words said (optional) and pick
the mouth layer for each shape you drew. The keys appear on the mouth layers' Opacity rows; move or change any of them
like any other key.

### In a script (`run_script`)

```python
with rig("puppet", w=1920, h=1080):
    rest = path("mouth_X", d=...)            # one layer (or group) per shape, all placed on the face
    closed = path("mouth_A", d=...)
    wide = group("mouth_D", w=40, h=28)       # a group works: teeth and tongue inside it
    ...
    said = lipsync("take.wav", at=0.5, text="Every city keeps one hour.",
                   shapes={"X": rest, "A": closed, "D": wide}, start=0, end=None,
                   lead_frames=1, min_frames=1, rest_gap=0.25, tail=0.08, pronounce=None)
```

The mouth layers must be made earlier in the same script. The call returns the answer below (phones, words, cues). A
re-run merges key by key like every script, so **a person's change to a mouth key stays**, and a held-back change is
reported by `run_script`.

### The operation (`edit_document`)

```json
{"op": "lipsync.apply", "target": "puppet",
 "args": {"source": "C:\\…\\take.wav", "at": 0.5, "text": "Every city keeps one hour.",
          "shapeX": "mouth_X", "shapeA": "mouth_A", "shapeD": "mouth_D", "leadFrames": 1}}
```

Target: the rig or group the mouth layers are in (they must be inside it). The operation **only adds keys**: a mouth
key that is already there (at the same time, or with the same id after a person moved it) is left as it is. To redo a
mouth from scratch, delete its opacity keys first (`key.clear`). For re-runs that update everything except a person's
edits, use the script call.

**Into a swap set.** When the target is a **swap set** (RIG.md › Swap sets) and every mouth layer you name is one of its
children, the operation keys the set's `show` (hold, one key where the mouth changes) instead of each layer's opacity;
the same in a script with `lipsync(..., slot=mouth)` (the slot must be made earlier in the script, with `swap=True`).
Same rule as above: it only adds keys, and a `show` key moved by a person stays. A group that is not a swap set keeps
the opacity keys.

### An agent's ears: `inspect_lipsync`

`inspect_lipsync {"source": …, "text": …, "start": …, "end": …, "at": …, "shapes": {"X": "mouth_X", …}}` answers, in
composition seconds: every **phone** (IPA, with the ARPAbet from the dictionary when the words were given, and its word),
every **word** (start, end), every **mouth cue** after the timing tools and, with `shapes`, which layer shows (and
which shape stood in for a missing one). It changes nothing. Check: does each word start where you hear it? Are the
closed mouths (A) on the M / B / P? Then look at frames (`look_frame`, `look_sheet`) and play the render with the sound.

## Cost

- The first run on a clip loads the model (632 MB on disk, fp16; its memory use while running is not measured yet), works the
  clip out and releases the model before answering. A 3 s clip took 2.9–5.4 s on this laptop's CPU, model loading
  included; on the GPU (DirectML, the default when `device.json` next to the model says `dml:…`) it is a few seconds
  for a line. It refuses to start with under 2.5 GB of free memory. Treat it as a GPU job (`heavy.ps1 … gpu`).
- After that: the cache (a few kB of JSON per clip). The keys cost nothing to play.
- Long audio is worked in 20 s pieces. Forced alignment runs over the whole clip at once: give it a line or a few
  lines (up to a minute or so), not a whole film.

## Files and settings

- Model folder: `ROSTRUM_PHONES_DIR`, else `~/.rostrum/models/wav2vec2-lv60-espeak-fp16/` (`model_fp16.onnx`,
  `vocab.json`, `device.json`). `ROSTRUM_AI_DEVICE` (`cpu`, `dml:0`, `dml:1`) forces a device.
- Dictionary: `ROSTRUM_CMUDICT`, else `~/.rostrum/models/cmudict-7479086/cmudict.dict`.
- Runtime: `pip install rostrum_core[lipsync]` (onnxruntime-directml on Windows, onnxruntime elsewhere; numpy, scipy,
  soundfile).
- On the CPU, onnxruntime 1.24's full graph fusion breaks on this fp16 model, so the CPU runs with basic
  optimisation only (`model.py`).

## Not yet

- **A Sound voice line as the source.** Today `source` is a WAV file: for a RostrumSound voice line, give its made take
  (`render_voice` answers with the file) and the line's words. Reading a Sound document's line id directly needs
  `rostrum_sound` in the 2D environment.
- **`at` as a shared marker** ("line 1"): today it is seconds.
- Languages other than English with words (free decoding already hears any language).
- A shared free-memory check in `rostrum_core` (this module and `rostrum_sound/voice.py` each have the same few lines).
