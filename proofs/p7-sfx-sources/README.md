# P7 · Where better sound effects come from: a listening page

**Question.** Sam heard P6's designed sounds as "the same thing, just more metallic". With the P6 placement (motion
reading, sync, glue bus) unchanged, how do real recordings from the sources we may use compare?

**Verdict: for Sam to choose by ear.** The research and the choice are in `apps/sound/SFX_SOURCES.md`. Measured: only
the Sonniss bundles (which the user must bring; we can't ship them) are full-band, studio-clean recordings. The sounds
we may ship (Freesound CC0, Kenney CC0) are usable but uneven, and need picking by ear.

## Setup

`score_source.py <source> [picks.json]` scores P6's 10 s slide deck (`proofs/p6-motion-sfx/`, motion events from
copied here as `slides-events.json`) with one source's recordings:
- each whoosh's loudest moment sits on the card's fastest moment, pans with the card, is louder for faster moves, and
  is trimmed with a fade after the move;
- a click where a card lands hard;
- ticks a little different in pitch and level;
- the button's press and release;
- everything on P6's `ui` glue bus, at −16 LUFS.

The picks (one take per role, per source) are in `picks-p7.json`: the libraries member's choices, plus the release
half of the Sonniss button file and the MP3 previews converted to WAV once. The engine and the measuring tool disagreed
by about 25 ms on MP3 start padding; on WAV they agree.

Mux: `proofs/p6-motion-sfx/mux.py`. Sync: `proofs/p6-motion-sfx/check_sync.py`.

## Results (`C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\`)

`slides-sonniss.mp4`, `slides-free-to-ship.mp4` (Freesound whooshes + Kenney clicks), `slides-freesound.mp4`,
`slides-kenney.mp4`, `slides-designed-p6.mp4` (P6, for comparison), each with its `.wav`.

| Source | Loudness | True peak | Whoosh peak vs fastest moment (entrances) | Clicks / ticks vs frame |
|---|---|---|---|---|
| Sonniss | −16.0 | −1.6 dBTP | 1–43 ms | ≤ 0.3 ms (ticks), landing click 35 ms early (under its whoosh) |
| Freesound | −16.1 | −3.6 | 1–3 ms | ≤ 22 ms |
| Kenney | −16.0 | −4.2 | 1–4 ms | ≤ 40 ms (landing), ticks 13 ms |
| Free to ship | −16.0 | −1.3 | 1–3 ms | ≤ 13 ms |

Exits overlap (four cards leave within 1.2 s), so the checker can't measure them separately. Spectrograms: Sonniss
runs to 20 kHz on every sound; the Freesound previews stop near 14 kHz (the MP3 preview format).

Each render takes about half a second on the CPU, with no GPU and no model.

## Attribution rows

No new dependencies. The evaluation recordings are not shipped and are not in the repo. Their sources and licences are
in `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\research\` (`sonniss_prov.json`, `freesound_prov.json`,
`libraries.md`).
