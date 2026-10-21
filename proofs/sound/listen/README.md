# listen — the agent's ears

An agent can't hear. `listen` turns a WAV into **facts** (JSON) and **pictures** (PNG) it can read. It never judges: no scores, no "good/bad", no style rules. It says what is there; the agent decides.

Run from `proofs/sound/`:

```
python -m listen <command> <wav> [options]
```

Every command prints one line of JSON. Errors go to stderr with a non-zero exit code (no half results). The same code is importable: `from listen import loudness; loudness.analyse("a.wav")`.

| Command | The question it answers | Options |
|---|---|---|
| `loudness a.wav` | How loud is it, does it clip, how does the level move? | – |
| `spectrogram a.wav --png out.png` | What frequencies are playing when? (a 1600×800 picture) | `--marks 12.0,24.5` draws lines at those times; `--mel` |
| `onsets a.wav` | Where are the hits, what's the tempo, where is the energy? | `--expect 1.2,3.4` |
| `bands a.wav` | Is it muddy, harsh, thin? Does the build really build? | `--section 5` (seconds) |
| `levels s1.wav s2.wav … --mix mix.wav` | Is each instrument heard? Who owns which band? | `--section`, `--buried-db 15` |
| `stereo a.wav` | How wide is it? Does it vanish in mono? | `--section` |
| `compare a.wav b.wav --png out.png` | How does my cue differ from that one? | – |
| `report a.wav --dir outdir` | Everything about this file, in one call | `--section` |

## What each gives back (shortened examples)

**loudness** — `{"integrated_lufs":-23.05,"true_peak_dbtp":-19.99,"lra_lu":0.0,"sample_peak_dbfs":-20.0,"rms_dbfs":-23.01,"clipping_samples":0,"short_term_lufs_per_s":[-23.0,-23.0,…]}`
True peak is measured at 4× oversampling. The short-term list is one value per second (a 3-second window ending there); `null` means silence.

**spectrogram** — writes the PNG, returns its path. Time in seconds along the bottom, frequency in Hz (log scale, 30 Hz to the top) up the side, colour = dB below the loudest point. `--marks` draws cyan lines labelled with the time — put your intended hits there and check that energy starts on the line.

**onsets** — `{"onsets_s":[1.2,3.4,7.5],"tempo_bpm":60.1,"beats_s":[…],"energy_db_per_0.5s":[…],"expected":[{"expected_s":1.2,"nearest_onset_s":1.2,"offset_ms":0.1}]}`
`offset_ms` > 0 means the sound lands late, < 0 early. Use it to check that effects land on on-screen events. Tempo is an estimate and can be half or double the real value; trust the onsets more.

**bands** — per section: dB and share of energy in `sub` (<60 Hz), `low` (60–250), `low_mid` (250–2k), `high_mid` (2–6k), `air` (>6k). A band that holds 70% of the energy is a mud/boom fact; a build is a rise in the bands across sections.

**levels** — per stem: LUFS, peak, its share of the mix's energy per band, its level per section. Per section: loudest stem, ranking, and which stem dominates each band. `flags` lists facts the agent may want to act on:
- `buried`: the stem is always more than 15 dB under the loudest other stem wherever it plays.
- `crowded_band`: two or more stems each hold ≥30% of a band's energy in the same section (they overlap there).
A share over 100% only means the mix is quieter than that stem on its own. Without `--mix`, the stems are summed.

**stereo** — per section: left/right `correlation` (+1 identical, 0 unrelated, below 0 cancels in mono), `width_pct`, `balance_lr_db`, `mono_loss_db`. `mono_compat_warnings` names sections where correlation is negative or the mono sum drops more than 6 dB.

**compare** — one PNG: spectrogram of A, spectrogram of B, then both short-term loudness curves on one axis. JSON adds each file's loudness numbers and a band-balance table (dB per band for A and B, and B minus A).

**report** — writes `outdir/report.json` (loudness + onsets + bands + stereo), `spectrogram.png`, and `curves.png` (loudness over time on top, the five bands over time below). Returns the same JSON plus the paths.

## Tests

`python -m pytest listen -q` (from `proofs/sound/`) guards two facts agents rely on: a −20 dBFS 1 kHz sine reads −23 LUFS, and clicks at known times come back with offsets under 10 ms (in practice ~0.1 ms).

Dependencies and licences: [`DEPS.md`](DEPS.md).
