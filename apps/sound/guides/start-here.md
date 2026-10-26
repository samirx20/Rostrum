# Start here: RostrumSound for agents

## How every reply reads

- Every reply has `ok`, `summary` (read it first), `data`, `files` (absolute paths) and `warnings`. A failure has `ok: false`
  and an `error` with `code`, `where`, `problem`, `accepted` and a hint. Read `accepted`: it lists what would have worked.
- **Guides.** `inspect_guide` takes one argument, `topic`: `{"tool": "inspect_guide", "arguments": {"topic": "writing-music"}}`.
  Everywhere a guide writes `inspect_guide 'x'` it means that call with `topic: "x"` (there is no `name` argument). With no
  `topic` it lists every guide.
- Tool names are `<verb>_<thing>`: `inspect_*` reads, `edit_*` and `run_*` change the document through operations,
  `render_*` makes files as a job, `look_*` lets you see or hear a result. Every tool and its arguments: `inspect_tools`.
- `inspect_operations` lists every operation and its arguments (`name: "master.set"` for one). `edit_document` applies a
  list of them, all or nothing.
- The song you work on is the item `cue` unless the project has another; `inspect_project` says.
- Your changes carry your client name and are grouped per turn, so a person can review or undo them together.
- `run_script` merges what the script makes into the document. Anything a person moved by hand stays where they put it
  and is listed in the reply as held back; pass `force` with those keys only when you mean to overwrite. Changing only
  the tempo and running again keeps every note (and a person's edits to them): nothing is removed and re-made.
- Long work (`render_mix`) comes back as a job id. Ask with `inspect_job` (`wait_s` up to 25); stop with `run_stop`.

## Writing parts from scratch, or changing what is there

- **A new part, written in a script: the script helpers** (`voice`, `comp`, `arp`, `bass_line`, `drum_grid`; `inspect_guide 'writing-music-tools'`), then `run_script`.
- **Notes that already exist (a person's, or a finished script's): the operations** `note.chord`, `note.invert`, `note.strum`, `note.arpeggiate`, `note.transpose`, `note.fit_key`, `note.duplicate`, `note.humanize`, `hit.humanize`, `hit.fill`, and `track.feel` (swing and looseness, one track's playing, notes untouched), through `edit_document`. They change the notes in place; a script would rewrite them. `note.humanize` / `hit.humanize` add on top of whatever looseness the notes already have (a script's own `humanize` included), and a second run with the same seed adds the same amount again: to redo it, undo first or use another seed.
- **Finding the notes to edit: `inspect_notes {track, from?, to?, section?, limit?}`**: one line per note (or drum hit) of the track, `id  time (s, bar.beat)  pitch  length  vel`, for a stretch given in bars `{"bar": 5}`, seconds, beats or a marker (`"#drop"`), or a section's name; capped, then "… N more, narrow the range". Use its ids as targets. A note's id is made from where it started when it was made (`harp.n8438` began at 8.438 s) and stays when the note moves or the tempo changes, so read a note's time from this list, never from its id. `inspect_item` with `detail: "full"` lists every note with its raw values and is long: prefer `inspect_notes`.
- **Making the file: `render_mix`** (a job; `inspect_job` with `wait_s` until done). The mix lands in the project at `renders/<item>/vNNN/<item>_mix.wav` (`.flac` / `.mp3` by `format`; `<item>` is the song's id, `cue` unless the project has another), the next free `vNNN` each time, never overwriting; stems beside it with `stems: true`. The reply's `file` and `files` hold the absolute paths: copy from there. A listening check with `solo` / `mute` goes to `renders/<item>/check/` instead and is not a version. `render_mix` with `what: "midi"` writes the notes as a `.mid` in `renders/<item>/midi/`. Delivery targets, the silent end and ranges: `inspect_guide 'exporting'`.
- The arpeggio steps, orders and octaves are one rule in both. The script's `voice` goes further (drop 2, spread, voice leading); `note.chord` stacks plain tones. Pick by what you start from.

## `edit_document`: whole calls that work

The argument is `ops` (not `operations`): a list of `{op, target, args}`. A track's target is its id (`"drums"`, not `"track.drums"`).
A note or hit operation takes note / hit ids, or a **range target** that names them without ids:
`{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}` is every note on that track that starts from bar 1 up to, not including,
bar 9 (bars count from 1; `from` / `to` left out = the start / the end; a time can also be seconds, `{"beat": 8}` or `"#drop"`).
An empty range fails and says where the track's notes are. Bars are for range targets only: everywhere else a time is seconds
or `{"beat": n}`, a length `{"beats": n}`. Each line below is the complete `arguments` of one `edit_document` call:

- Make a chord on every note of bar 1-8 of a track (a range target: from included, to not; bars count from 1):
  `{"ops": [{"op": "note.chord", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}], "args": {"shape": "minor"}}]}`
- Transpose up a fifth, notes of bars 1-8:
  `{"ops": [{"op": "note.transpose", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}], "args": {"semitones": 7}}]}`
- Strum the chords of a whole track (no from / to = all of it):
  `{"ops": [{"op": "note.strum", "target": [{"track": "guitar"}], "args": {"gap": 30, "soften": 0.1}}]}`
- Repeat bars 1-4 once, 16 beats later; notes you name by id work too:
  `{"ops": [{"op": "note.duplicate", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 5}}], "args": {"by": {"beats": 16}, "times": 1}}]}`
- Fill a hi-hat row (the TRACK is the target; from and to are beats here, not bars):
  `{"ops": [{"op": "hit.fill", "target": ["drums"], "args": {"drum": "hat", "every": 0.5, "from": {"beat": 0}, "to": {"beat": 32}, "vel": 0.8}}]}`
- Repeat the drum hits of bars 1-4 three times:
  `{"ops": [{"op": "hit.duplicate", "target": [{"track": "drums", "from": {"bar": 1}, "to": {"bar": 5}}], "args": {"by": {"beats": 16}, "times": 3}}]}`
- Add a section (at / end, not start) and a marker:
  `{"ops": [{"op": "section.add", "args": {"name": "verse", "at": {"beat": 0}, "end": {"beat": 32}}}, {"op": "marker.add", "args": {"name": "drop", "at": {"beat": 32}}}]}`
- Set a track's volume in dB:
  `{"ops": [{"op": "track.set", "target": ["drums"], "args": {"volume": {"db": -4}}}]}`

The range is read as the song was before the call. Operations' own arguments: `inspect_operations` with `name`.

## The order of work

1. **Read** `inspect_guide` with `topic: "writing-music"` (the craft), then `topic: "script"` (the names a script knows). Scoring to a picture:
   `scoring-to-picture`.
2. **Pick the sounds.** `inspect_engine` (`what: "names"`, the default; there is no `instruments`) lists every instrument marked *recorded* or *synthesized*, the part each suits and
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
   `look_music` (`what`: `events`, `beats`, `pitch`). `pitch` (with `track`) checks a chord part note by note; the loudness summary names the loudest moment and its time and has an `ending` line (see 8). Which tool answers which question: `listening`. Whether it is musical is
   for a person to hear; say so in your report.
7. **Fix, render again.** Change one thing at a time. To change a value a script made, edit the script and run it again under
   the same `name`; to change one value, use `edit_document`.
8. **End it cleanly** (`topic: "script"`, section "Ending a song") and render the last version. Check the end with
   `look_sound` (`what: "loudness"`): its `ending` line gives the level of the last 0.5 s, whether the file still sounds above
   -50 dBFS at its end, and whether the last 50 ms drop faster than the fade. Still above -50 dBFS with a fast last-50-ms drop is a cut: lengthen
   the song or add `master(fadeOut=...)`. Below -50 dBFS (or no fast drop) is a clean end.

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

## Loudness: louder or cleaner (`maxLimit`)

A new song has gentle limiting on: the master's limiter may pull the loudest moment down by at most `maxLimit` (default 2 dB;
the screen's **Most limiting**; the document takes 0 to 12 dB). A mix whose peaks stand further above its average loudness is
turned down as a whole instead, so it lands under its target (for a quiet piano or peaky drums, 1 to 3 dB under is normal) and
the `render_mix` reply says how far and names the best of three ways to reach it:

- **Cleaner:** turn the track that sets the peaks down (`look_sound` `loudness` names who drove the limiter's worst moment; `levels`
  shows each track's level), or write its loudest notes softer. The balance of the mix changes, and no limiting is added.
- **Tamed:** `edit_loudness {"apply": "tame_peaks"}` puts a gentle compressor first on the most peaked track (two or three when one
  is not enough), its threshold found by re-rendering and its makeup measured so the track keeps its loudness against the rest:
  the target within the master's `maxLimit`, the balance as written. Do not guess compressor settings by hand.
- **Louder:** `edit_loudness {"apply": "keep_balance"}` sets `maxLimit` to the value that reaches the target (one call, measured; do not set it by hand). More limiting means a
  flatter, denser master; 4 to 6 dB is a loud, pressed one. The balance between tracks does not change.

`{"apply": "best"}` takes the one the reply names best: keep_balance when it raises `maxLimit` by 1 dB or less, else
tame_peaks (the master stays transparent). Raise `maxLimit` further only when the dense sound is what the piece wants.

**Under the target: call `edit_loudness` first.** It reads the last render and answers three ways with measured numbers
and the exact `edit_document` call for each: `keep_balance` (the `maxLimit` that reaches the target, no track moves),
`tame_peaks` (the gentle compressor above, threshold and makeup measured, balance and limit kept) and `trim_track` (the smallest cut of the most peaked track, or the `track` you name, that reaches it within the current
`maxLimit`, tried with offline renders). `{"apply": "best"}` (or an option's name) makes that edit as one
step. Never rebalance or raise `maxLimit` by guess. Turning every track up does not make the mix louder while the target
is on: the master sets the level, and only how far the peaks stand above the average decides the limiting.

## Which arguments go with which `what`

`look_sound` and `look_music` are one tool each; `what` picks the question and the call is checked against that question's own
arguments (a wrong one is refused with the list that works).

| Call | Arguments that work |
|---|---|
| `look_sound` `loudness` | `item`, `wav` only (no `start`, `end` or `track`: it reads the whole file; the short-term curve and `loudest` give times) |
| `look_sound` `levels`, `low_end` | `item` only (they read every stem of the last render) |
| `look_sound` `clash` | `tracks` (up to 12), `within_db`, `floor_db`, `min_over_db`, `min_length`, `detail` |
| `look_sound` `spectrum` | `track`, `marks`, and `start` with `end` together (both or neither) |
| `look_sound` `stereo` | `section` (seconds per section) |
| `look_music` `events` | `track`, `expect`, `tolerance`, `by_stem`, `detail` |
| `look_music` `beats` | `track`, `stems`, `division`, `beats_per_bar`, `tolerance` |
| `look_music` `pitch` | `track` (needed to compare with the written notes), `fmin`, `fmax`, `cents_tolerance`, `timing_tolerance` |
| `look_music` `harmony` | `track`, `per` (`bar` or `beat`), `key`, `source`, `checks` |

All of them take `item` (when more than one song is open) and, except `levels`, `low_end` and `clash`, `wav` (any file instead of the last render).
`look_music events` finds an onset only where a sound starts clearly: a soft or masked start (a held chord under another)
has none, and the reply then names another stem's nearest onset; read the stem's own row. `beats` reads the document's tempo
as the answer; the `heard_bpm` from the sound alone can be a related tempo (half, double, 2/3, 3/2) on a groove with rolls.
