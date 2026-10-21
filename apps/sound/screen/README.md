# apps/sound/screen — the RostrumSound screen

Instruments, Timeline and Mix pages on one Sound document, built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          RostrumSound · document · [Instruments | Timeline | Mix] · play · bar.beat + seconds · history · Ctrl+K
centre           Instruments: a card per track with its main controls · Timeline: the piano roll of the selected
                 track (drums: a row per drum; clips: the waveform) · Mix: a strip per track + master, listen pictures
right            Inspector: the selected item (track, note, hit, clip, marker, effect, master)
bottom (full)    the arrangement: bars / beats ruler, named markers, a row per track (M / S), notes, hits, clips,
                 the playhead; tall on Timeline, slim on the other pages
```

## The rules it builds in

- **Individuality from data.** A card's controls are the track's "Instrument" fields whose `valid_when` holds, primary
  on the card, the rest behind its More (`screensound/cards.py`): a plucked string shows position and damping, a
  synth attack and brightness, because of `rostrum_sound/doc/playing.py`, never a list per instrument.
- **Every action is an operation, one history.** Card and inspector edits, mute / solo, fader and pan drags, adding an
  effect, adding / deleting / dragging notes, clips and markers. Each drag is one `doc.gesture` = one undo step.
  Times keep the form they were written in (beats stay beats, `"#drop+0.5"` stays on its marker); drags snap to a
  quarter beat (Shift: free).
- **Preview ≡ export.** Playback is the engine's own render of the compiled document (`screensound/playback.py`,
  the long-lived engine, newest request wins, re-rendered ~300 ms after a change), played with Qt Multimedia. A failed
  render is red in the status; the last good render plays only with "playing the last good render".
- The Mix page's meters, loudness numbers and listen pictures (`screensound/listen_pics.py`, made with
  `rostrum_sound.listen`) come from the same render (`backend.lastRender`).

## Run

```
.venv\Scripts\python.exe apps\sound\screen\main.py                                  # the sample song
... main.py --script song.py                                                        # what a script builds
... main.py --doc <project folder> <item>                                           # open / make; saves on change
... main.py --step "page mix" --step render --step "wait 20" --shot out.png         # scripted, quits by itself
.venv\Scripts\python.exe -m pytest -q apps\sound\screen\tests                       # under a second
```
Steps (`screensound/steps.py`): `page`, `select`, `time`, `set`, `drag-note <id> <dt> <dsemitones>`, `drag-clip`,
`drag-marker`, `add-note`, `delete`, `mute`, `solo`, `undo`, `redo`, `play`, `render`, `wait <s>`, `more`,
`commands`, `run`, `zoom`, `scroll`, `fit`, `lane`, `lane-point`, `lane-delete`, `picture`. Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Mix page: loudness, delivery, export, ducks, cleaned takes

- **Master loudness, live** (`loudness.py`, `MixLoudness.qml`, `LoudnessCurve.qml`): the short-term loudness (LUFS-S) and the
  true peak follow the playhead, read from the series of the render that plays (preview ≡ export). While playing, the
  integrated loudness is the one so far ("Integrated so far": BS.1770's gated mean of the render's 400 ms blocks up to
  the playhead, `loudness.integrated`); stopped, it is the whole mix's, from the engine. The curve shows the short-term
  series with the target as a dashed line. The first 3 s show "—" (the first short-term window ends at 3 s).
- **Delivery target** (`delivery.py`: a small table of published specs with a source per row; streaming −14 / −1,
  Apple Music −16 / −1, EBU R128 −23 / −1, ATSC A/85 −24 / −2, podcast −16 / −1). It follows the fields' valid_when
  (`delivery.applying`): the true peak ceiling always applies, the loudness target only with Normalize on. "Deliver to"
  sets those that apply in one `master.set`, and a Pass / Miss line compares the last render to them (within ±1 LU,
  true peak under the ceiling).
- **A control once per screen** (`onpage.py`): the inspector leaves out what the page's own controls show (the master
  strip's fader, Normalize and target; a strip's fader, pan, output; a send's level; the track headers' mute / solo).
- **Render mix and stems** (`export.py`, `MixExport.qml`): the same versioned render as the MCP `render_mix`
  (`handoff.render`, stems "all"), in the background on its own engine process; status, the `vNNN` folder and "Show folder".
  Needs a project folder (`--doc`); without one it says so in red.
- **Ducks** (`ducks.py`, `MixDucks.qml`, `DuckPanel.qml`): "+ Duck" on a track strip adds a duck under another track
  (`duck.add`); its chip opens a panel: which tracks it is under (`duck.set` with the list) and the settings from `duck.set`'s
  own params (depth, attack, release, hold, voice, lookahead behind More). A drag is one undo step.
- **Make cleaned take** (`cleaning.py`, `CleanTakeBar.qml`, under the inspector): only while the selected clip has a cleanup
  step and no cleaned take yet; runs `clean_clips.make_clips` (what `render_cleanup` runs) in the background, then re-renders.
- A plug-in's own "Bypass" setting is not listed (our bypass switch is beside it).
- Steps: `deliver <key>`, `export`, `duck-add <track> <under>`, `duck-open <id>`, `duck-set <param> <value>`.

## Recording

Arm a track (round button on its header), press the red Record button or R: the microphone starts
(`rostrum_sound.record`, the engine's `record`), the count-in clicks if it is on, the mix plays from the playhead,
levels show live, and the take becomes one clip at the start time (one undo step) in
`<project>/media/<track>-take-<n>.wav`. The take is placed where it was played: what the microphone heard before
playback was heard (its start-up, the count-in) and the microphone's own delay (when `rostrum-sound play --calibrate`
measured it for this microphone) are cut off with the clip's in-point (`record.place_take`, `take_clock.py`).

- **Take panel** ("Take" beside Record, `RecordSetup.qml` / `record_setup.py`; screen state, not an edit). Its rows show
  only when usable: **Count-in** (Bars only while on: that many bars of clicks before playback), **Punch in** (From /
  To only while on; turning it on starts a two-bar range at the playhead; the range is shaded on the timeline; only it
  is kept: the clip is trimmed to it, and the take stops by itself past the To time; a playhead already past From
  starts a bar before it), **Input level** (the microphone runs for the meter alone, before a take).
- **Keyboard takes** (`keys_record.py`): on an armed notes or drum track with a MIDI keyboard connected, "Record keys"
  records what is played (the engine's `live --midi`); the panel picks the **Keyboard** when one or more are connected
  ("No MIDI keyboard found" otherwise; the list is read again on every arm) and **Quantize** (off by default; To: beat,
  1/8 or 1/16 note). Stop puts the take on the track as one `note.add_many` (drums: `hit.add_many`), one undo step, at
  the beats played relative to playback, and the piano roll shows that track. Count-in works here too.
- Steps: `arm <track>`, `record`, `record-fake <wav>` (a WAV stands in for the microphone), `take-panel`,
  `take-set <row> <value>`, `midi-fake <file.mid | note list>` (`fake_midi.py` stands in for two keyboards), `keys`.
- Use headphones: a take made against speakers hears them. What is left of the timing is the screen player's own
  output delay (tens of ms). Hearing yourself through the app (input monitoring) is not there: the engine's `record`
  only captures.

## Zoom, automation lanes, picture (Timeline)

- **Zoom / scroll.** One view (`screensound/view.py`: `backend.viewStart` + `viewSpan`) draws the ruler, markers, rows,
  playhead and the piano roll's time axis. Ctrl + wheel or a pinch zooms around the pointer; Shift + wheel or a sideways
  swipe scrolls (a plain wheel scrolls in time when the rows have nothing to scroll up and down); Ctrl + / Ctrl - /
  Ctrl 0 (show all); a slim scrollbar while zoomed in. Playing keeps the playhead on screen. Screen state, not an edit.
- **Automation lanes.** A track's "Auto" chip opens a lane under its row: volume, pan, expression (notes tracks) and
  each send's level (`screensound/lanes.py`). Click adds a point, drag moves it (stays between its neighbours; quarter
  beat grid, Shift = free), Delete removes it; each is one `automation.set` with the whole point list, one gesture = one
  undo step. Times keep the form they were written in. Effects' envelope settings and each EQ band's frequency, gain
  (peak and shelves) and width are lanes too (`doc/lanes.py`: "band2.gain"). Under the tracks, compact rows for each
  bus and the master (`MixRowHeader.qml`) carry their own lanes (volume, bus pan, their effects).
- **Duck dips** (`DuckDips.qml`): a ducked track's row shades where its ducks pull it down and how far ("−14 dB"),
  from the engine's own report in the render that plays (`lastRender.ducks`: every stretch below −3 dB).
- **Picture.** "Picture" in the piano roll's header opens a corner with the video frame at the playhead (Qt Multimedia;
  plays along while playing, set back to the playhead when it drifts a frame). The file is the document's `picture`
  field (`doc.set`, so agents set it too): a chosen file, or `item:<id>` = the newest picture render of a 2D item of
  the project ("From the project…", `picture.py`; the one place that turns it into a file, re-checked every 2 s so the
  corner follows a newer render; without a project folder it says so). "Starts at" (`pictureAt`, any time form) puts the
  picture's first frame on the song's start or on a shared marker, so it moves with the marker. The video's own sound
  is not played. Offscreen screenshots show it black (no video renderer there): shoot with a real window.

## Song: tempo, key, sections (editable)

Click the tempo / key in the top bar: the Song popup (`SongEditor.qml`, `song_edit.py`). **Tempo**: the song's own,
"Tempo change here" (on the playhead's beat, `tempo.add`), the selected change's tempo and Delete. **Key**: tonic + mode
choosers (`key.set` on the key playing now, or a first `key.add`), "Key change here" (only once the song has a key and
the playhead is not on one), Delete on a selected key change. **Sections**: "Section here" (4 bars from the playhead),
the selected one's name, Delete. A delete shows only with that thing selected. On the ruler, flags for tempo and key
changes (`SongBand.qml`: click selects, drag moves, one undo step, on its beat; a change in seconds stays in seconds)
and the section bar's edges: drag an edge to resize (`section.set`, the contents stay), drag the middle to move it
with everything inside. Times keep their written form. Steps: `song <action> [value]`, `song-open`, `drag-tempo`,
`drag-key`, `drag-edge`, `picture-link`, `picture-start`, `picture-pick`.

## Not yet

No sample-exact overdub (takes are placed by measured start times; the screen player's own output delay, tens of ms,
remains; use headphones), no input monitoring (hearing yourself), keyboard takes not tried with a real keyboard. Bus / master rows have no mute or fader on the Timeline (those are
on the Mix page).
Choices show their stored names ("builtIn", "warmPad") until the kit can show labels; a bus output is typed in the inspector
(the Mix page has a picker). `screensound/bridge.py` is ~390 lines: it should be split once the kit allows slots outside the bridge class.
Voice: see `apps/sound/VOICE.md`.
