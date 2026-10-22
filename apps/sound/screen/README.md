# apps/sound/screen — the RostrumSound screen

One workspace on one Sound document (apps/sound/DESIGN.md §2), built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          RostrumSound · File · song · ⏮ ▶ · Record (only while a track is armed) · bar.beat · time ·
                 ♩ tempo · beats · key (click: the tempo / key popover) · Loudness against the target (once there is
                 sound; click: the Mixer) · history · + Add · Deliver (once there is sound) · Ctrl+K · Help
left             the Sounds panel (L, + Track, + Add): instruments, drum kits, microphone, voices, my sounds; pushes the
                 arrangement on a wide window, floats over it below 1500 px and closes after use
centre           the arrangement, always (Arrangement.qml + Timeline.qml): zoom strip, ruler, sections, markers, a row
                 per track, + Track, groups, Master; under it the dock (Dock.qml): Editor (E: the selection's track up
                 close, EditorDock.qml) or Mixer (X: strips, the Master pinned right, Mixer.qml), folds away
right            the settings panel: the selection's settings (the kit's Inspector), or the song while nothing is
                 selected (SongSettings.qml, `songPanel`)
dialog           Deliver (Ctrl+Shift+E): target, file, quality, stems, the live check, Deliver, then Show file
```
Screen state (never saved in the song): `workspace` (screensound/workspace.py: the dock, its height per tool, the
Sounds panel).

## The rules it builds in

- **Individuality from data.** The settings panel shows a track's "Instrument" fields whose `valid_when` holds: a
  plucked string shows position and damping, a synth attack and brightness, because of
  `rostrum_sound/doc/playing.py`, never a list per instrument. Record, Deliver, the loudness readout and the dock
  are absent until they apply.
- **Every action is an operation, one history.** Inspector edits, mute / solo, fader and pan drags, adding an
  effect, adding / deleting / dragging notes, clips and markers. Each drag is one `doc.gesture` = one undo step.
  Times keep the form they were written in (beats stay beats, `"#drop+0.5"` stays on its marker); drags snap to a
  quarter beat (Shift: free).
- **Preview ≡ export.** Playback is the engine's own render of the compiled document (`screensound/playback.py`,
  the long-lived engine, newest request wins, re-rendered ~300 ms after a change), played by the engine's own live
  transport (`screensound/live_transport.py`: one `rostrum-sound play --shared` process per screen, started on the first
  play or arm, each new render sent with `{"load"}`; the playhead is the speaker's position it reports). A failed
  render is red in the status; the last good render plays only with "playing the last good render". When the player
  cannot open (no sound output) it is said in red and the playhead runs on a clock.
- The Mixer's meters and loudness numbers come from the same render (`backend.lastRender`). The screen draws no listen
  pictures after a render (a whole-song read nothing on screen showed); agents ask `rostrum_sound.listen` for them.

## Run

```
.venv\Scripts\python.exe apps\sound\screen\main.py                                  # the last song, else a new one
... main.py <song folder or .trk>  |  --new  |  --sample                               # open / new untitled / sample
... main.py --script song.py                                                        # what a script builds
... main.py --doc <project folder> <item>                                           # open / make; saves on change
... main.py --step "dock mixer" --step render --step "wait 20" --shot out.png         # scripted, quits by itself
.venv\Scripts\python.exe -m pytest -q apps\sound\screen\tests                       # under a second
```
Steps (`screensound/steps.py`): `dock editor|mixer|none` (old scripts' `page timeline|mix|instruments` still work), `sounds`, `deliver-open`, `select`, `time`, `set`, `drag-note <id> <dt> <dsemitones>`, `drag-clip`,
`drag-marker`, `add-note`, `delete`, `mute`, `solo`, `undo`, `redo`, `play`, `render`, `wait <s>`, `more`,
`commands`, `run`, `zoom`, `scroll`, `fit`, `lane`, `lane-point`, `lane-delete`, `picture`. Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Songs as files, Settings (P21)

File menu (`FileMenu.qml`, `screensound/session.py` = `songs`, `projects.py`): New song, Open…, recent songs, Save… /
Save a copy as…, Settings…. A new song is untitled (saved per change in the untitled area) until Save names it; named
songs are saved per change. Crash recovery offers back untitled songs whose process is gone. Settings
(`SettingsPanel.qml`, `screensound/settings_page.py` = `settingsPage`) is the kit's Inspector on
`rostrum_sound.settings_fields.FIELDS`. Switching songs rebuilds the bridge and its parts and reloads the window
(`main.py` `Screen.show`). Steps: `file-new`, `file-open <path>`, `file-save-as <folder>`, `file-menu`, `settings`,
`add-track <sound key>` (adder.py: `builtIn:grandPiano`, `kit`, `mic`, `voice:ryan` …; the old piano|strings|pad|bass|drums|voice|audio still work), `press <Ctrl+Shift+S>` (a key chord into the window).
The File menu shows the shortcuts (`HintMenu.qml`, the kit's Menu with key hints): Ctrl N / O / S, Ctrl Shift S (Save a copy), Ctrl ,.

## Mixer and Deliver: loudness, delivery, export, ducks, cleaned takes

- **Master loudness, live** (`loudness.py`, `MixLoudness.qml`, `LoudnessCurve.qml`): the short-term loudness (LUFS-S) and the
  true peak follow the playhead, read from the series of the render that plays (preview ≡ export). While playing, the
  integrated loudness is the one so far ("Integrated so far": BS.1770's gated mean of the render's 400 ms blocks up to
  the playhead, `loudness.integrated`); stopped, it is the whole mix's, from the engine. The curve shows the short-term
  series with the target as a dashed line. The first 3 s show "—" (the first short-term window ends at 3 s).
- **Delivery target** (`delivery.py`: a small table of published specs with a source per row; streaming −14 / −1,
  Apple Music −16 / −1, EBU R128 −23 / −1, ATSC A/85 −24 / −2, podcast −16 / −1). It follows the fields' valid_when
  (`delivery.applying`): the true peak ceiling always applies, the loudness target only with Normalize on. choosing a target
  sets those that apply in one `master.set`, and a Pass / Miss line compares the last render to them (within ±1 LU,
  true peak under the ceiling).
- **A control once per screen** (`onpage.py`): the inspector leaves out what the workspace's own controls show (the master
  strip's fader; a strip's fader, pan, output; a send's level; the track headers' mute / solo).
- **Deliver** (`export.py`, `DeliverDialog.qml`; top bar Deliver, Ctrl+Shift+E, once the song makes a sound): target,
  file, quality, stems (off by default), trim; the live Pass / Miss line; Deliver runs the same versioned render as the
  MCP `render_mix` (`handoff.render`) in the background on its own engine process; then "Done", the `vNNN` folder and
  "Show file". Needs a project folder (`--doc`); without one it says so in red. The top bar's loudness readout
  (`LoudnessReadout.qml`) is the whole song's loudness against the target (green dot within ±1, amber outside).
- **Ducks** (`ducks.py`, `MixDucks.qml`, `DuckPanel.qml`): "+ Duck" on a track strip adds a duck under another track
  (`duck.add`); its chip opens a panel: which tracks it is under (`duck.set` with the list) and the settings from `duck.set`'s
  own params (depth, attack, release, hold, voice, lookahead behind More). A drag is one undo step.
- **Make cleaned take** (`cleaning.py`, `CleanTakeBar.qml`, under the inspector): only while the selected clip has a cleanup
  step and no cleaned take yet; runs `clean_clips.make_clips` (what `render_cleanup` runs) in the background, then re-renders.
- A plug-in's own "Bypass" setting is not listed (our bypass switch is beside it).
- Steps: `deliver <key>`, `deliver-open`, `export`, `duck-add <track> <under>`, `duck-open <id>`, `duck-set <param> <value>`.

## Recording

Everything goes through the engine's live transport, the same process that plays the song, so a take is placed
against what was heard, to the sample. Arm a track (Rec on its header): the microphone opens in the player
(`--mic`), its level shows in the record cluster of the top bar. Press the red Record button or R: the engine counts
in if asked (its own clicks), plays from the playhead and records; Stop and the take becomes one clip (one undo step)
in `<project>/media/<track>-take-<n>.wav` at the engine's `start` (its clock, minus the microphone's delay when
`rostrum-sound play --calibrate` measured it; `rostrum_sound.record.land_take`).

- **Take panel** ("Take" in the record cluster, `RecordSetup.qml` / `record_setup.py`; screen state, not an edit). Rows
  show only when usable: **Count-in** (Bars only while on), **Punch in** (the range is dragged on the ruler: drag
  across it, or drag either red edge; a quarter beat grid, Shift free; turning punch on starts a two-bar range at the
  playhead; the engine keeps only the range and the take stops by itself past it; a playhead already past the
  punch-in starts a bar before it), **Hear input** (only while the microphone is open, off by default: the microphone
  mixed into the output, with its **Volume**), a line saying whether the microphone's delay was measured.
- **Keyboard takes** (`keys_record.py`): on an armed notes or drum track with a MIDI keyboard connected, the player also
  opens the keyboard (`--midi`, with a monitor instrument), and "Record keys" records what is played; the engine
  reports each note at its mix time. The panel picks the **Keyboard** ("No MIDI keyboard found" otherwise; the list is
  read again on every arm) and **Quantize** (off by default; beat, 1/8 or 1/16). Stop puts the take on the track as one
  `note.add_many` (drums: `hit.add_many`), one undo step, and the piano roll shows that track.
- Steps: `arm <track>`, `record`, `take-panel`, `take-set <row> <value>`, `punch <from> <to>`, `fake-player [options]`,
  `record-fake <wav>`, `midi-fake <file.mid | note list>`, `keys` (`fake_play.py` stands in for the engine's player,
  microphone and keyboard).
- Use headphones (or Hear input off): a take made against speakers hears them.

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

Takes not yet checked against a real microphone for sample-exactness (needs a loopback test), keyboard takes not tried
with a real keyboard. The library's audition still plays through Qt Multimedia (its files are any format). Bus / master rows have no mute or fader on the Timeline (those are
on the Mix page).
Choices show their stored names ("builtIn", "warmPad") until the kit can show labels. A track's / bus' Output is a pick list
(Master and the buses; `output_pick.py`). Inspector rows have no hover words yet (kit request: show a field's `help` as a HoverTip). `screensound/bridge.py` is ~390 lines: it should be split once the kit allows slots outside the bridge class.
Voice: see `apps/sound/VOICE.md`.
