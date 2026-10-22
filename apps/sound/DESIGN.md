# RostrumSound — design from the workflows (P26)

*Design member, Team Priyam, 2026-10-22. Written from six real jobs walked step by step, today's screen walked
the same way with pictures (`C:\Users\Sam\.rostrum\waves\results\sound-redesign\p26\before\`), and how the best
tools structure the same work (Logic Pro, GarageBand, Ableton Live, Reaper, Hindenburg, Descript), studied, not
copied. Judged by the 3E's: **effective** (it does the job fully), **efficient** (few clicks, no screen hopping),
**easy** (you see what to do next without being taught).*

Contents: 1 the select-first operations (for the ops member) · 2 the jobs, step by step · 3 today's screen, counted ·
4 the structure · 5 the basics a person expects · 6 requests to the shared kit · 7 open points · 8 for docs/PLAN.md.

**Decided by the lead (P26), from this document:** §4 is adopted as written: one workspace (arrangement in the
centre, Editor / Mixer dock below), the Sounds panel instead of the Instruments page, Deliver as its own dialog with
a loudness readout in the top bar, actions on the selection, tools that appear when used. Where it needs the kit:
- **The selection list, the context bar and the right-click menu are built in apps/sound now** (Team Hem owns the
  kit and is changing it in H28). They take the kit's own command list (`commands.build` already accepts a list), so
  moving them into the kit later changes no behaviour: that is request §6.1–6.4, and 2D's select-first actions should
  use the same pieces once they are there, never a second copy.
- **"Make a part" waits** for a `part` field (Team Sam, schema): every job works on note selections without it.
- **Bounce and "export this range"** wait for the block-by-block render (P26 B), which makes a time range cheap
  to render; then `render_mix` gets `from` / `to` on the one export path.
- **Voice edited by its words** (a transcript of recordings) is the next brief, not this one.

---

## 1. Select first, then act — the operations

Rule (manager, binding): you select the things, then act on them. Never an empty container first ("+ Bus", then
route each track into it). Every action is **one operation taking the selected ids** (`target: [ids]`), so a
person's right-click and an agent's MCP call are the same call, one undo step. Actions are reached four ways, all
built from the same list: the **context bar** (a small strip that appears over the arrangement only while the
selection allows something), the **right-click menu**, **Ctrl+K**, and **shortcuts**.

Status: **exists** = registered today in `apps/sound/python/rostrum_sound/doc/ops_*.py` and already takes a list of
targets; **new** = the ops member builds it under this name.

| You select | Action (label people see) | Operation | Status | What it does (one undo step) |
|---|---|---|---|---|
| tracks | Send to a new group | `bus.from_tracks` | **new** | Adds a bus (name optional, default "Group 1"), sets every selected track's `output` to it, places it after the last selected track. Fails loudly if a track already plays into a bus that plays into one of them (a loop). |
| tracks | Colour | `track.set {colour}` | exists once `colour` lands (S26 is adding the field) | Same colour on all. |
| tracks | Mute / Solo together | `track.set {mute}` / `{solo}` | exists | Toggles all to the same state (if any is off, all go on). |
| tracks | Duplicate track | `track.duplicate` | **new** | Copies tracks with everything on them, new ids, placed below each. |
| tracks | Delete | `track.remove` | exists | |
| tracks | Add effect: … | `effect.add` | exists | One insert per selected track. |
| clips | Split at playhead | `clip.split` | **new** | Each selected clip that spans `at` becomes two clips (`in` / `length` adjusted, fades: the left keeps its fade-in, the right its fade-out, effects copied, `group` kept). `at` defaults to the playhead. |
| clips | Join | `clip.join` | **new** | Valid only when the clips are on one track, use the same `media` and touch in the file (`in` + `length` of one = `in` of the next): one clip. Anything else is a bounce (below), not a join; the action is absent, never greyed. |
| clips | Fade in / fade out | `clip.set {fadeIn, fadeOut}` | exists | Same fade on all; the drag on a clip's top corner sets it on that clip (gesture). |
| two clips touching or overlapping on one track | Crossfade | `clip.crossfade` | **new** | Sets the first's `fadeOut` and the second's `fadeIn` to the overlap (or `length` arg when they only touch: extends the second's start into the first's tail, from its file). |
| clips | Normalise | `clip.normalize` | **new** | Sets each clip's `volume` so its loudest peak (or loudness, `by: peak|loudness`) reaches `to`. The measurement is analysed once and cached by media + range (AGENTS rule 7). |
| clips | Clean up (voice, noise, echo, stem) | `clip.set {isolate, denoise, dereverb, stem}` + job `render_cleanup` | exists | The recipe on all selected; "Make cleaned takes" then runs the existing job for those clips only (today it runs for one). |
| clips | Add effect to just these | `effect.add` with clip targets | exists | Clips already own an `effects` list (`registry.LISTS`). The screen never offers it today. |
| clips | Layer as one sound | `clip.set {group}` | exists | Same group name on all (they then move / level together). |
| clips | Split into stems | `clip.split_stems` | exists | |
| clips, notes, hits, sounds, lines | Duplicate (Ctrl+D) | `note.duplicate`, `hit.duplicate`, `clip.duplicate`, `sound.duplicate`, `line.duplicate` | **new** | Copies right after the selection's end (by its span), new ids, times written in the original's form (beats stay beats, `#marker+x` stays on its marker: `shift.write_like`). Registered by the same maker as `.add/.set/.remove` in `ops_timed.py`. |
| clips, notes, hits, sounds, lines | Nudge (arrow keys) / move together | `note.move`, `hit.move`, `clip.move`, `sound.move`, `line.move` | **new** | `by`: seconds or `{"beats": n}`, like `section.move`'s `by`; also `semitones` for notes. Each item keeps its written form. A mouse drag of several is one `move` at the end (one undo step). |
| notes (or hits) | Quantise | `note.quantize`, `hit.quantize` | **new** | `grid` (beat, 1/8, 1/16, 1/8T …), `strength` 0–1 (default 1), `ends` (also lengths, default off). |
| notes | Transpose | `note.transpose` | **new** | `semitones` (±), or `in_key: true` to move by scale steps in the key playing there (`key.*` exists). |
| notes (or hits) | Humanise | `note.humanize`, `hit.humanize` | **new** | `timing` (ms), `velocity` (0–1 spread), `seed` (same seed = same result, so an agent re-run is stable). |
| notes (or hits) | Set velocity | `note.set {vel}` / `hit.set {vel}` | exists | Absolute on all; a drag on the velocity strip scales them together (one `note.set` per gesture end). |
| notes | Make a part | see "Parts" below | **needs Team Sam** | |
| notes, hits, clips, sounds | Delete | `<type>.remove` | exists | |
| a time range (drag on the ruler) | Loop this | screen state, no op | — | Loop is playback state (the transport), not the song. |
| a time range | Make a section | `section.add {at, end}` | exists | Asks only the name. |
| a time range (+ optional tracks) | Bounce to audio | job `bounce` → `track.add` + `clip.add` | **new job** | Renders the range of the selected tracks (all when none) through the engine (preview ≡ export) to `media/bounce-<n>.wav`, then one batch: a new audio track with that clip; the sources are muted, not deleted. |
| a time range | Export this range | job `render_mix {from, to}` | **extend** | The existing render (`handoff.render`) gains `from` / `to`. |
| a time range | Delete time / insert time | `range.remove`, `range.insert` | later | Like `section.move` for everything after; noted, not needed for the six jobs. |
| one track (armed) | Record | screen + engine (exists) | exists | |
| a voice track | Add a spoken line at the playhead | `line.add` | exists | The screen has no way to call it today (the card says "add one with line.add"). |
| the playhead / a time | Add marker here | `marker.add {name, at}` | exists | The screen has no way to call it today (it needs a name: the context bar asks it inline). |

Paste (Ctrl+V) needs no new operation: the clipboard is screen state, and paste is the existing
`note.add_many` / `hit.add_many` / `sound.add_many` / `clip.add` (one batch) on the selected track at the playhead.

### Parts ("make a part") — a flag for Team Sam

Today notes and hits live directly on a track: there is no region / part. Logic and GarageBand let you select a
phrase as one block (move, loop, duplicate it, open it in the editor); Ableton's clips do the same. Two answers:

- **Without a schema change (now):** "Make a part" is not offered. Everything a part is used for works on a note
  selection: select the notes (box or by range on the track), Duplicate / Move / Loop the range. A "range on a
  track" (drag on the track's lane in the arrangement) selects every note in it, which is what clicking a region does
  in Logic. This is enough for the six jobs.
- **Later (Team Sam, a schema change):** a `part` name field on notes and hits, exactly like the `group` name on
  clips (`ops_group.py`): no second list that could disagree with the notes. Then `part.make` (notes → a name),
  and the arrangement draws a part as one block you can grab, duplicate as a whole and see named ("chorus riff").
  **Flagged, not designed around.** Recommendation: do it after the one-workspace screen lands, if Sam's use
  shows people miss blocks.

---

## 2. The jobs, step by step

Each step: what the person is thinking · what they need on screen · what they don't need then.

### A. Write a song from scratch (parts, instruments, notes)

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1 New song | "Where do I start?" | Empty arrangement with one obvious action: **Add a track** (and tempo / key / bars in the top bar) | Mixer, delivery, effects, inspector full of master settings |
| 2 Pick a sound | "A piano? a pad?" | Sounds list (instruments + kits + my library), audition on hover/click, pick = a track with that sound | A track with a default sound I must change afterwards |
| 3 Play / write the idea | "Get the chords down" | The **editor** (piano roll) for that track, big; a keyboard or click-to-add; the grid in the song's key; metronome | Other tracks' detail, mixer |
| 4 Shape it | "Longer notes, softer here" | Drag note ends; velocity strip; quantise / transpose on the selection | The inspector's long list of synth settings |
| 5 Build the song | "Verse, chorus, repeat this 4 bars" | The **arrangement** big: sections on the ruler, all tracks, select a range → duplicate | The piano roll of one track |
| 6 Add more instruments | "Bass under it, drums" | Same as 2–4, the arrangement stays above | — |
| 7 Shape the sound | "Warmer pad" | That track's instrument settings (inspector, essentials first) | Everyone else's settings |
| 8 Listen through | "Does it flow?" | Arrangement + playhead + loop range | Editor |

**Best tools:** GarageBand / Logic: the arrangement (tracks × time) is the centre; the selected region's editor
opens *below* it (one key, E), the library of sounds on the left when choosing. Ableton: the clip's detail in a
bottom panel. **Lesson:** the arrangement is the song and stays in the middle; the note editor is a detail of a
selection, below it.

### B. Score a video to picture and its markers

| Step | Thinking | Needs | Doesn't need |
|---|---|---|---|
| 1 Bring the picture | "Show me the film" | Picture panel (from a file or a 2D item of the project), sized by me, its markers on the ruler | Mixer |
| 2 Find the hits | "Logo lands at 4.2 s, cut at 9" | Scrub with picture; **Add marker here** (M) with a name; the project's shared markers from 2D already there | Typing seconds |
| 3 Fit the tempo | "Make bar 5 land on the cut" | Tempo in the top bar; a tempo change at a marker; the ruler in bars *and* seconds | — |
| 4 Write to the hits | "Swell into the logo" | Arrangement + editor; things snap to markers; times written on the marker ("#logo−0.5") | — |
| 5 Check sync | "Does it hit?" | Play with the picture, loop the range | Editor |

**Best tools:** Logic's movie window floats and its scene markers sit on the ruler. **Lesson:** picture is a
*tool panel* that appears when you load one; markers are the shared language (AGENTS rule 8), and making one must be
one key.

### C. Record a voice-over and clean it up

| Step | Thinking | Needs | Doesn't need |
|---|---|---|---|
| 1 Set up | "Is my mic on, am I loud enough?" | Pick input, **level meter**, Hear input, count-in | Instruments, piano roll |
| 2 Record | "Go" | Big record / stop, a timer, the take appearing as I speak | Anything else |
| 3 Review | "Which take? Cut the fluffs" | The voice as **words** (transcript) and waveform; split / delete / close gaps | Notes, mixer |
| 4 Clean | "Less room, no hiss" | Clean up on the selected clips (voice isolate, noise, echo), before / after listen | Effects chain jargon |
| 5 Level | "Even, podcast loud" | Normalise selected clips; the loudness meter against the target | Faders of other tracks |
| 6 Deliver | "An mp3/wav at −16" | Deliver dialog with the podcast target | — |

**Best tools:** Hindenburg: voice tools, auto-levelling and a loudness meter always visible, delivery by target.
Descript: edit the voice by editing its words. **Lesson:** voice work is about words and loudness, not notes and
buses. We have no transcript yet (open point 3); until then the waveform with split / close gap carries step 3.

### D. Design sound effects for motion

| Step | Thinking | Needs | Doesn't need |
|---|---|---|---|
| 1 See the motion | "Where does it whoosh / hit?" | Picture or the 2D markers on the ruler | Piano roll |
| 2 Find / make a sound | "A whoosh, 0.6 s" | Sounds panel: my library (search by kind), **designed sounds** (whoosh, impact, riser … with their settings), audition | — |
| 3 Place it | "On 'logo lands'" | Drop at a marker / the playhead; it stays on the marker when 2D moves | — |
| 4 Shape it | "Faster, darker, layer a thud" | The selected sound's settings (inspector), layer = group of clips/sounds | Track instrument settings |
| 5 Sit it in | "Under the music" | Level, duck under voice | Delivery |

**Lesson:** a **Sounds panel** (library + designed sounds + instruments) is one place for "find a sound", placed on
the selected track at the playhead. Today the library panel is built but not shown and designed sounds have no
screen at all.

### E. Mix to delivery loudness

| Step | Thinking | Needs | Doesn't need |
|---|---|---|---|
| 1 Balance | "Voice up, pad down" | Mixer: faders, pan, meters, mute / solo, names in plain words | Piano roll |
| 2 Group | "Drums together" | Select tracks → Send to a new group | "+ Bus" then routing each |
| 3 Effects | "Glue, space" | Effects on the strip / selection, their settings in the inspector | — |
| 4 Duck / automate | "Music under the voice" | Duck on the selection, lanes on the arrangement | — |
| 5 Hit the target | "Streaming −14" | Loudness meter + target line always visible while mixing | — |
| 6 Deliver | "Final WAV + stems" | **Deliver dialog**: target, format, rate, range, stems, Pass / Miss, Render, Show folder | The master strip carrying all of it |

**Best tools:** Logic's mixer is a key away (X), not a separate app; Reaper's render dialog holds format, range and
stems together. Hindenburg puts the loudness meter always on screen.

### F. An agent builds a cue while a person tweaks it

| Step | Thinking | Needs | Doesn't need |
|---|---|---|---|
| 1 Ask | "Make a 20 s tension cue to the markers" | Agent works through MCP on the same document | — |
| 2 Watch | "What is it doing?" | Changes appear live on the arrangement; history shows **who** made each change | A frozen screen |
| 3 Tweak | "Too busy in bar 3" | Select notes → act, exactly as alone; my edits are not wiped when the agent re-runs (AGENTS rule 3) | — |
| 4 Hand back | "Tidy the ending" | Select a range → the command box / the agent gets the selected ids | — |

**Lesson:** select-first makes the agent and the person speak the same language: "the selection" is ids, the
actions are operations. The screen needs a "who changed this" mark in history (exists in the kit's history) and
no special agent mode.

---

## 3. Today's screen, walked and counted

Pictures (1646×900, fresh user, offscreen): `C:\Users\Sam\.rostrum\waves\results\sound-redesign\p26\before\`.
The table is also in `before\clicks.md`. A click = one press (a double-click counts 1, typing a value counts 1);
a screen change = a page switch, a popup or a dialog opening. "Read" = counted from the QML because it can't be
scripted offscreen. Other members were editing the screen while I shot (S26): a few later pictures already show
their fixes (Output as a picker, "Group channel", "Loudest peak").

| Flow (smallest real version) | Clicks today | Screen changes | Where it hurts | After (estimate) |
|---|---|---|---|---|
| A. Song: 2 tracks, 16 notes + 8 hits, repeat 4 bars, a section | ~57 (2 add piano, 16 notes, 2 sound, 2 add drums, 8 hits, **24 to re-enter the repeat: no copy / duplicate / multi-select**, 3 section) | 2–4 (Instruments ↔ Timeline to see the sound; Song popup) | Piano roll of one track fills the middle, the song (arrangement) is a strip at the bottom (`01-timeline.png`); note length only by typing (no edge drag); new song's inspector shows master jargon (`03-new.png`) | ~31 (box-select + Ctrl+D replaces 24 → 2) , 0 page changes |
| B. Score to picture: load video, 3 hit markers, tempo to land bar 5 | ~10 + **blocked**: no way to add a marker on screen (`marker.add` needs a name; not in Ctrl+K either) | 3 popups (Picture, project list, Song popup) | Markers come only from 2D or scripts; Song popup covers the roll (`picture-02-song-popup.png`); picture corner shoots black offscreen (Read) | ~9, markers with M |
| C. Voice-over: record, cut a fluff, clean, normalise, podcast deliver | ~16 + **blocked**: no split, no trim by dragging, no normalise | 2 (Take panel, Mix page for loudness / delivery) | Empty piano-roll area shows "Nothing on this track yet" (`voice-03-recording.png`); clean-up only one clip at a time; loudness only on Mix | ~12, 0 page changes |
| C'. Voice track (spoken lines) | **blocked**: no way to add a line (card text: "add one with line.add", `voice-04-voice-track.png`) | — | Jargon to a person; lines only on the Instruments card | 2 (select voice track, Add line) |
| D. SFX for motion: a whoosh + impact on two markers | **blocked**: Library panel is built but never shown (`soundLibrary` not wired, `sfx-01-library.png`); designed sounds (`sound.add`) have no screen | — | The only way is a script / agent | ~6 |
| E. Mix: 3 faders, group the drums + 2 tracks, 2 effects, streaming target, WAV + stems | ~18 (1 page, 3 drags, **group: 1 + 3 × 3 = 10 (empty "+ Bus" then route each)**, 4 effects, 2 target, 1 render) | 1 page + 3 pickers | Delivery crammed into the master strip: with Normalize on, **Render is cut off** under the Listen pane (`mix-01-deliver.png`); "+ Duck" on every strip; jargon (LUFS-S, dBTP, pk, Glue) partly fixed in S26 | ~11 (group: 3 + 1) |
| F. Agent + person | 1 to see history | 0 | Works: one document, one history. Missing: the person can't hand a *selection* to the agent (single selection only; Ctrl+K gets one id) | same, with multi-select |
| Bus from 3 tracks (select-first check) | 10 | 3 pickers | Empty container first | 4 (click, Ctrl-click ×2, "Send to a new group") |

What the pictures show at a glance:
- **Instruments page** (`00-instruments.png`, `song-04-instruments.png`): each track's settings twice (card + inspector), two-thirds of the page empty.
- **Timeline page** (`01-timeline.png`): the piano roll of one track takes the main area; the arrangement — the whole song — is squeezed into the bottom third; "Auto" chips sat on top of the notes (S26 has since moved them to the track header).
- **Mix page** (`02-mix.png`, `mix-01-deliver.png`): the master strip holds fader, normalise, target, loudness curve, pass line, format, rate, trim and Render; the Listen pictures push Render off.
- **New song** (`03-new.png`): the inspector shows the master (Glue, true peak ceiling, track reverb space) before there is anything to mix.
- **Ctrl+K** (`song-05-ctrlk-note.png`): good: only what applies. Missing because selection is one item only.

---

## 4. The structure — decided from the flows

### One workspace, no pages (like 2D)

```
┌ top bar: File · song name · ▶ ● (record shows when a track is armed) · bar.beat / time · tempo · key · loudness · changes · Ctrl+K ┐
├ Sounds (left, opened by L / "+ Track") ┬ ARRANGEMENT (centre, always)                      ┬ Inspector (right) ┤
│  instruments · my library ·           │  ruler: bars + seconds, sections, markers, picture │  the selection,  │
│  designed sounds; audition; place     │  track headers (name, M S, Rec when armed)         │  essentials then │
│  on the selected track at playhead    │  lanes: notes as mini-roll, hits, clips, sounds    │  folded groups   │
│                                       │  [context bar floats here for the selection]       │                  │
│                                       ├────────────────────────────────────────────────────┤                  │
│                                       │ BOTTOM DOCK (one at a time): Editor (E) · Mixer (X) │                  │
│                                       │ Editor = the selection's detail: piano roll / drum │                  │
│                                       │ grid / clip waveform + clean-up / voice lines      │                  │
└───────────────────────────────────────┴────────────────────────────────────────────────────┴──────────────────┘
Picture: a floating, resizable panel over the arrangement's top-right, only while a picture is set.
Deliver: its own dialog (File › Deliver…, Ctrl+Shift+E, and a "Deliver" button in the top bar).
```

| Decision | Why (3E) |
|---|---|
| **1. Arrangement always in the centre; no Instruments / Timeline / Mix pages.** | *Effective:* the song is the arrangement; every job (A–F) starts and ends there. *Efficient:* page switches drop to 0 (today 1–4 per flow). *Easy:* one place to look, like GarageBand. Same decision as 2D. |
| **2. Bottom dock shows the Editor *or* the Mixer, one key each (E, X), and folds away.** The Editor opens by itself when you double-click notes / a clip, and follows the selection's track. | *Efficient:* the detail opens where your eye already is, below the bar it belongs to (Logic/GarageBand). *Easy:* the piano roll is a detail of a selection, not the main view. Mixer one key away instead of a page. |
| **3. The Instruments page goes.** A track's sound is chosen in the **Sounds panel** (left, opened by "+ Track" or L) and shaped in the **inspector** (essentials first, groups folded, search — same as 2D's settings panel). | *Effective:* the cards duplicated the inspector. *Efficient:* adding a track *is* choosing its sound: select the sound, then it becomes a track (select first, never an empty track). *Easy:* one place for "find a sound": instruments, my library, designed sounds (job D was blocked). |
| **4. Delivery is its own dialog**; the master strip keeps fader, meter and loudness only. | *Effective:* target, format, rate, range, stems and Pass/Miss together (Reaper's render dialog). *Easy:* nothing cut off; a once-per-job task doesn't sit in the mixer forever. |
| **5. A compact loudness readout always in the top bar** (now / whole song vs target, green / amber), the full curve in the Mixer. | *Efficient:* jobs C and E check loudness constantly (Hindenburg's always-on meter). |
| **6. Actions live on the selection**: context bar (only while the selection allows something), right-click, Ctrl+K, shortcuts — all four built from the operation list (§1), so nothing is hand-made per panel. | Rule of individuality and select-first; *easy:* the next step appears next to what you selected; *effective:* agents call the same op. |
| **7. Record is a tool**: Rec on a track header arms it; only then the top bar shows ● Record, the input meter and Take. | Individuality; job C needs it, A–B rarely. Today's behaviour, kept. |
| **8. Picture is a tool panel**: appears with a picture, floats over the arrangement (movable, resizable), its markers on the ruler; **M adds a marker at the playhead** (name asked inline). | Job B blocked today without markers; the picture shouldn't eat a fixed area when there is none. |
| **9. Plain words everywhere**: Loudness (not LUFS-S), Loudest peak (not dBTP), Peak, Group channel (not bus), Squeeze (Glue), Output as a picker. Units shown small after numbers. | *Easy* — Sam's plain-language rule. Partly done in S26. |
| **10. A new song's inspector shows nothing but a hint** until something is selected (today: master settings). Master is selected by clicking its row / strip. | Individuality: master jargon is noise at step 1 of job A. |

What appears when:

| Always | With a selection | With a tool | One click / key away |
|---|---|---|---|
| Top bar (transport, position, tempo, key, loudness readout, changes, Ctrl+K); arrangement; inspector (empty hint when nothing selected) | Inspector fields of it; context bar actions; Editor content (notes → piano roll, hits → drum grid, clip → waveform + clean-up, voice line → script); velocity strip with notes | Armed track → Record cluster + Take; picture loaded → Picture panel + its markers; automation lane open → lane under its track | Mixer (X), Editor (E), Sounds (L), Deliver dialog, Song popup (tempo / key / sections), Settings, File |

---

## 5. The basics a person expects

| Basic | Expected behaviour | Today (read from the QML / bridge) |
|---|---|---|
| Click select | Click a note / clip / hit / sound / line / track selects it; click empty deselects | **Exists**, single item (kit `bridge.select(id)`) |
| Shift / Ctrl multi-select | Ctrl-click adds/removes one; Shift-click adds the run between (same track / lane) | **Missing** — needs the kit's selection to be a list (§6) |
| Box select | Drag on empty space in the editor or a lane draws a box; Shift adds | **Missing** (empty drag does nothing / moves the playhead) |
| Range select | Drag on the ruler = time range (loop / bounce / export / section); Shift = also restrict to selected tracks | **Partly**: ruler drag is used for punch-in only |
| Select all / in range | Ctrl+A: all on the focused track (editor) or all tracks' items in the range | **Missing** |
| Copy / Cut / Paste | Ctrl+C / X / V: paste at the playhead on the selected track, times kept relative | **Missing** |
| Duplicate | Ctrl+D: right after the selection | **Missing** |
| Nudge | ←/→ one grid step (Shift: a bar; Alt: free 10 ms); ↑/↓ a semitone for notes (Shift: octave) | **Missing** |
| Drag move | Moves the selection together; snaps to the grid / markers, Shift free; one undo step | **Exists** for one item (`doc.gesture`, quarter-beat snap) |
| Drag ends | Drag a note's / clip's right edge = length; a clip's left edge = trim (`in`); clip top corners = fades | **Missing** (lengths and fades only by typing) |
| Velocity | Velocity strip under the piano roll; drag a bar, or drag over several | **Missing** (inspector number) |
| Zoom / scroll | Ctrl+wheel / pinch zooms at the pointer; Shift+wheel scrolls in time; Ctrl+0 fits; Z zooms to the selection | **Exists** (not Z) |
| Right-click menu | On any item / track / range: the selection's actions, from the operation list | **Missing** everywhere |
| Undo | Every gesture (a whole drag, a whole box-move, a paste) = one step; Ctrl+Z / Ctrl+Shift+Z | **Exists** (kit) |
| Feel of drags | Follows the pointer at screen rate (no wait for the engine; render after release), no jump on press (grab offset kept), snap shown as a line | **Exists** for moves (render debounced ~300 ms); check that a long song's drag stays smooth after P25 |
| Play from here | Space plays / stops; click on the ruler moves the playhead; Enter back to start | Space **exists**; Enter **missing** |
| Loop | C or drag on the ruler top → loop range; Space plays it | **Missing** |

Shortcuts (proposed; the kit's AppShell owns Ctrl+K / Ctrl+Z / redo, the rest are Sound's):

| Key | Does | Key | Does |
|---|---|---|---|
| Space | Play / stop | R | Record (armed track) |
| Enter | Playhead to start | C | Loop the selected range |
| E | Editor dock | X | Mixer dock |
| L | Sounds panel | M | Add marker at the playhead |
| Ctrl+C / X / V | Copy / cut / paste | Ctrl+D | Duplicate |
| Ctrl+A | Select all (focused area) | Delete | Delete selection |
| ← → | Nudge a grid step (Shift: bar) | ↑ ↓ | Notes: semitone (Shift: octave) |
| Q | Quantise selection | Ctrl+T | Split clips at playhead |
| Ctrl+Shift+E | Deliver… | Z | Zoom to selection |

---

## 6. Requests to the shared kit (Team Hem, H28 — exact)

1. **Selection is a list.** `rostrum_gui/bridge.py`: `select(id)` keeps working (replaces); add `selectAlso(id)`
   (toggle one), `selectMany(ids)`, `selectNone()`, a `selection` property (list) beside `selected` (the first
   one, for the inspector's title). `_commands()` already passes a list to `commands.build`: pass the whole list.
2. **Inspector on several items of one type**: show the fields they share; a value that differs shows "—" (mixed);
   setting it calls the op once with all ids. Several types selected: show "3 notes, 1 clip" and only the actions.
3. **A ContextBar component** in RostrumKit: given the command list for the selection (the same `commands.build`
   output), shows the top 3–5 by the op's `importance` as buttons + "More…" (opens Ctrl+K filtered); hidden when the
   list is empty. Each app places it.
4. **A right-click Menu fed by the same command list** (the kit's `Menu` with `entries`), grouped by `importance`.
5. `commands.build`: support ops whose one missing required param is a **number or text** by asking inline (a
   small field in the bar / menu) — needed for `marker.add` (name), `note.transpose` (semitones), `clip.split`
   would default `at` to the playhead the app passes as context.
6. **Timeline**: if H28 makes the kit's timeline the base, Sound needs: lanes of variable height (a track with a
   mini piano roll), box selection on empty space, a ruler range selection (from / to, emitted as screen state),
   and drag handles on item ends (left / right edge).

---

## 7. Open points for the lead

1. **Parts** need a schema field (Team Sam): flagged in §1; the six jobs work without it.
2. **Bounce** and **range export** are jobs, not document ops; they need the engine's render to accept a range
   (`handoff.render` `from` / `to`) — check with whoever owns `handoff.py`.
3. **Voice as words** (Hindenburg / Descript) needs a transcript of recorded clips, analysed once and stored
   (AGENTS rule 7). The ASR models in memory (Parakeet / Omnilingual via sherpa-onnx) were chosen for 2D captions;
   reusing them for Sound is a natural next brief, not part of this redesign.
4. `bus.from_tracks` naming: the screen already says "Group channel"; the op keeps `bus` (the document's word) and
   the label says "Send to a new group".
5. Shot hygiene: `shot.sh` leaves an untitled song per run in its scratch home, so the next `--new` shot opens on
   "RostrumSound closed unexpectedly" (seen in two of my shots). I reshot with my own scratch copy that clears
   `untitled-songs` first (`C:\Users\Sam\.rostrum\waves\scratch\priyam-P26-design\shot.sh`). Either make `--shot`
   remove its untitled song on exit, or have shot.sh clear it.
6. New track colour (S26) shows `#000000` in the inspector while the header bar is teal (`voice-04-voice-track.png`):
   the default should be the colour the screen actually draws.

---

## 8. In docs/PLAN.md

The decisions above are recorded in `docs/PLAN.md` › Decided, "2026-10-22 — RostrumSound's screen and workflow".
