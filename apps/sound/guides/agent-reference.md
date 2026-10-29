# Agent reference: the loop, replies, names and units in full

The long companion of `start-here` (read that first: it is the short version). Everything here is detail: how replies read,
the instrument and kit names, whole `edit_document` calls, the order of work, units, loudness and which arguments go with
which `what`. Each tool's full words: `inspect_guide 'tools-in-detail'`.

## The loop: the whole piece is one script

1. **Write the whole piece as one Python script** (tempo map, sections, markers for the sync points, every track's notes,
   dynamics and effects, the mix, the master target) and run it with `run_script`, **one `name` for the song**, with
   `look: true` (it renders and listens).
2. **Read the reply.** It carries the render's listening check: loudness, the weakest asked moments with a fix for each,
   and faults such as "leading silence", "tempo far from the brief's" (give the brief's with `expect`:
   `{"kind": "tempo", "bpm": 96}`) and "stop lands soft".
3. **Edit the script and run it again under the same name.** A removed track, note, effect or marker disappears, a new
   tempo moves everything written in beats, nothing is copied. A **new name** that makes the same tracks is refused, naming the script to run under.
4. Repeat until the check is clean and the minutes are used. `edit_document` is for one-off touch-ups: one value, or a note a
   person asked you to leave alone. A value you set there is held against the script's (the reply says so); keep each setting in one place.

The shape of a script is a technique, not a template (`inspect_guide 'script'` has every name):

```python
tempo(96); key("F major"); length(bar(17)); marker("lift", at=bar(9))     # the song's map first
CHANGES = {1: "F", 3: "Bb", 5: "Dm7", 7: "C"}                              # chord changes as data you can edit
def section_a(first, last): ...                                            # a section is a function: call it where it plays
for b in range(first, last): ...                                           # loops over bars write the repeating parts
for t in (keys, pad): t.humanize(seed=2)                                   # then one pass for how it is played
master(loudness=-16, truePeak=-1)                                          # the mix and master last
```

Landing a sound on a time without bending the tempo: `downbeat(bar(n), at=T)` puts bar n at T seconds (music before bar 1
is a pickup), `land(bar(n), at=T, ramp_from=bar(m))` glides the tempo so bar n lands at T; or write the moment as a marker
(`marker("hit", at=31.5)`, `at="#hit"`). Details: `inspect_guide 'script'`, "Landing on a time".

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
- The song you work on is the item `song` in a new project (`inspect_project` says which items there are).
- Your changes carry your client name and are grouped per turn, so a person can review or undo them together.
- `run_script` merges what the script makes into the document. Anything a person moved by hand stays where they put it
  and is listed in the reply as held back; pass `force` with those keys only when you mean to overwrite. Changing only
  the tempo and running again keeps every note (and a person's edits to them): nothing is removed and re-made.
- Long work (`render_mix`) comes back as a job id. Ask with `inspect_job` (`wait_s` up to 25); stop with `run_stop`. Or pass `"wait": true` (or a number of seconds) to `render_mix` or any `look_*` tool: it waits for its job and answers with the finished file (past the wait: still running, with the job id).

## Writing parts, or changing what is there

- **Write parts in the script:** the script helpers (`voice`, `comp`, `arp`, `bass_line`, `drum_grid`; `inspect_guide 'writing-music-tools'`), then `run_script`.
- **Touch-ups on notes that already exist (a person's, or one note of the script's): the operations** `note.chord`, `note.invert`, `note.strum`, `note.arpeggiate`, `note.pedal` (the sustain pedal lifted on each chord change, down again `catch` beats later), `note.ramp_velocity` (a crescendo or fade: `start` on the first note, `end` on the last, by time), `note.transpose`, `note.fit_key`, `note.duplicate`, `note.humanize`, `hit.humanize`, `hit.fill`, and `track.feel` (swing and looseness, one track's playing, notes untouched), through `edit_document`. They change the notes in place; the next run of the script keeps them and lists them as held back. `note.humanize` / `hit.humanize` add on top of whatever looseness the notes already have (a script's own `humanize` included), and a second run with the same seed adds the same amount again: to redo it, undo first or use another seed.
- **Finding and checking notes:** `inspect_notes {track, from?, to?}` lists a track's notes (ids, time, pitch, length, vel; read a note's time from the list, never from its id); `inspect_note_changes {since}` shows what an edit really changed; `edit_history_go {to}` goes back to an earlier step (your own steps only); `edit_undo` takes back the last one. Arguments: `inspect_tools`; the craft: `inspect_guide 'writing-parts'`.
- **Making the file: `render_mix`** (a job; `inspect_job` with `wait_s` until done). The mix lands in the project at `renders/<item>/vNNN/<item>_mix.wav` (`.flac` / `.mp3` by `format`; `name` gives the file another name, like the Export sheet's name box; `<item>` is the song's id, `song` in a new project), the next free `vNNN` each time, never overwriting; stems beside it with `stems: true`. The reply's `file` and `files` hold the absolute paths; `folder` (an absolute path, made when missing) also copies the mix there under `name` (stems beside it in "<name> stems"), so there is never a shell copy to refuse; `copied` in the reply lists the new files. Replies open `NOT DONE:` with each fault (id, when, fix) or `DONE:`. A delivery (`render_mix`, or `run_script` `look` with `folder`) is refused while a fault is open (the file is kept as `<name>.NOT-DONE.wav`) unless `keep: {id: "why"}` explains it, and every why quotes the brief (in quotes, or 3 or more of its words in a row) where it asks for that fault: `brief("...")` in the script stores the brief's own words on the song (a dull top is kept for "dark, muffled", never for "a piano chord progression"); with no brief stored, or a why that does not quote it, the keep is refused and the fault's fix says why; a fault on the moment the brief asked for (its words say so) can be kept only after a render that tried the fix, and only when it measures within the stated distance of passing (its words say what passes and from where it may be kept); further off, fix it, or move the moment itself in the script (`moment(name, at=...)` or `expect`) when the brief allows another time. **A song with a `length` renders exactly that long:** trim never cuts below it, and a ring-out that would run past it is faded out inside it (the reply's warnings say by how much; `ring_past_length: true` lets the file run on up to 2 s past it while the ring dies away, a number up to that many seconds). A listening check with `solo` / `mute` goes to `renders/<item>/check/` instead and is not a version. `render_mix` with `what: "midi"` writes the notes as a `.mid` in `renders/<item>/midi/`. Delivery targets, the silent end and ranges: `inspect_guide 'exporting'`. **`render_video` (2D) does not use this file:** it renders the song's current document again (the same sound, cached when the song is unchanged); so a `render_mix` is for you to check and deliver, and `run_set_main_mix` only says which song goes under the picture.
- The arpeggio steps, orders and octaves are one rule in both. The script's `voice` goes further (drop 2, spread, voice leading); `note.chord` stacks plain tones. Pick by what you start from.

