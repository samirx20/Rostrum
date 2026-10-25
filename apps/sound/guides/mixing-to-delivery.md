# Mixing to a delivery target

How the mix tools fit together, and how to hit the loudness and peak a destination asks for. How it should sound is
your call; the tools tell you where you are.

## The signal path

track (instrument, notes / clips) → its effect chain → its fader and pan → sends to buses → bus chains → master
(glue, reverb, master effects) → master volume → loudness normalize → true-peak limiter → file.

- **Tracks:** `track.set` for volume (gain 0 … 4, or in dB: `{"db": -6}`; tracks with a built-in instrument or the built-in kit start roughly balanced at the same volume for the part each suits (inspect_engine), so move a track for what the music needs (a lead 3 dB up, a pad 6 dB down) and check with `look_levels`: a sound played outside its part (one loud chord on a glockenspiel) can be several dB off), pan, mute. **Buses:** `bus.add` (named "Group 1", "Group 2" … unless you give `name`; the id such as `bus_1` is internal) / `bus.set` (`output` routes a bus into another
  bus or the master). **Sends:** `send.add` on a track (`bus`, `level`, `pre` = before the fader).
- **Effects:** `effect.add` on a track, bus or master (`effect` names the kind; every new effect starts valid and playable with its default settings: an EQ starts with one flat band (peak, 1000 Hz, 0 dB, q 1) that changes nothing until you move it, and settings depend on the kind: an EQ has `bands`,
  a compressor `threshold`, `ratio`, `attack`, `release`, `makeup`, `knee`, a reverb `space`, `mix`, `decay`).
  `effect.set` changes one, `bypass` switches it off without losing settings. On screen an effect's amounts (mix,
  feedback, drive, width, damping) read in percent (stored 0–1: type "20 %" or 0.2) and a ratio reads "3 :1". Plug-ins (CLAP / VST3) go in the same
  chain (inspect_plugins).
- **Ducks:** `duck.add` on a track with `under` = the tracks that push it down (music under dialogue), and `depth`,
  `attack`, `release`, `hold`. The `voice` setting listens for speech only. On the screen: **+ Dip under…** on a strip.
- **Automation:** `automation.set` with `lane` and the whole `points` list. Mix values, effect settings and plug-in
  parameters can be automated (inspect_operations lists the lanes). In the arrangement: a row's **A** button opens its lanes;
  click adds a point (in the grid cell under the pointer), drag moves it, Delete removes it; one drag = one undo step.

## The Mixer's strips

The Mixer (X) has one strip per track, then the groups (buses), then the master. Each strip, top to bottom:

- a bar in the track's colour (the same as in the arrangement; groups and the master are grey) and the name;
- its effects, one line each in the order they play (click one to edit it in the settings panel; a switched-off one
  is dim), and **+ Effect** under them on every strip;
- its sends: **Reverb send** (how much goes to the master's reverb, in %; the same setting as Reverb in the settings
  panel), one row per group it feeds (drag the slider), **+ Send** while there is a group it doesn't feed yet,
  and its dips with **+ Dip under…**;
- where it plays to: "→ Master", or a pick of the groups when there are any;
- **Pan** (C = centre) and its slider, which fills from the centre toward the side you pan to (double-click: back to the centre);
- the fader with a dB scale beside it (+6, 0, −6 … −∞), and the meter with a number above it. While the song plays
  the meter moves with what you hear: the wide bar is the average level (RMS), the thin bar beside it the peak, and a
  mark holds the highest peak for a second before it falls. The number is one thing on every strip, group and the
  master: the highest peak, in dBFS, since play started. It keeps climbing while the song plays and stays after you
  stop, until the next play starts and clears it (nothing before the first play, "−∞" for a strip that has made no sound).
  Stopped, the meter bars fall to empty and only the number stays. The levels are the engine's own, measured on the
  render that plays; a group reads higher than its tracks when sends, reverb or its own effects add to what the tracks
  put in. Green below −6 dB, amber from −6 to 0 and red over
  0, on every strip, group and the master. Rest the pointer on it for the track's loudness;
- **M** (mute, amber), **S** (solo, green) and **R** (arm for recording, red), tracks only for S and R;
- its volume in dB: click it and type (−6, 1.5, −inf); a value outside −60 … +12 dB is refused with that range. The
  fader's knob drags; the mouse wheel over the fader nudges it (1 dB a notch, Shift 3 dB, Alt 0.1 dB); Alt-click on the
  fader sets 0 dB; double-click the fader to type. While the Mixer is open the track's settings panel does not repeat the volume: it keeps Name, Colour, Sound (or Kit) and Tone filter.

