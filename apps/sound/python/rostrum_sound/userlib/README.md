# userlib: bring your own sound library — UNFINISHED (stopped 2026-10-21)

**Status: unfinished, parked.** Sam took the sound-effects question himself on 2026-10-21 ("maybe go to basics or
generate our own sound; move forward away from that"), so P8 Package A was stopped. This code is committed as it
stood; nothing more is being built on sound-effect sources or libraries until Sam decides the direction.

What is here and works (checked on the 106 Sonniss evaluation files, not listened to):
- `folders.py`: the user's library folders, kept in `~/.rostrum/settings/sound-library.json` (not the project).
- `index.py`, `measure.py`, `kinds.py`, `meta.py`: a folder is read once into the shared content-keyed cache
  (`rostrum_core.cache`); long files are cut into single sounds (silences, else `sfx/pool.py`'s cut pool); each
  sound gets kind, length, attack, brightness, peak and loudness, from its name, UCS category, WAV metadata and
  shape. Only paths and measurements are stored; no audio is copied. 106 files → 205 sounds in ~15 s, a second
  run from the cache in ~0.02 s.
- `search.py`: search by kind, words, shape words (short / bright / sharp …) or number ranges.
- MCP: `inspect_library` (`folder`, `kind`, shape filters); `edit_sounds_from_motion source="library"`
  (`motion/score_library.py`). Guide: `apps/sound/guides/library.md`.
- Screen: `screen/screensound/library_panel.py` + `screen/qml/LibraryPanel.qml`. **Not wired into
  `screen/main.py`** (the Instruments page shows it only when a `soundLibrary` context object exists), so it is not
  on screen yet.

Not done: the panel's Play button and the library-scored slide deck were never listened to; kinds read from shape are
rough (UI sounds also get a weak "whoosh" tag). Test: `python/tests/test_userlib.py`.
