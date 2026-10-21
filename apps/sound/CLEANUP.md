# Cleanup in RostrumSound

Clean up recorded audio: keep only the dialogue, take out background noise or the room's echo, or split a song into
its stems (vocals, drums, bass, other). The clip keeps its **original file**; its cleanup settings say what the
cleaned take is made of. The cleaned take is made once on request and kept in a cache, so playing and rendering only
read it (nothing is made while you play or render).

## The clip's cleanup fields (inspector group "Cleanup")

| Field | Label | What it does |
|---|---|---|
| `stem` | Play one stem | `none` (the whole clip), `vocals`, `drums`, `bass`, `other`: the clip plays that one stem |
| `isolate` | Keep only the dialogue | The voice separated from music and effects. Absent while a stem is chosen (a stem already separates) |
| `denoise` | Noise reduction | 0..1: steady background noise out (hiss, hum, room tone); 0 = off |
| `dereverb` | Reverb reduction | 0..1: the room's echo out; 0 = off |
| `useCleaned` | Use cleaned take | On (default): the clip plays its cleaned take; off: the original file. Shown only while a step above is set |

The steps run in this order: stem or isolate (separation), then noise, then reverb. Each step is its own cache entry,
so changing the reverb amount redoes only the reverb step.

## Clean a clip, make it, hear it

**A person** (Timeline): select a clip, open the Cleanup group in the inspector, set what you need. Make the cleaned
take, then play. To compare, switch **Use cleaned take** off and on.

**An agent** (MCP, or `edit_document` / `apply`):

1. `clip.set` on the clip: `denoise`, `dereverb`, `isolate` or `stem` (one call, one undo step).
2. `render_cleanup` (MCP tool; optional `ids` = clip ids, left out = every clip that plays a cleaned take). A job: it
   makes each missing take, one clip at a time, and answers per clip: `id`, `media` (the original), `file` (the
   cleaned take), `generated` or from the cache, and `steps` (each step's engine and file). Python:
   `rostrum_sound.clean_clips.make_clips(doc, ids)`, or for one file `rostrum_sound.cleanup.make(file, recipe)`.
3. `look_cleanup` to hear the difference (below), then `render_mix` and the other look tools.

**Split a song into stems:** `clip.split_stems` on a clip adds four tracks right under its track, named
`<track> · vocals` (… drums, bass, other), each with a copy of the clip (same file, time, in-point, length, fades,
level) playing that stem. The original clip's volume goes to 0, so nothing is heard twice; its track and other
clips are untouched. One undo step. Running it again on the same clip fails (`is already split into stems`): delete
those tracks first to split again. Then `render_cleanup` makes the stems (all four are made together, once).

## Listening: look_cleanup

- `clip`: that clip's file before vs its cleaned take, plus its four stems when it plays a stem or they are made.
- `before` + `after`: any two WAVs. `stems`: `{name: wav}` to check. `reference`: `{name: wav}`, the true parts, to
  score the stems (SDR).

It answers, before and after: **noise floor** (the quiet 10th percentile of 50 ms level frames, dB), **speech level**
(the 90th percentile), the **gap** between them, and the **reverb tail** (how far the level falls in the 200 ms after
the sound stops: bigger = drier), with the change (after minus before). For stems: each stem's level, **leakage** (for
every pair, the correlation of their 50 ms level envelopes: near 0 = independent, near 1 = one is heard in the other)
and with reference stems the **SDR** in dB. Pictures: before / after spectrograms stacked on one colour scale with the
level line, floor and speech level drawn; the stems' levels over time, one row each. They are written to
`<project folder>/renders/<item>/look/` and returned as the reply's files.

## When something is missing (it fails loudly)

- Playing or rendering a clip whose cleaned take is not made: `clip "dlg.c1000"'s cleaned take is not made yet`, with
  how to make it (the `render_cleanup` tool, `rostrum_sound.cleanup.make`) or to switch `useCleaned` off. The original is
  never played silently in its place.
- `render_cleanup` with a clip id that has no step set: `has no cleanup step set`. An unknown id names the known ones.
- A model that is not installed, too little free memory or a step that fails: the job fails, names the clip and the
  step, and the cache keeps nothing from it.
- `look_cleanup` on a clip whose take or stems are not made: `is not made yet`, run `render_cleanup` first.

## Where things are

- Cleaned takes: the shared cache (`rostrum_core.cache`), `~/.rostrum/cache/cleanup/<key>/` (`ROSTRUM_CACHE_DIR`
  moves it), each with `entry.json` (the step, engine, input and settings). The key is a hash of the input file's
  content, the step's model and version and its settings, so the same take is never made twice; over the cache's size
  cap, the least recently used entries go first.
- A clip's `media` is used as written (an absolute path, or relative to the folder the app runs in), the same file the
  engine opens; the cache finds the take by the file's content.
- Code: `python/rostrum_sound/cleanup/` (the steps and the chain), `clean_clips.py` (which take a clip plays),
  `doc/fields_cleanup.py` (the fields), `doc/ops_cleanup.py` (`clip.split_stems`), `mcp/tools_cleanup.py`,
  `listen/cleanup.py` and `listen/cleanup_draw.py` (the measures and pictures).

## Models and cost

See [`MODELS.md`](MODELS.md).