The fader takes all the height the dock has left (the dock gets taller, the fader, its dB scale and the meter grow with it). In a dock under about 460 px (a laptop screen) the sends and ducks move into the **…** button on the output line (click it: the reverb send, the group
sends and **+ Dip under…** open above it); the fader, M S R and the volume stay. Every fader starts at the same height,
the master's too: a new track starts at 0 dB (gain 1), and headroom is the main bus's business, not each track's.

## The Mixer's loudness panel

The strips sit side by side from the left, the Master right after the last one; with many tracks they scroll sideways
and the Master stays in place. The rest of the width is the loudness panel: its title names the target ("Loudness ·
target −14 LUFS (Streaming)"), then three numbers, **Whole song** (how loud the whole mix is; "So far" while playing),
**Now** (the 3 seconds before the playhead; before the first 3 seconds, or when stopped at the start, it shows the last value in grey, and is absent until the song has had one) and **Loudest peak** ("Loudest so far" while playing), and under them
the short-term loudness over the song, with the target as a dashed line and the playhead. Whole song is green within
1 of the target and amber outside; Loudest peak is amber only over the ceiling. The Master strip's meter number, when
stopped, is the same true peak. Rest the pointer on a number for what it means.
An open effect's settings or a duck sit at the right end while they are open.

## Loudness words, briefly

- **Integrated loudness (LUFS):** the whole mix's average loudness, as the destination measures it.
- **Short-term loudness (LUFS-S):** the last 3 seconds; shows where a mix gets loud or dips.
- **True peak (dBTP):** the highest the waveform reaches between samples after conversion. Over the ceiling = distortion
  on some players.
- **Loudness range (LU):** how much the loudness moves between quiet and loud parts.

## Setting the target

`master.set` with `normalize` on, `loudness` (LUFS) and `truePeak` (dBTP ceiling). On the screen, the Export sheet
(Ctrl+E) has a "What for" picker with published targets (Streaming, Apple Music, Broadcast = EBU R128, US TV = ATSC A/85, Podcast; each
row cites its source in `screensound/delivery.py`) that sets both in one step (and says so on the sheet), and a "Right for the target" / "Misses the target" line from the sound
that plays now. The top bar's Loudness chip shows the song's loudness against the target; it opens the Mixer.

Normalizing makes the number right; it does not make the mix right. If the master limiter is working hard to hold the
ceiling, the mix is denser than the target allows: turn the loud parts down at the source rather than squeezing harder.

## Checking (agents)

1. `render_mix` (stems on). Its reply already has integrated LUFS, true peak and each track's level.
2. `look_loudness`: integrated, true peak, range, the short-term curve as a picture, clipped moments.
3. `look_levels`: each stem's level and how far under the loudest / the mix; flags a buried or dominant track.
4. `look_clash`: which two tracks fight in which frequency band, and when.
5. `look_low_end`: each track's and the mix's share below 150 Hz, below 60 Hz and in the low mids (150–500 Hz). `look_stereo`: balance and mono safety.
6. Change one thing, render, look again. Compare numbers between renders, not against a rule.

## Stems and handoff

`render_mix` with `stems: true` writes one WAV per track and per bus (`<group name>.wav`) beside the mix in
`renders/<item>/vNNN/`. On the screen: the Export sheet (Ctrl+E) with **Stems** on, then **Export**.
**The rule, in plain words:** a stem leaves through the master's *volume* (master fader and its automation, the
fades, and the gain that brings the mix to its loudness target) but not through the master's *glue compressor,
limiter or master effects* (those can't be split between stems). So the stems add up to the mix exactly wherever
none of those acted. The manifest (`manifest.json`, `stems_rule`) says how far they can differ:
`limiter_max_reduction_db` and `glue_max_reduction_db` (the most the limiter / glue turned the mix down, dB),
`master_effects_on_mix_only` (true if the master has effects, reverb or time warps), `master_gain_db` (already in
the stems), and `stems_add_up` (true only when all of these are nothing). A limiter reduction of 0.5 dB means the
stems sum up to 0.5 dB louder than the mix at the worst moment.
`render_mix` with `master: false` gives the mix before mastering, for someone else to master.
