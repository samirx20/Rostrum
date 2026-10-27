# Voice in RostrumSound

Spoken lines, made on this computer. The document holds the **words and when they start**; the audio is made once on
request and kept in a cache, so a render only reads it (nothing is made while you play or render).

## Add a line, make it, hear it

**A person** (Instruments page): a track whose instrument is `voice` shows its voice, language and style, and its
lines (text + time). A green dot means the audio is made; amber means it is not. **Make voice** appears only while a
line has no audio; it runs in the background and shows what it is doing (a failure is red on the card). Click a line
to edit its words, time, take number, level and fades in the inspector.

**An agent** (MCP, or `edit_document` / `apply`):

1. `track.add` with `instrument: "voice"`, `voice` (one of the presets), `language`, `style` (plain words:
   how it should sound).
2. `line.add` on the track: `text`, `at` — seconds, `{"beat": 8}` or a marker, `"#drop+0.5"` (the same times notes
   use, so a line follows its marker when the marker moves). `seed` is the take number: the same words with another
   seed are another reading. `line.set` changes a line, `line.remove` deletes it.
3. `render_voice` (MCP tool; optional `ids` = line ids). Makes every missing take, one at a time, and answers per line:
   id, file, seconds, `generated` or from the cache, `start` and `end` in seconds, so the next line can be timed
   to follow it. Python: `rostrum_sound.voice_lines.make_lines(doc, ids)`.
4. `render_mix`, then listen with the look tools (`look_music` (`what: "events"`) with `expect`, `look_sound` (`what: "loudness"`), `look_sound` (`what: "levels"`)).

Rendering or playing a document with a line whose audio is not made fails loudly: `voice line "vo.line_2" is not made
yet` plus how to make it. A line is never skipped silently. Changing a line's words, the track's voice, style or
language, or a line's seed means that line needs making again (its old audio stays in the cache).

## Where things are

- Takes: in the shared cache (`rostrum_core.cache`): `~/.rostrum/cache/voice/<key>/take.wav` and `entry.json` (the
  recipe, size, how long it took). The key is a hash of the recipe and the engine version, so the same recipe is never
  made twice; over the cache's size cap, the least recently used takes go first.
- Model: Qwen3-TTS 1.7B (CustomVoice, Q6_K) in `~/.rostrum/models/qwentts` (`ROSTRUM_QWENTTS_DIR` to move it),
  run by `qwen-tts.exe` (qwentts.cpp). The model loads for the line and is released when it ends.
  `ROSTRUM_TTS_DEVICE` picks the device (`Vulkan0`, `CPU`).
- Presets: ryan, aiden, vivian, serena, uncle_fu, dylan, eric, ono_anna, sohee. Languages: auto, english, chinese,
  japanese, korean, german, french, russian, portuguese, spanish, italian.

## Each word's time (for 2D's voice-over row, lip sync and captions)

The speech model that made the line cannot say where each word falls, so a **second model listens to the made take**:
Parakeet TDT v3 (int8, Apache-2.0 / CC-BY-4.0 weights) through sherpa-onnx, on the CPU, about 7 s for a 6 s line
(measured), loaded for the take and released. It runs **once on request** and the words are **stored in the shared
cache** (`~/.rostrum/cache/voice-words/<key>/words.json`; key = hash of the take's own key and `voice_words.ENGINE`),
so asking again reads them and a re-render never runs the model. Models: `~/.rostrum/models/parakeet-tdt-0.6b-v3`
(`ROSTRUM_ASR_DIR` to move it).

- **Agent:** `render_voice` first (the take must be made), then the MCP tool `render_voice (what "words") {item?, ids?, read_only?}`
  (a job). `read_only: true` only reads what is stored and fails loudly for a line not heard yet. Answer per line:
  `id, track, text, start, end, words: [{word, start, end}], heard_now`. Times are **song seconds** (the line's start
  added, markers resolved), the same clock as `render_voice`'s `start` / `end`.
- **Python (what 2D reads):** `rostrum_sound.voice_words.read(doc_or_root, ids=None)` never runs the model; `compute(...)`
  hears what is missing. Same rows. A line whose take is not made, a missing model and a take with no words are loud
  errors (`NOT_FOUND`, `MODEL_MISSING`, `JOB_FAILED`) saying what to do; nothing is stored then.
  2D's `voice_words.lines()` can add `words` to each row by calling `voice_words.read` under the same
  `markers.project(folder)` it already uses (not done here: 2D is Team Hem's).
- When the model hears as many words as the line has, the **line's own spelling** is kept with the heard times;
  otherwise the heard words are kept ("streetlight" can come back as "street light,").
- A word's **start** is the model's frame (80 ms steps); its **end** is the next word's start, or its last piece plus
  0.16 s, so a pause after a word is counted in it. Good for captions and for cutting to a word; for lip sync use
  the start times and the loudness of the take.

## Main mix and 2D's cues on Sound's screen

- **Make this the main mix:** the song the other apps play with the picture. Tool `run_set_main_mix {item?}` and the
  screen's Song panel (nothing selected): the title reads "Song · Main mix" when it is, and the button
  **Make this the main mix** is there only when it is not (also in Ctrl+K). A mark on the project
  (`rostrum_core.project.set_main`), not a song edit, so no undo step. Python: `rostrum_sound.main_mix`.
- **Cues from 2D:** the track 2D's "Add a sound here" writes (`cues_2d`, named "Cues from 2D") is an ordinary track in
  the arrangement. A clip whose start is written on a marker (`"#Logo lands+0.1"`) shows a small diamond and the
  marker's name before its file name, and the Inspector says "Clip · tied to marker “Logo lands”" (the marker's name
  cut to 14 characters there, whole on the block). Drag the marker and the clip follows.

## Cost (measured)

About 3 GB of GPU memory and a gate of 2.5 GB free RAM (it refuses, loudly, below that). On this laptop's RTX 3050 a
5.9 s line was made in 11.6 s. One line at a time; never more than one voice job at once.

## How long a line takes (estimate before making it)

`voice_estimate.estimate(text, language)` (MCP: `render_voice` with `what: "estimate"`) says how long words will take before
they are made: seconds = 0.1 breath + syllables x rate + 0.15 per comma, colon or semicolon + 0.45 per sentence end after
the first. Rate per syllable: 0.245 s in Latin scripts, 0.215 s per Chinese character, 0.135 s per Japanese kana (a kanji
counts two), 0.2 s per Korean block. Range = the estimate +/- 22 % (at least 0.3 s).
Measured on 17 real takes (Qwen3-TTS: aiden, ryan, vivian, ono_anna; English, German, Chinese, Japanese; with and
without a style): 13 % off on average, 15 of 17 inside the range. The same words differ 10-25 % between seeds (one
Chinese line of 17 characters came out 3.1 s and 5.4 s in two readings), and a style like "slow" or "excited" shifts the
pace; Korean was not measured. The made take's `seconds` is always exact.

## Licences

Qwen3-TTS weights: Apache-2.0. qwentts.cpp: MIT. Nothing here is GPL.
