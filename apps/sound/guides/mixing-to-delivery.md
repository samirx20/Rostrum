# Mixing to a delivery target

How the mix tools fit together, and how to hit the loudness and peak a destination asks for. How it should sound is
your call; the tools tell you where you are.

## The signal path

track (instrument, notes / clips) → its effect chain → its fader and pan → sends to buses → bus chains → master
(glue, reverb, master effects) → master volume → loudness normalize → true-peak limiter → file.

**Gentle limiting** (master `gentle`, on in every new song; `maxLimit` 2 dB): the limiter may pull the loudest moment
down by at most `maxLimit`. A mix that would need more (piano chords or drum hits whose peaks stand far above the
song's loudness) is turned down as a whole instead, one gain for the whole song, so the balance between tracks stays
and the master stays clean; the song then lands under its loudness target, and the `render_mix` reply says by how
much and what to do ("… landed 1.9 dB under the -14 LUFS target: call edit_loudness first"). `maxLimit` is in dB, 0 to 12 in the
document (`master.set`; the screen's **Most limiting**).

**Reaching the target, first step: `edit_loudness`.** Do not rebalance by guess and do not raise `maxLimit` by feel. With the target
on, raising every track's volume changes nothing (the master brings the mix to the target anyway); only the peaks over the average decide how much
limiting the target takes. `edit_loudness` reads the last render and answers two exact edits, each with `ops` for `edit_document`:
`keep_balance` (the `maxLimit` that reaches the target; no track moves; the master gets flatter and denser, 4–6 dB is a loud, pressed master)
and `trim_track` (the smallest cut, at most 12 dB, to the most peaked track, found by re-rendering, that reaches the target inside the master's
own `maxLimit`; the balance moves; if no cut of that track is enough it says so, and `track` tries another). One call applies one:
`edit_loudness {"apply": "keep_balance"}`, or `{"apply": "trim_track", "track": "drums"}`, then `render_mix` again: the second render is on the target. The
trade-off is **cleaner** (`trim_track`: nothing is squeezed, the balance moves) or **louder** (`keep_balance`: the balance does not move). With the master's
loudness target off, `edit_loudness` answers the `master.set` that turns it on.
Songs saved before 2026-10-25 open with it
off, so they sound as they did.

- **Tracks:** `track.set` for volume (gain 0 … 4, or in dB: `{"db": -6}`; tracks with a plain-named instrument or a drum kit start roughly balanced at the same volume for the part each suits (inspect_engine; kits and bass a few dB under, brass no louder than strings), so move a track for what the music needs (a lead 3 dB up, a pad 6 dB down) and check with `look_sound` (`what: "levels"`): a sound played outside its part (one loud chord on a glockenspiel) can be several dB off), pan, mute. **Buses:** `bus.add` (named "Group 1", "Group 2" … unless you give `name`; the id such as `bus_1` is internal) / `bus.set` (`output` routes a bus into another
  bus or the master). **Sends:** `send.add` on a track (`bus`, `level`, `pre` = before the fader).
- **Effects:** `effect.add` on a track, bus or master (`effect` names the kind; every new effect starts valid and playable with its default settings: an EQ starts with one flat band (peak, 1000 Hz, 0 dB, q 1) that changes nothing until you move it, and settings depend on the kind: an EQ has `bands`,
  a compressor `threshold`, `ratio`, `attack`, `release`, `makeup`, `knee`, a reverb `space`, `mix`, `decay`).
  `effect.set` changes one, `bypass` switches it off without losing settings. Every effect's settings with units and ranges
  (compressor `threshold` dB as a plain number, `attack` / `release` in seconds, the reverb spaces, the master's `loudness`, `truePeak`, `fadeOut` …):
  `inspect_engine`, and the table in `inspect_guide 'script'` ("Effects and the master"). On screen an effect's amounts (mix,
  feedback, drive, width, damping) read in percent (stored 0–1: type "20 %" or 0.2) and a ratio reads "3 :1". Plug-ins (CLAP / VST3) go in the same
  chain (inspect_engine (what "plugins")).
- **Ducks:** `duck.add` on a track with `under` = the tracks that push it down (music under dialogue), and `depth`,
  `attack`, `release`, `hold`. The `voice` setting listens for speech only. On the screen: **+ Dip under…** on a strip.
- **Automation:** `automation.set` with `lane` and the whole `points` list. Mix values, effect settings and plug-in
  parameters can be automated (inspect_operations lists the lanes). In the arrangement: a row's **A** button opens its lanes;
  click adds a point (in the grid cell under the pointer), drag moves it, Delete removes it; one drag = one undo step.

## The Mixer's strips

The Mixer (X) has one strip per track, then the groups (buses), then the master; **+ Group** sits on the master's strip,
under its effects (a new group plays into the master). Each strip, top to bottom:

- a bar in the track's colour (the same as in the arrangement; groups and the master are grey) and the name;
- its effects, one line each in the order they play (click one to edit it in the settings panel; a switched-off one
  is dim; **drag a line up or down** to change the order (right-click a line for **Remove**, as the Delete key does), a line shows where it will land, one Undo puts it back;
  an agent calls `effect.move {to}`), and **+ Effect** under them on every strip: it stays in view under the lines even
  when there are more effects than fit (the lines scroll above it). Every strip keeps the room for its effect lines
  whether they are used or not, so adding an effect never moves a pan or a fader. The menu and the chain say the same names (Saturation, Stereo width, De-esser …);
- its sends: **Reverb send** (how much goes to the master's reverb, in dB like every send; the same setting as Reverb in the
  settings panel), one row per group it feeds (drag the slider; right-click a group send for **Remove**), **+ Send** while there is a group it doesn't feed yet,
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
- its volume in dB: click it and type (−6, 1.5, −inf; −60, the fader's floor, also reads −∞); a value outside −60 … +12 dB is refused with that range. The
  fader's knob drags; the mouse wheel over the fader nudges it (1 dB a notch, Shift 3 dB, Alt 0.1 dB); Alt-click on the
  fader sets 0 dB; double-click the fader to type. While the Mixer is open the track's settings panel does not repeat the volume: it keeps Name, Colour, Sound and Tone filter. In the settings panel a number goes back to its default when you double-click its box or slider (or right-click it and choose Reset).

The fader takes all the height the dock has left (the dock gets taller, the fader, its dB scale and the meter grow with it). In a dock under about 460 px (a laptop screen) the sends and ducks move into the **…** button on the output line (click it: the reverb send, the group
sends and **+ Dip under…** open above it); the fader, M S R and the volume stay. In a very low dock (a 720-px-high
window) the effect lines get less room and scroll; the volume box is never cut off. Every fader starts at the same height,
the master's too: a new track starts at 0 dB (gain 1), and headroom is the main bus's business, not each track's.

## The Mixer's loudness panel

The strips sit side by side from the left, the Master right after the last one; with many tracks they scroll sideways
and the Master stays in place. The rest of the width is the loudness panel: its title names the target ("Loudness
target −14 LUFS (Streaming)", on a second line when the panel is narrow), then three numbers, **Whole song** (how loud the whole mix is; "So far" while playing),
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

Normalizing makes the number right; it does not make the mix right. With gentle limiting on, a mix denser than the
target allows comes out under the target (the reply says how far; `edit_loudness` gives the exact edit) rather than squeezed; with it off the limiter works
as hard as it must. Either way the fix is at the source: turn the loud parts down rather than squeezing harder.

## Checking (agents)

1. `render_mix` (stems on). Its reply already has integrated LUFS, true peak and each track's level.
2. `look_sound` (`what: "loudness"`): integrated, true peak, range, the loudest moment and its time, the short-term curve as a picture, clipped moments.
3. `look_sound` (`what: "levels"`): each stem's level and how far under the loudest / the mix; flags a buried or dominant track.
4. `look_sound` (`what: "clash"`): which two tracks fight in which frequency band, and when.
5. `look_sound` (`what: "low_end"`): each track's and the mix's share below 150 Hz, below 60 Hz and in the low mids (150–500 Hz). `look_sound` (`what: "stereo"`): balance and mono safety.
6. Change one thing, render, look again. Compare numbers between renders, not against a rule.

## Stems and handoff

`render_mix` with `stems: true` writes one WAV per track and per bus (`<group name>.wav`) beside the mix in
`renders/<item>/vNNN/`. On the screen: the Export sheet (Ctrl+E) with **Stems** on, then **Export**.
**The rule, in plain words:** a stem leaves through the master's whole *gain*: master fader and its automation,
the fades, the glue compressor, the gain that brings the mix to its loudness target and the limiter. The engine
works that gain out once, on the mix, and gives every stem the same turn-down at the same moment, so the stems
(the ungrouped tracks' plus the group stems) add up to the mix and a stem does not clip where the mix doesn't.
What can't be split between stems, the master's effects, its reverb, time warps and the safety clip, is on the
mix only. The manifest (`manifest.json`, `stems_rule`) says it: `on_mix_only` (those, by name; empty normally),
`max_difference` (the most the stems' sum and the mix differ, as a sample value, measured when the stems hold
everything that reaches the master), `stems_add_up`, and the master's `master_gain_db`,
`glue_max_reduction_db` and `limiter_max_reduction_db` (all already in the stems). Each stem's `loudness_lufs`,
`true_peak_db`, `sample_peak_db` and `clipped_samples` are measured on the file written. The render reply's
`warnings` (and the Export sheet's result line) say in words when a file was cut flat or the stems don't add up.
A render that made no stems has no `stems`, `bus_stems`, `direct`, `stems_rule` or `stems_add_up` in its manifest: the manifest says nothing about stems that do not exist.
**Ending a file:** a held note and its reverb stop at the song's `length`; `master(fadeOut=...)`, a later `length` and the `trim` option are in
`inspect_guide 'script'` ("Ending a song"). `trim` only cuts below -80 dBFS and says `trimmed: false` when sound is still above that at the end.
Check the end with `look_sound` (`what: "loudness"`), whose `ending` line gives the last 0.5 s level, whether it is still above -50 dBFS and whether the last 50 ms drop faster than the fade (a cut).
`render_mix` with `master: false` gives the mix before mastering, for someone else to master.
