# Cleaning a recording

How to take noise, room echo or music out of a recorded take and check what it did. The tool reference is
inspect_guide `cleanup` and `apps/sound/CLEANUP.md`; this page is the job from start to finish.

## 1. Record or bring in the take

- **On the screen:** arm a track (Rec on its header), press Record or R. The mix plays from the playhead and the
  take becomes one clip (one undo step) in `<project>/media/`. Count-in, punch-in over a range and the input level
  are in the record controls. Use headphones: a take recorded against speakers hears them.
- **As an agent:** `clip.add` with `media` = the file and `at` = where it starts.

## 2. Find what is wrong before fixing it

- `look_spectrum` on the clip's file (`wav`): steady lines are hum or whistle (`hum_lines`), a raised floor across all
  frequencies is hiss or room tone.
- `look_cleanup` with `before` = the file and no `after` gives its noise floor, speech level, their gap and the reverb
  tail (how fast the sound dies after a word: a slow fall is a roomy recording).
- Listen for what numbers miss: clicks, mouth noise, a door. Note the times.

## 3. Choose the steps

Each is a field on the clip (`clip.set`), and they run in this order:

| Problem | Field | Notes |
|---|---|---|
| Music or effects under the voice | `isolate` | keeps the dialogue only |
| You want one part of a song | `stem` (`vocals`, `drums`, `bass`, `other`) | or `clip.split_stems` for all four as tracks |
| Steady noise (hiss, hum, air conditioning) | `denoise` 0..1 | start low; too much makes the voice watery |
| Room echo | `dereverb` 0..1 | too much makes the voice dry and pinched |

Change one step at a time. Each step is cached on its own, so changing `dereverb` remakes only that step.

## 4. Make the cleaned take and compare

- **Agent:** `render_cleanup` (optional `ids`), then `look_cleanup` with `clip` = the clip id: before / after numbers
  and spectrograms on one colour scale. A bigger gap between floor and speech = cleaner; a bigger reverb-tail fall = drier.
- **Screen:** click the clip, then **Clean up…** at the top of the settings panel: the **Cleanup** group opens with the presets **Dialogue only**, **Less noise** and **Less echo**. "Make cleaned take" appears under the settings panel while the clip has a step and no take yet; until it is made, the song keeps playing and the clip plays its original. Switch
  **Use cleaned take** off and on to compare by ear.

Numbers can say the noise went down; only listening says whether the voice still sounds like the person. Watch for
watery, metallic or lisping artefacts, and back the amount off when you hear them.

## 5. Put it in the mix

The cleaned clip then goes through the track's chain like any clip: an EQ to take out boom or harshness, a compressor
to even the level, a duck on the music under it (`duck.add` with `under` = this track, `voice` on).
