# Mixing to a delivery target

How the mix tools fit together, and how to hit the loudness and peak a destination asks for. How it should sound is
your call; the tools tell you where you are.

## The signal path

track (instrument, notes / clips) → its effect chain → its fader and pan → sends to buses → bus chains → master
(glue, reverb, master effects) → master volume → loudness normalize → true-peak limiter → file.

- **Tracks:** `track.set` for volume, pan, mute. **Buses:** `bus.add` / `bus.set` (`output` routes a bus into another
  bus or the master). **Sends:** `send.add` on a track (`bus`, `level`, `pre` = before the fader).
- **Effects:** `effect.add` on a track, bus or master (`effect` names the kind; settings depend on it: an EQ has `bands`,
  a compressor `threshold`, `ratio`, `attack`, `release`, `makeup`, `knee`, a reverb `space`, `mix`, `decay`).
  `effect.set` changes one, `bypass` switches it off without losing settings. Plug-ins (CLAP / VST3) go in the same
  chain (inspect_plugins).
- **Ducks:** `duck.add` on a track with `under` = the tracks that push it down (music under dialogue), and `depth`,
  `attack`, `release`, `hold`. The `voice` setting listens for speech only. On the screen: "+ Duck" on a strip.
- **Automation:** `automation.set` with `lane` and the whole `points` list. Mix values, effect settings and plug-in
  parameters can be automated (inspect_operations lists the lanes). On the Timeline: a row's "Auto" chip opens its lanes;
  click adds a point, drag moves it, Delete removes it; one drag = one undo step.

## Loudness words, briefly

- **Integrated loudness (LUFS):** the whole mix's average loudness, as the destination measures it.
- **Short-term loudness (LUFS-S):** the last 3 seconds; shows where a mix gets loud or dips.
- **True peak (dBTP):** the highest the waveform reaches between samples after conversion. Over the ceiling = distortion
  on some players.
- **Loudness range (LU):** how much the loudness moves between quiet and loud parts.

## Setting the target

`master.set` with `normalize` on, `loudness` (LUFS) and `truePeak` (dBTP ceiling). The screen's Mix page has a
"Deliver to" chooser with published targets (streaming, Apple Music, EBU R128, ATSC A/85, podcast; each row cites its
source in `screensound/delivery.py`) that sets both in one step, and a Pass / Miss line from the last render.

Normalizing makes the number right; it does not make the mix right. If the master limiter is working hard to hold the
ceiling, the mix is denser than the target allows: turn the loud parts down at the source rather than squeezing harder.

## Checking (agents)

1. `render_mix` (stems on). Its reply already has integrated LUFS, true peak and each track's level.
2. `look_loudness`: integrated, true peak, range, the short-term curve as a picture, clipped moments.
3. `look_levels`: each stem's level and how far under the loudest / the mix; flags a buried or dominant track.
4. `look_clash`: which two tracks fight in which frequency band, and when.
5. `look_low_end`: each track's share below 150 Hz and 60 Hz. `look_stereo`: balance and mono safety.
6. Change one thing, render, look again. Compare numbers between renders, not against a rule.

## Stems and handoff

`render_mix` with `stems: true` writes one WAV per track and per bus (`<bus>.bus.wav`) beside the mix in
`renders/<item>/vNNN/`. On the screen: Mix › "Render mix and stems" (needs a project folder).
`render_mix` with `master: false` gives the mix before mastering, for someone else to master.