## Instrument and kit names

`builtIn="…"` takes exactly these names (the second column lists other names for the same sound; a track's id, like `horns`,
is not an instrument name: write `builtIn="horn"`). `kit="…"` takes the bare kit name (`kit="classic"`; `kit:classic`, as
`inspect_engine` writes it, is accepted too). A wrong name is refused with the close ones: `contrabass` points to `basses`,
`uprightBass`, `doubleBass`. Played instruments (`model=`) and synth waves (`synth=`) are other forms: `inspect_engine`. A
test keeps this list equal to the engine's table (`tests/test_sound_names.py`). Ranges and what suits which part: `inspect_engine`
with `name` (one instrument), `inspect_engine` what `instrument` (its recorded range). Recorded instruments are samples; synth ones play any key.

| Name | Also accepted as | What it is |
|---|---|---|
| `piano` | `grandPiano`, `acousticPiano`, `feltPiano` | concert grand (Salamander, Yamaha C5), A0–C8 |
| `electricPiano` | `wurlitzer` | Wurlitzer EP200 electric piano |
| `rhodes` | | Fender Rhodes Mark II electric piano, E1–E7 (F4–C#6 were not recorded: they are stretched from E4 and D6 and blended across B4–G5, so the tone darkens evenly there; a mono recording, widen it with `chorus` or `tremolo`) |
| `organ` | `drawbarOrgan` | drawbar organ |
| `pipeOrgan` | | pipe organ, loud registration |
| `guitar` | `nylonGuitar` | classical nylon-string guitar |
| `acousticGuitar` | `steelGuitar`, `archtopGuitar` | steel-string archtop guitar |
| `electricGuitar` | `cleanGuitar` | clean electric guitar |
| `bass` | `electricBass`, `bassGuitar` | fingered electric bass |
| `uprightBass` | `doubleBass` | plucked double bass (pizzicato) |
| `strings` | `analogStrings` | string section, basses to violins by pitch, sustained |
| `spiccatoStrings` | | the same section, short and bouncy |
| `violins` | | violin section |
| `violas` | | viola section |
| `cellos` | | cello section |
| `basses` | | contrabass: bowed, the orchestral bass (`uprightBass` is the plucked jazz one) |
| `violin` | | solo violin |
| `cello` | | solo cello |
| `harp` | | concert harp |
| `brass` | `cinematicBrass` | brass section: tuba, trombone to D4, trumpet above (each recorded soft and loud; the horn is `horn`) |
| `horn` | | French horn (the name is singular) |
| `trumpet` | | trumpet |
| `mutedTrumpet` | | trumpet with a straight mute: soft, nasal |
| `trombone` | | tenor trombone |
| `tuba` | | tuba |
| `flute` | | flute |
| `piccolo` | | piccolo |
| `oboe` | | oboe |
| `clarinet` | | clarinet |
| `bassoon` | | bassoon |
| `saxophone` | `tenorSax` | tenor saxophone |
| `harmonica` | | chromatic harmonica (Hohner Super 64) |
| `marimba` | `glassMarimba` | marimba |
| `vibraphone` | | vibraphone, hard mallets |
| `xylophone` | | xylophone |
| `glockenspiel` | | glockenspiel: bright, keep it quiet |
| `tubularBells` | | tubular bells, single strikes |
| `timpani` | | timpani |
| `warmPad` | `pad` | analog synth pad with a slow start (synth) |
| `subBass` | | round analog synth bass (synth) |
| `pluck` | | short analog synth pluck (synth) |
| `choirPad` | | held "aah" voices (synth) |
| `classic.feltPiano` | | the older synthesized felt piano |
| `classic.grandPiano` | | the older synthesized grand piano |
| `classic.warmPad` | | the older synthesized pad |
| `classic.analogStrings` | | the older synthesized string ensemble |
| `classic.spiccatoStrings` | | the older synthesized short strings |
| `classic.choirPad` | | the older synthesized "aah" voices |
| `classic.cinematicBrass` | | the older synthesized brass swells |
| `classic.subBass` | | the older synthesized bass |
| `classic.glassMarimba` | | the older synthesized glassy struck bar |

| Kit (`kit=`) | What it is |
|---|---|
| `drums` | recorded rock kit (MuldjordKit) |
| `studio` | recorded studio kit |
| `jazz` | recorded jazz kit played with brushes: brush snare, stir (`stir`), ride, hats |
| `classic` | the synthesized kit (kick, snare, clap, hat, openHat, cymbal, tom, rim) |

Levels: every plain name starts level-matched for the part it suits (`inspect_engine` with `name` gives its starting level in dB;
`look_sound` levels gives each track's `volume_db` against it). Matching is by loudness of a typical phrase, so a quiet, sparse part
(a vibraphone line at low velocities, a brush pattern) still sits under a dense one: check `look_sound` levels and raise the track.
How the starting levels were measured: `apps/sound/python/devtools/level_match.py` (instruments), `kit_levels.py` and `level_files.py` (kits).

## `edit_document`: whole calls for one-off touch-ups

The argument is `ops` (not `operations`): a list of `{op, target, args}`. A track's target is its id (`"drums"`, not `"track.drums"`).
A note or hit operation takes note / hit ids, or a **range target** that names them without ids:
`{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}` is every note on that track that starts from bar 1 up to, not including,
bar 9 (bars count from 1; `from` / `to` left out = the start / the end; a time can also be seconds, `{"beat": 8}` or `"#drop"`).
An empty range fails and says where the track's notes are. Bars are for range targets only: elsewhere in an operation a time is `{"beat": n}`, a marker
`"#name"` or seconds, a length `{"beats": n}`. Each line below is the complete `arguments` of one `edit_document` call:

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
- Sidechain (a duck: the bass dips on every kick) belongs in the script, so a re-run keeps it:
  `bass.duck(under=["kick"], depth=0.5, attack=0.005, release=0.15)`. The same as a one-off operation, on a song no script
  owns: `{"ops": [{"op": "duck.add", "target": ["bass"], "args": {"under": ["kick"], "depth": 0.5, "attack": 0.005, "release": 0.15}}]}`

The range is read as the song was before the call. Operations' own arguments: `inspect_operations` with `name`.

## The order of work

1. **Read** `inspect_guide` `writing-music` (the craft), then `script` (the names a script knows). Scoring to a picture: `scoring-to-picture`.
2. **Pick the sounds.** The names are in this guide's "Instrument and kit names". `inspect_engine` (`what: "names"`, the default)
   answers the same names compactly; with `name` (an effect, `master`, an instrument, a kit) one thing's settings with units or its
   role and starting level; `what: "instrument"` with ONE of `builtIn`, `model`, `synth`, `sfz`, `kit`, `kitSfz` gives its range.
3. **Write the whole piece as one script and run it with `look: true`** (the loop above). The argument is `source`;
   `name` is the song's one script name:

   ```json
   {"tool": "run_script", "arguments": {"name": "song", "look": true, "source": "tempo(96); length(bar(9))
t = track('keys', builtIn='piano')
t.note('D4', at=bar(1), dur=beats(4))"}}
   ```

4. **Look before you listen, when the check names something.** `look_arrangement` (every part against the bars and markers),
   `look_music` `harmony` (chords and range checks), `inspect_diagnose` (what is wrong with the song).
5. **Look at the result.** `look_sound` (`what`: `loudness` by default, `levels`, `low_end`, `clash`, `spectrum`, `stereo`) and
   `look_music` (`what`: `events`, `beats`, `pitch`). The loudness summary names the loudest moment and its time, the loudness
   of each section (`data.sections`) and an `ending` line (see 7); `start` / `end` (seconds, `{"beat": n}` or `"#marker"`) measure
   one stretch only. Which tool answers which question: `listening`, `checking-a-mix-by-ear`. Whether it is musical is for a person to hear; say so in your report.
6. **Fix in the script, run again under the same name.** Change one thing at a time; use `edit_document` only for a single value.
7. **End it cleanly** (`script`, "Ending a song") and render the last version. `look_sound` (`what: "loudness"`): the `ending` line gives
   the level of the last 0.5 s, whether the file still sounds above -50 dBFS at its end, whether the last 50 ms drop faster than the
   fade, and the **audible end** (`audible_end_s`: where the sound falls under -60 dBFS for good). Still above -50 dBFS with a fast
   last-50-ms drop is a cut: lengthen the song or add `master(fadeOut=...)`. Below -50 dBFS is a clean end.

## Rules that save a render

- **`run_script` `name`.** The same name replaces and merges what that script made before; a new name that
  makes the same tracks is refused (it would double every note) and names the script to run under. One name per song, for every run.
- **Without an MCP client of your own:** `python shared/mcp/call.py --name <you> -- <server command> :: <tool> '<json>'`. The first
  command starts a session that keeps the server running (later commands answer in about a second, and a job started in one
  command is still there in the next); `:: stop` ends it, 30 min without a call ends it too. `python shared/mcp/call.py` alone prints the help.
- **A call list stops at the first failed step.** Run through `devtools/mcp_session.py` (or `shared/mcp/call.py`), a list of
  calls stops at the first reply with `ok: false`: the later steps are not run, the output says which step failed and which
  were not run, and the exit code is 1. So a render never runs on a song the failed script did not change. If you call
  tools one by one yourself, read each `ok` before the next call.
- **Names.** Track, section and other item ids: 1 to 64 letters, digits, `_`, `.` or `-`, no spaces (`final_chorus`, not
  `final chorus`). Marker names are free text: spaces and most characters work (`"logo lands"`, then `"#logo lands"`).
- **Times and lengths: write music in bars and beats.** `bar(5)` is where bar 5 starts, `beat(8)` a time in beats
  (`{"beat": 8}` in an operation; `{"bar": 5}` only in a range target), `beats(2)` a length (`{"beats": 2}`): singular for a time, plural for a length.
  These follow the tempo: change it and every part moves with it. A bare number is seconds and does NOT move with the tempo:
  use seconds only for a moment fixed to a picture, and better still write that moment as a marker (`"#hit"`).
- **Volume.** A bare number is gain 0 to 4 (1 = 0 dB); in dB write `{"db": -6}`.
- **Effect settings** are plain numbers in the units `inspect_engine` lists: a compressor's `threshold` is dB as a plain number
  (`-24`, not `{"db": -24}`), `attack` and `release` are in seconds (`0.01`, not `10`).

## Loudness: louder or cleaner (`maxLimit`)

**A first render often lands 1 to 3 dB under the target (-16 LUFS for video): that is the default, not a failure. Do not leave it: the `render_mix` reply names the fix; `edit_loudness {"apply": "best"}` (or `keep_balance`) reaches the target in one call (with no loudness target on the master yet, the same call turns it on: render again, then call it once more). A single track far below the others (`look_sound` `levels` shows each track's LUFS) is a level problem of its own: raise that track.**

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

`{"apply": "best"}` takes the one the reply names best: keep_balance when it raises `maxLimit` by 1 dB or less and leaves at most ~3 dB of limiting, else
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
| `look_sound` `loudness` | `item`, `wav`, and `start` with `end` together (both or neither: only that stretch is measured, its times in the file's own time; the limiter curve and sections are of the whole file, so they are left out). No `track`. |
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
