# Start here: RostrumSound for agents

## How every reply reads

- Every reply has `ok`, `summary` (read it first), `data`, `files` (absolute paths) and `warnings`. A failure has `ok: false`
  and an `error` with `code`, `where`, `problem`, `accepted` and a hint. Read `accepted`: it lists what would have worked.
- Tool names are `<verb>_<thing>`: `inspect_*` reads, `edit_*` and `run_*` change the document through operations,
  `render_*` makes files as a job, `look_*` lets you see or hear a result. Every tool and its arguments: `inspect_tools`.
- `inspect_operations` lists every operation and its arguments (`name: "master.set"` for one). `edit_document` applies a
  list of them, all or nothing.
- The song you work on is the item `cue` unless the project has another; `inspect_project` says.
- Your changes carry your client name and are grouped per turn, so a person can review or undo them together.
- `run_script` merges what the script makes into the document. Anything a person moved by hand stays where they put it
  and is listed in the reply as held back; pass `force` with those keys only when you mean to overwrite.
- Long work (`render_mix`) comes back as a job id. Ask with `inspect_job` (`wait_s` up to 25); stop with `run_stop`.

## The order of work

1. **Read** `inspect_guide 'writing-music'` (the craft), then `script` (the names a script knows). Scoring to a picture:
   `scoring-to-picture`.
2. **Pick the sounds.** `inspect_engine` lists every instrument marked *recorded* or *synthesized*, the part each suits and
   where it sounds best, plus every effect's settings with units. `inspect_engine` with `what: "instrument"` and ONE of
   `builtIn`, `model`, `synth`, `sfz`, `kit`, `kitSfz` (for example `builtIn: "marimba"`) gives one instrument's range.
3. **Write the song** with `run_script`. The argument is `source` (the Python text); `name` is optional (see below):

   ```json
   {"tool": "run_script", "arguments": {"name": "cue", "source": "tempo(96); length(bar(9))\nt = track('keys', builtIn='piano')\nt.note('D4', at=bar(1), dur=beats(4))"}}
   ```

4. **Look before you render.** `look_arrangement` (a picture of every part against the bars and markers),
   `look_music` with `what: "harmony"` (chords and range checks on the written notes), `inspect_diagnose` (what is wrong
   with the song).
5. **Render.** `render_mix` with `stems: true`, then `inspect_job` until it is done.
6. **Look at the result.** `look_sound` (`what`: `loudness` by default, `levels`, `low_end`, `clash`, `spectrum`, `stereo`) and
   `look_music` (`what`: `events`, `beats`, `pitch`). `pitch` checks a chord part note by note; the loudness summary names the loudest moment and its time. Which tool answers which question: `listening`. Whether it is musical is
   for a person to hear; say so in your report.
7. **Fix, render again.** Change one thing at a time. To change a value a script made, edit the script and run it again under
   the same `name`; to change one value, use `edit_document`.
8. **End it cleanly** (`inspect_guide 'script'`, section "Ending a song") and render the last version.

## Rules that save a render

- **`run_script` `name`.** The same name replaces and merges what that script made before; a new name adds a second copy.
  Keep one name per song.
- **A call list stops at the first failed step.** Run through `devtools/mcp_session.py` (or `shared/mcp/call.py`), a list of
  calls stops at the first reply with `ok: false`: the later steps are not run, the output says which step failed and which
  were not run, and the exit code is 1. So a render never runs on a song the failed script did not change. If you call
  tools one by one yourself, read each `ok` before the next call.
- **Names.** Track, section and other item ids: 1 to 64 letters, digits, `_`, `.` or `-`, no spaces (`final_chorus`, not
  `final chorus`). Marker names are free text: spaces and most characters work (`"logo lands"`, then `"#logo lands"`).
- **Times and lengths.** A bare number is seconds. A time in beats is `beat(8)` in a script (`{"beat": 8}` in an operation); a
  length in beats is `beats(2)` (`{"beats": 2}`): singular for a time, plural for a length.
- **Volume.** A bare number is gain 0 to 4 (1 = 0 dB); in dB write `{"db": -6}`.
- **Effect settings** are plain numbers in the units `inspect_engine` lists: a compressor's `threshold` is dB as a plain number
  (`-24`, not `{"db": -24}`), `attack` and `release` are in seconds (`0.01`, not `10`).
