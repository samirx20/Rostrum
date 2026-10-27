# The sound library

## Sample packs: the recorded instruments, drum kits and sound effects

The plain instrument names (piano, strings, bass, flute …), the drum kits (`drums`, `studio`, `jazz`) and the sound-effect library
are **sample packs**: real recordings installed on this machine, not part of the app (the piano alone is 1.2 GB). Each pack
is listed with its author, licence and size; every file is checked by its fingerprint before it is kept (a wrong one is
deleted and the install fails, saying so), and what was installed is recorded in `<assets>/assets.json`.

    inspect_library kind="packs"                       # every pack: installed or missing, size, licence, credit
    run_model_install model="salamander-piano"         # one pack; also all-instruments and all
    python -m rostrum_sound.packs list | install <pack> | verify <pack>      # the same in a terminal

Which names play these recordings and which are synthesized (`warmPad`, `subBass`, `pluck`, `choirPad`, `classic.*`, `model=`, `synth=`):
`inspect_engine` marks each "recorded" or "synthesized". No pack holds a pad: there is no recorded pad today. The harmonica (`harmonica`: a recorded chromatic Hohner Super 64, B2-D7, the plain breath; the pack also holds an accented and a vibrato breath, reachable today only through your own SFZ; the breath-out sound plays when a key lifts) is in the pack `vcsl-harmonica` (29 MB, CC0).

A name whose pack is missing fails loudly and names the pack to install; it never falls back to another sound. Packs
licensed CC-BY (Salamander piano, Wurlitzer, the rock kit) need a credit: a render or export that used them returns the
credit lines and writes them into the export's manifest. Everything else is CC0 or MIT: no credit needed.

# Your own sound library

Point Rostrum at a folder of sound effects you own: a bought sound-effects bundle, Soundly exports, your own
recordings. Rostrum indexes it **once**: every file is split into its single sounds and each is measured. Nothing is
copied out of the folder; the index keeps file paths and measurements only, in the shared cache. The folder list lives
in your settings (`~/.rostrum/settings/sound-library.json`), not in a project.

**On the screen:** open the **Library** (Ctrl+L) and click **My sounds**; with the chip on, **Add a folder of my
sounds…** sits at its bottom. Search with the Library's search box, narrow by kind, length and brightness, click a row
to hear it (the row lights at once; a click again stops it, another row replaces it; a click only plays it; it changes nothing in the song; voice rows have no preview: they are made from a line you type, see [voice.md](voice.md)), and press the
row's **Add** to put it at the playhead: on the selected recordings track, else on a "Sound effects" track (one undo
step). The preview stops and the Library stays open (in a narrow window it closes).

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
