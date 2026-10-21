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

## Recording

Arm a track (round button on its header), press the red Record button or R: the mix plays from the playhead, the
microphone records (`rostrum_sound.record`, the engine's `record`), levels show live, and the take becomes one clip
at the start time (one undo step) in `<project>/media/<track>-take-<n>.wav`. Steps: `arm <track>`, `record`,
`record-fake <wav>` (test stand-in for the microphone). Use headphones: a take made against speakers hears them.

## Zoom, automation lanes, picture (Timeline)

- **Zoom / scroll.** One view (`screensound/view.py`: `backend.viewStart` + `viewSpan`) draws the ruler, markers, rows,
  playhead and the piano roll's time axis. Ctrl + wheel or a pinch zooms around the pointer; Shift + wheel or a sideways
  swipe scrolls (a plain wheel scrolls in time when the rows have nothing to scroll up and down); Ctrl + / Ctrl - /
  Ctrl 0 (show all); a slim scrollbar while zoomed in. Playing keeps the playhead on screen. Screen state, not an edit.
- **Automation lanes.** A track's "Auto" chip opens a lane under its row: volume, pan, expression (notes tracks) and
  each send's level (`screensound/lanes.py`). Click adds a point, drag moves it (stays between its neighbours; quarter
  beat grid, Shift = free), Delete removes it; each is one `automation.set` with the whole point list, one gesture = one
  undo step. Times keep the form they were written in.
- **Picture.** "Picture" in the piano roll's header opens a corner with the video frame at the playhead (Qt Multimedia;
  plays along while playing, set back to the playhead when it drifts a frame). The file is the document's `picture`
  field (`doc.set`, so agents set it too; the project service lists no items yet, so it is a chosen file). The video's
  own sound is not played. Offscreen screenshots show it black (no video renderer there): shoot with a real window.

## Not yet

No Voice card, no MIDI keyboard input, no picture from the project's items, no automation on buses / master lanes.
Choices show their stored names ("builtIn", "warmPad") until the kit can show labels.
