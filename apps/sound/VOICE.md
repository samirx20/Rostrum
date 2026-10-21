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
4. `render_mix`, then listen with the look tools (`look_events` with `expect`, `look_loudness`, `look_levels`).

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

## Cost (measured)

About 3 GB of GPU memory and a gate of 2.5 GB free RAM (it refuses, loudly, below that). On this laptop's RTX 3050 a
5.9 s line was made in 11.6 s. One line at a time; never more than one voice job at once.

## Licences

Qwen3-TTS weights: Apache-2.0. qwentts.cpp: MIT. Nothing here is GPL.
