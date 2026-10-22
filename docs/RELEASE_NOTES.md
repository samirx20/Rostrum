# Rostrum — what's in each version

## 0.1.3 (22 October 2026) — the first version to try 2D and Sound

One installer, `RostrumSetup-0.1.3.exe`. When it asks, tick **Rostrum2D**, **RostrumSound** or both. It installs for
you only (no administrator question) into `%LOCALAPPDATA%\Programs\Rostrum`, and the uninstaller takes out everything
it put in but leaves your own files alone. Windows only for now; Mac comes later.

### What the two apps do

**Rostrum2D** makes moving pictures: titles and type, shapes, product and screen animation, drawing and painting
(also frame by frame), and simple 2D characters you can pose and make talk.
- Draw shapes, text and paintings straight on the frame; move, turn and resize them with handles.
- Animate by setting keys on the timeline; change how each move speeds up and slows down in the curve editor.
- Text can follow a path; a camera can move, zoom and give depth; grain and other effects per layer.
- Characters: bones from the parts' names, posing by dragging, a list of poses, lip sync to a voice line, blinks.
- Sound: the project's music plays with the picture, you can put a sound at any moment, and videos keep their sound.
- Export MP4 (with the project's sound), WebM, GIF, PNG pictures and more.

**RostrumSound** makes the sound: music, sound effects, voice, recording and mixing.
- Build a song from sections and tracks; write notes in the piano roll; the tempo, beats and key sit in one place.
- A Library of instruments and sounds you can hear by hovering, try, keep or undo.
- Record from a microphone, clean up a recording (the clean-up helper downloads the first time you use it), type a
  line and have it spoken.
- Mix with levels, effects and groups; the loudness of the whole song is shown in one place at the top.
- Export WAV, FLAC or MP3, the whole song or one part, and separate tracks for an editor.

Both apps save every change by themselves, keep a full History you can step back through, and can be driven by an AI
agent: **Help → Connect an AI agent** sets it up for coding agents such as Claude Code or Codex. **Help → Guides**
has how-to pages for people.

### New today

- **Faster with big work.** A drawing with 10,000 strokes takes a new stroke in a few hundredths of a second instead
  of 3–4 seconds, opens in about a second instead of six, and its file is a third of the size. Long songs use far less
  memory when they are exported.
- **Cleaner screens in both apps.** Each value is shown once, in one place; fewer labels and repeated names; one
  Export button; settings panels that only show what you can use right now.
- **2D:** text on a path, a curve editor with handles that are easy to grab, posing and lip sync on the screen, video
  sound and grain mixed by Sound's engine, a Library and brand kit (first version), dropping files from the desktop.
- **Sound:** tempo reads "100 bpm", Library rows play when you hover, a clean-up result shows inside its own panel,
  "Make this the main mix", cues taken from a 2D project, hold H to hear the version before your last change.
- **New guides in Help:** text on a path, the curve editor, characters / sound / camera (2D), arranging and
  delivering (Sound).
- **Two copies of one project at once** (for example you and an agent) no longer trip over each other when they save
  sound or pictures.

### Your files

- Files made with earlier test versions open as before.
- Saving keeps a new, faster file layout. **Files only move forward:** once 0.1.3 has saved a project, an earlier test
  version may not open it. Keep a copy first if you still need the old version.
- If the computer stops in the middle of a change, the app opens the file without that half-written step and tells
  you so.

### Known limits

- Rarely, Rostrum2D does not open its window at the first try (seen twice in about 40 starts while testing). Close it
  in Task Manager and start it again; nothing is lost.
- Icons are placeholders.
- Tried on this laptop as a brand-new user, not yet on a second Windows account or a Mac.
- 3D and the Editor are not in this installer yet.
