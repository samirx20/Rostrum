# Start here: RostrumSound for agents

You make music, sound effects and mixes. The song is a document of tracks (an instrument or kit, its notes or hits, its
effects), sections, markers and a master. You build it from ONE Python script and check it by ear-like tools.

## The loop

1. **Write the whole piece as one script**, starting with the brief you were given, word for word: `brief("...")`.
   Then the song's map (tempo, key, length, sections, markers), every track's notes, the effects, the mix and the master
   target.
2. **Run it with `run_script` and `look: true`**, under one `name` for the song. It merges the script, renders the mix and
   listens.
3. **Read the faults.** The reply opens `NOT DONE:` (each fault with its id, its time and a fix) or `DONE:`.
4. **Fix the script, not the song**, and run it again **under the same name**. A removed track, note or marker disappears;
   nothing is copied. A new name that makes the same tracks is refused (it would double every note).
5. Repeat until the reply says `DONE:`, then deliver with `render_mix` (`name`, `folder`, `format`). A delivery is refused
   while a fault is open, unless `keep: {"fault_id": "why"}` explains it by quoting the brief's words that ask for it
   (`"dull_top": "the brief asks for \"dark, muffled\""`); any other why is refused. A fault on the moment the brief
   asked for is kept only after a render that tried the fix, and only when it measures near passing (the fault says what passes); else
   fix it, or move the moment itself in the script when the brief allows.

## Bars first

- **Write every musical time in bars and beats.** `bar(n)` is where bar n starts (bars count from 1); `beat(8)` is a time in
  beats; `beats(2)` is a length. `length(bar(9))` is an 8-bar song: for N bars write `length(bar(N + 1))`.
- **A tempo change moves everything written in bars and beats.** Change `tempo(96)` to `tempo(104)` and run again: every part
  follows, no note is re-made. A bare number is seconds and does NOT follow the tempo.
- **Sync points are markers.** Name each moment the music must meet (`marker("hit", at=bar(9))`) and write parts against it:
  `at="#hit"`, `"#hit+0.5"` (half a second after). Checks find them by name (`expect: ["#hit"]`).
- **A moment fixed to a picture** (a cut at 12.4 s): land a bar on it without bending the music,
  `downbeat(bar(5), at=12.4)` (or `at="#cut"`), or glide the tempo into it, `land(bar(9), at="#cut", ramp_from=bar(5))`.
  Then keep writing in bars. `marker("cut", at=12.4, shared=True)` publishes it so 2D follows it.
- **A build into a moment:** `build_to("#hit", over=beats(8), parts=[cymbal_roll(drums), crescendo(strings, ["D3", "A3"])])`
  writes plain notes you can edit.
- **Keep a part moving:** `strings.shape("vol", 0.4, 1.0, over=(bar(1), "#climax"), curve="late")` plays it softer to
  louder (loud sample layers come in on the way up, held chords swell); `"bright"` opens a lowpass, `"art"` switches
  articulation. A build that goes flat before its climax is a fault; a part that never changes in a build is a warning
  (`inspect_guide 'writing-music'` › Keep it moving).
- **The ending:** `ending("ring", at="#end")` lands every part together on the home chord and sets the length so it
  rings out; `"button"` is a short hit, `"fade"` a written fade. The reply says where it lands, where the ring dies and
  the file's length: with an asked length, put `at` so the ring dies by it. A loop takes no ending (`inspect_guide 'script'` › Ending a song).
- **A moment that must read** (a hit out of silence, a band that really stops, a drop that is a gap): `moment("hit", at="#hit")`
  rests before it, stops the band and strikes its layers; its checks join the faults (`inspect_guide 'script'` › Moments that read).

## A tiny example (a technique, not a piece)

```python
tempo(96); key("D minor"); length(bar(9))
marker("lift", at=bar(5))
keys = track("keys", builtIn="piano")
for b in range(1, 9):
    keys.chord(["D3", "A3", "F4"], at=bar(b), dur=beats(4))
drums = track("drums", kit="studio")
drums.hit("kick", at="#lift")
master(loudness=-16, truePeak=-1)
```

Run it as `{"name": "song", "look": true, "source": "<the script>"}`. Every script name (track, note, chord, hit, voice,
comp, bass_line, drum_grid, duck, send …) is in `inspect_guide 'script'`.

## The five tools to start with

- `run_script`: build or rebuild the song from the script; `look: true` renders and listens in the same call.
- `look_sound`: the mix as numbers: loudness and faults (default), each track's level, low end, clashes, spectrum, stereo.
- `look_music`: the music as facts: where sounds start against `expect`, beats and swing, pitch, key and chords.
- `inspect_guide`: these guides by `topic` (`{"topic": "script"}`); with no topic, the list.
- `render_mix`: the delivered file and stems; it lands on the master's loudness target and says how much limiting that took.

Speech under music: `track("vo", role="dialogue")`, then `music.duck()` dips under every dialogue track for whole lines.
Every other tool: `inspect_tools`. `look_arrangement` shows the written song as a picture without rendering;
`edit_document` is for one-off touch-ups on a song no script owns.

## Never

Never write music in seconds, never set loudness or compressors by guess (use `edit_loudness`), never run the same
parts under a second script name, and never read `.trk` files directly: use the tools.

## Where next

- `writing-music`: the craft (form, voicing, groove, dynamics); read it before composing. Its helpers: `writing-music-tools`.
- `script`: every script name, effect setting and unit; ending a song; landing on a time.
- `agent-reference`: replies in full, instrument and kit names, whole `edit_document` calls, units, loudness, which
  arguments go with which `what`.
- `tools-in-detail`: every tool's full description and every argument's full words.
- `writing-parts`: notes and parts, touch-up operations (`note.chord`, `note.strum` …).
- `listening` and `checking-a-mix-by-ear`: which look answers which question.
- `mixing-to-delivery` and `exporting`: mix, loudness, formats, stems.
- `scoring-to-picture` and `scoring-motion`: music against a picture, sounds from 2D motion.
- `voice`, `library`, `cleanup`: spoken lines, sample packs and sound folders, cleaning a recording.
- `first-song`: the app's window, click by click (what a person sees).
