# Your own sound library

Point Rostrum at a folder of sound effects you own: a Sonniss GDC bundle, BOOM, Soundly exports, your own
recordings. Rostrum indexes it **once**: every file is split into its single sounds and each is measured. Nothing is
copied out of the folder; the index keeps file paths and measurements only, in the shared cache. The folder list lives
in your settings (`~/.rostrum/settings/sound-library.json`), not in a project.

**On the screen:** open the **Library** (Ctrl+L) and click **My sounds**, or **Add a folder of my sounds…** at its
bottom. Search with the Library's search box, narrow by kind, length and brightness, hear a sound with ▶ (voices have none: they are made from a line you type, see [voice.md](voice.md)), and
double-click it (or **Place**) to put it at the playhead: on the selected recordings track, else on a "Sound effects"
track (one undo step).

## Add a folder

    inspect_library folder="D:\Sounds\Sonniss GDC 2024"

The first time takes a while (about 0.15 s per file on this laptop); after that, an unchanged folder comes back from
the index in a fraction of a second. A changed folder re-reads only new or changed files. A file that can't be read is
listed under `skipped` with the reason.

## What each sound says about itself

| Field | Meaning |
|---|---|
| `path`, `start`, `end` | the file, and where this one sound sits in it (seconds) |
| `kind`, `kinds` | impact, hit, click, ui, beep, ambience, foley, drone, glitch and others: from the library's UCS category, the file name, its metadata (BWF description, iXML, INFO), its folders, and its measured shape. `kinds` lists every kind with evidence, strongest first |
| `seconds` | its length |
| `onset_s`, `peak_s` | from its start: where it begins as the ear hears it, and its loudest moment |
| `attack_ms` | onset to peak: 3 ms is a click, 300 ms a slow swell |
| `brightness`, `centroid_hz` | 0 (250 Hz, dark) … 1 (8 kHz, bright), and the same as a frequency |
| `peak_db`, `lufs` | sample peak, and loudness while it sounds |
| `words` | the same in plain words: length short / medium / long, brightness dark / mid / bright, attack sharp / medium / soft |
| `about` | the words from its name and metadata |

## Search

    inspect_library kind="impact" length="short" brightness="dark"
    inspect_library kind="click" attack_ms=[0, 8] seconds=[0, 0.2]
    inspect_library kind="sounds" find="metal" lufs=[-30, null]

Ranges are `[low, high]`; either end may be `null`. Results come strongest-kind first, then by file and time, the
same every time.

## Place a sound

A sound is a clip of its file, starting at its `start`:

    t = track("hits")
    t.clip(r"D:\Sounds\…\Switch_04.wav", at=3.475 - 0.0175, in_=0.0024, length=0.094)

- **On a moment** (a card landing, a beat): put the sound's `onset_s` on it: `at = moment - onset_s`.
- **A recorded swell on a build**: put its `peak_s` on the moment it builds to: `at = moment - peak_s`. If that is
  before 0, start later in the file instead (`in_ = start - at`, `at = 0`).
- **Only this sound**: keep `length` ≤ `end - in_`, so the next sound in the same file doesn't play too.
- **Levels**: sounds in one library differ by 15 dB or more. `lufs` tells you how loud each is; raise `volume` for a
  quiet one rather than guessing.
- **Not one take everywhere**: use several of the nearest matches, and a little `pitch` (±0.3 st) and level
  variation on repeats.

## Sounds from the picture's motion, from your library

    edit_sounds_from_motion samples="…\samples.json" source="library"

Answers the events you choose with recordings of real things, not synthetic effects: a click or knock where
something lands hard, a press and its release (the same click higher and softer), a real hit under a big landing.
Each sound is chosen by kind and shape; a recording already used is pushed back. Rostrum makes no whooshes: score a
move with an instrument instead (`inspect_guide 'scoring-motion'`). Change any clip with `clip.set` (or move it in
the arrangement); running it again keeps your changes. Missing a kind (no clicks in your folders) is an error that
says which kind to add.

## Licences

Sounds from your folders are yours to use under their own licences (Sonniss bundles: royalty free in your
productions, not to be redistributed as sound effects). Rostrum never copies or ships them.
