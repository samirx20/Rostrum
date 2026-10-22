# RostrumSound — the UX and interaction spec

*Team Priyam, brief P26, 2026-10-22. Written by four designers in parallel (people, screen, flows and feel ·
making music · audio, voice and picture · mix, delivery and the app) on one shared screen model, one template and one
key map, then put together and settled by the lead. **This is the spec to review before any more screen building.**
The first design round (six jobs walked, today's screen counted with pictures) is kept as Appendix A.*

Sam's ask, word for word: *"think about the user experience and the user interaction. How would a user interact and
achieve the thing he wants, what is the approach that the rule of 3E's satisfies, and apply that for every
interaction. What are all the features needed and how the user will interact, and everything else."*

**3E** — every choice below is judged by it: **effective** (it does the whole job), **efficient** (fewest clicks, no
screen hopping), **easy** (you see what to do next without being taught).

**How to read a feature (§3).** Each one has the same parts, in this order: **Goal** (in the person's words) ·
**Who / when** (jobs A–H) · **How it works** (the clicks, drags and keys; where each control lives and when it
appears) · **Feedback** · **Undo and adjust** · **Keys** · **Agent** (the same action as an operation or MCP tool;
**(new)** = to build, **(new, schema)** = a new field in the song file, Team Sam's) · **Why this way (3E)** and what
was **Rejected** · **Studied** (Logic, Ableton, GarageBand, Reaper, Hindenburg, Descript: what we take, what we don't)
· **Later** · **Today** (what exists now; collected in the gap table, §7).

Contents: 0 Decisions in short · Words · 1 People and jobs · 2 The screen (regions, what appears when, dialogs, window
sizes, wireframes) · 3 Features (3.0 the grammar, 3.1–3.23) · 4 Flows with click counts · 5 Feel · 6 Key map ·
7 Gap table against today · 8 What it needs (operations, song-file fields, engine, shared kit) · 9 Later ·
10 Open points, settled · Appendix A Today's screen, counted (first round).

---

## 0. Decisions in short

The structure (decided in the first round, refined here):
1. **One workspace, no pages.** The arrangement (every track over time, sections and markers on the ruler) is always
   in the middle. Below it, one dock shows either the **Editor** (E: the selection's detail — piano roll, drum grid,
   clip waveform with clean-up, voice lines) or the **Mixer** (X), and folds away. The Instruments, Timeline and Mix
   pages go.
2. **Select first, then act.** Every action works on what is selected (tracks, notes, hits, clips, sounds, lines,
   markers, sections, a time range, automation points) and is **one operation taking those ids**, so a person and an
   agent call the same thing and it is one undo step. The actions appear in the **action bar** next to the selection
   (only while something applies), in the right-click menu, in Ctrl+K and as keys — all from one list. Never an empty
   container first.
3. **Adding a track is choosing a sound.** The **Sounds panel** (L, or + Add › Track) holds instruments, drum kits,
   voices, the microphone, the person's own library and designed sounds; picking one makes the track or places the
   sound. A track's settings live once, in the settings panel.
4. **With nothing selected, the settings panel shows the song** (name, tempo, beats per bar, key, length), as in 2D.
   The Song popup that covered the notes goes.
5. **Deliver is its own dialog**; a small **loudness readout** against the target sits in the top bar once the song
   makes a sound. The master strip keeps only fader, meter and loudness.
6. **Tools appear when used:** Record once a track is armed; the Picture panel once a picture is set; automation lanes
   under their track (A); the Editor tool (Select V / Draw B) only in the Editor.
7. **Groups are one thing:** a group (the song file calls it a bus) that tracks play into, drawn as a header with its
   tracks indented under it, which also folds for tidiness. Select tracks → Ctrl+G. No separate "folders".
8. **Handles on items, not modes:** a clip's edges trim, its top corners fade, its bottom-right corner stretches, its
   level line sets volume; a note's right end sets length. Dragging: **Ctrl = no snapping, Alt = drag a copy, Shift =
   only in time** — 2D's meanings.
9. **Things that take time are made when you let go, not by a button:** a cleaned take is made when you release the
   clean-up slider, speech when you finish typing a line — once, kept, and reused (rule 7); one job at a time, newest
   wins, with progress on the item and Esc to cancel.
10. **Plain words on screen, the technical word on hover:** Loudness (LUFS), Loudest peak (true peak, dBTP), Group
    (bus), Duck (sidechain), Plays into (output).
11. **Fail loudly, in one sentence:** a missing plug-in stops play and delivery until it is switched off (one click);
    a marker deleted in 2D raises a problem chip with choices; nothing is silently converted.
12. **The agent sees what the person sees:** "the selection" is ids (`inspect_selection`, new); agent changes flash
    briefly, never move the person's view, and fold into one history row with Keep / Undo all.

Settled between the four parts (where they differed):
- **Home** always moves the playhead to the start; **Enter** confirms or does the obvious thing for what has focus
  (add a line on a voice track, place the sound picked in the Sounds panel). Enter no longer means "to start".
- **Mute / solo the selected tracks:** Shift+M / Shift+S (M is the marker key). **Next / previous marker:** Alt+M /
  Alt+Shift+M.
- **Pitch by keys:** ↑ / ↓ move notes a half step (Shift: an octave) and move clips to the track above / below;
  **Ctrl+↑ / Ctrl+↓** change pitch the other way round (notes: a scale step in the key; clips: "pitch only" by a half
  step). Alt+arrows stay unused (2D uses them for drawn frames).
- **Hear the original while cleaning:** hold **H** (B is the Draw tool, as in 2D). **T** steps through takes, **S**
  opens Swap on a placed sound, **P** is kept for "make a part" when parts arrive.
- **Track order:** Ctrl+] / Ctrl+[ (2D's "order"), not Alt+↑/↓.
- **Help:** F1 (Help lists every key). Ctrl+H opens History. Ctrl+B is kept for Bounce (later).

---

## Words used in this spec

Said once, in plain language; the screen uses the plain word and gives the technical one on hover.

- **Track**: one row of the song; it plays one instrument, or holds recordings or spoken lines.
- **Note**: one pitch held for a time. **Velocity**: how hard a note or drum hit is played (soft … loud).
- **Hit**: one drum stroke. **Clip**: a piece of a sound file placed on a track. **Designed sound**: a whoosh,
  impact, riser or click made by Rostrum from settings, not a recording. **Line**: one spoken line on a voice track.
- **Bar / beat**: a bar is one count of "1-2-3-4" in a 4/4 song; each count is a beat. **Tempo**: beats per minute.
- **Quantise**: move notes onto the nearest grid line. **Key / scale**: the set of notes a song uses (D minor).
- **Group** (the song file calls it a **bus**): a channel several tracks play into before the master, so they share
  one fader and one set of effects. **Send**: some of a track's sound copied to a group (a shared reverb).
- **Effect**: something that changes a sound on its way through; a **chain** is one track's effects in order.
  **Plug-in**: an effect or instrument from another company (CLAP or VST3), with its own window.
- **Duck** (sidechain): a track dips by itself while others sound (music under a voice).
- **Automation**: a setting that changes over time by itself, drawn as points in a **lane** under its track.
- **Loudness** (LUFS): how loud the song feels on average — what streaming sites and TV measure. **Loudest peak**
  (true peak, dBTP): the highest point the wave reaches once played back. **Peak**: a strip meter's highest level.
- **Stem**: one part of the mix as its own file (the drums alone). **Bounce**: turn tracks into one recording.
- **Marker**: a named moment ("logo lands"). **Shared** markers belong to the project and are the same in 2D and
  Sound; a song's own markers belong to the song.
- **SFZ**: a free file format for sampled instruments. **CLAP / VST3**: the two plug-in formats.

---

## 1. Who comes to Sound, and for which jobs

### The people

| Person | What they want from Sound | How often | What they already know | What that means for the screen |
|---|---|---|---|---|
| **Motion designer** (the main 2D user) | Music and sound effects that hit the moments of a 2D film: the logo lands, the card slides, the drop | Every project, a short session (30–90 min) at the end of the animation | After Effects, Premiere, maybe GarageBand. Knows "timeline", "keyframe", "marker". Doesn't know "bus", "LUFS", "sidechain" | The project's markers are on the ruler from the first second; sounds are placed *on* a marker; designed sounds (whoosh, impact, riser) are one search away; loudness is a word and a colour, not a unit |
| **Video maker doing a voice-over** | Record their voice, cut the mistakes, make it clean and even, deliver at the right loudness | Weekly; the same steps every time | Premiere / CapCut / Descript, a USB mic. Knows "cut", "fade". Thinks "too quiet", not "−18 dB" | Recording is one key once a mic track exists; the take appears as you speak; clean-up and "even out" act on the selection; Deliver offers "Podcast" and "YouTube" by name |
| **Musician writing a score or a song** | Write parts with instruments, build the song, mix it | Long sessions, many times a week | GarageBand / Logic / Ableton. Knows piano roll, quantise, tempo, bars, often a MIDI keyboard | The arrangement and piano roll behave like GarageBand/Logic (E opens the editor below, same keys where we can); nothing taught that they already know |
| **An agent** working for any of them | Do the job through MCP: write parts, place sounds, mix, deliver; check by "ears" tools | Any time, often while a person watches | Every operation by name; the guides in `apps/sound/guides/` | Every action is an operation taking the selected ids; the agent can read what the person selected; its changes show live and never move the person's selection, playhead or scroll (same rule as 2D) |
| **Sam** (the owner) | All of the above, and judging the result by ear | Daily while the app is built | Knows the plan, not mixing jargon | Plain words everywhere; nothing cut off at 1646×900; every step shows what to do next |

Most people who open Sound are **not** musicians: two of the four human kinds have never mixed. So the first screen
and every first try must work with defaults, and every sound word is explained the first time it shows (hover words,
§5).

### The jobs

The six jobs of DESIGN.md §2, plus two I found missing (G, H). Each in two lines.

| Job | What the person does | What "done" looks like |
|---|---|---|
| **A · Write a song** | Pick instruments, write or play notes, build verse/chorus, shape the sounds. | A song they can play through and deliver as a WAV. |
| **B · Score to picture** | Bring in a 2D film or a video, mark the hits, fit the tempo, write music that lands on them. | Music that hits each marker, checked by playing with the picture. |
| **C · Voice-over** | Record (or generate) a voice, cut the fluffs, clean it, even it out. | A clean voice file at podcast or video loudness. |
| **D · Sound for motion** | Find or design whooshes, hits and clicks and place them on the 2D markers. | Effects that stay on their moments even when 2D is re-timed. |
| **E · Mix to delivery** | Balance, group, add effects, duck, hit a loudness target, deliver with stems. | Files that pass the target, plus stems if asked. |
| **F · Agent and person together** | An agent builds; the person watches, tweaks a selection, hands parts back. | One song, one history, nobody's edits wiped. |
| **G · Fix the sound of a recorded video** *(found missing)* | Bring in a video with its own camera sound (an interview, a vlog), clean it, level it, add music under it. | The video's voice is clean and the music ducks under it; delivered back to the project. Common for video makers; today it means splitting the job by hand. |
| **H · Versions for each platform** *(found missing)* | The same piece delivered several ways: a 30 s and a 15 s cut, a loud one for social and a −16 one for podcast. | Several files from one song in one Deliver, each passing its own target. (Short cuts by range need the range render, §9.) |

---

## 2. The screen

One workspace, no pages (DESIGN.md §4, decided). This section fixes every region's content, what appears when,
every dialog, the sizes and the wireframes.

### 2.1 Changes to DESIGN.md §4, with reasons

| Change | Why (3E) |
|---|---|
| **Undo and Redo buttons and "what just happened" sit in the top bar**, beside the change count, exactly as in 2D. | *Easy:* a person new to Sound sees that every step can be taken back; *family:* 2D's top bar has the same three things in the same order. |
| **"+ Add" in the top bar** (a short menu: *Track with a sound… L* · *Picture to work to…* · *From a file…*), and a **"+ Track" row under the last track** that opens the Sounds panel directly. | *Easy:* 2D's "+ Add" is where new things come from; one place to look in both apps. *Efficient:* "+ Track" sits where the new track will appear. Picture and files are not sounds, so they don't belong inside the Sounds panel. |
| **Recording is chosen in the Sounds panel** ("Microphone" and "Line in" are the first entries under *Record*), and **a voice** ("Voice: Maya" …) is chosen there too. | *Effective:* every track starts from what it will sound like, including a mic or a voice (select first: never an empty "audio track" to set up afterwards). *Easy:* one list for "what do I want to hear". |
| **Nothing selected → the settings panel shows the song**: name, tempo, beats per bar, key, length, with the hint "Select a track, a note or a clip to change it here". Master settings stay on the Master row. | *Family:* 2D shows the composition when nothing is selected. *Easy:* tempo, key and length have one home instead of a popup that covers the notes (`picture-02-song-popup.png`). Keeps decision 10 (no master jargon at step 1). |
| **Deliver and the loudness readout appear once the song makes a sound** (absent in an empty song). | Rule of individuality: nothing to deliver or measure yet. |
| **One action bar at a time**, in the area that has focus (arrangement or Editor). Delete, Copy, Paste are never on it (they are keys and in the right-click menu). | *Efficient:* the bar keeps room for the 3–5 actions that matter; *easy:* one bar to read. |

### 2.2 Regions

**Top bar** (always, 44 px high; one row; fixed order, left to right)
- **File** (menu: New, Open, Open recent, Save, Save as, Import a file, Export MIDI, Settings, Connect an AI agent, About, Quit).
- **Song name** with a dot while unsaved (click = rename).
- **What just happened** ("Agent: added 12 notes to Strings") · **N changes** (click = history list) · **↶ ↷**.
- **Transport:** ⏮ (to start, Enter) · ▶ / ■ (Space) · **⟳ loop** (only while a loop range exists; lit when on) ·
  **click** (the metronome, K) · **● Record** and the **input meter** (only while a track is armed).
- **Position:** bar.beat.tick and time ("5.3.1 · 0:09.60"); click to type a place to jump to.
- **Tempo · beats per bar · key** ("♩ 100 · 4/4 · C major"); click = the Song popover (§2.4).
- **Loudness readout** (once the song makes a sound): "Loudness −15.2 · target −14", a green dot inside ±1 of the
  target, amber outside (never red: it is not an error). Click = opens the Mixer with its loudness curve.
- **+ Add** · **Deliver** (once there is sound; Ctrl+Shift+E) · **Search or run a command** (Ctrl+K) · **?** Help.

**Sounds panel** (left, one click away: L, "+ Track", "+ Add › Track with a sound…"; 260 px)
- Search box (focused on open) and kind chips: *All · Instruments · Drums · Record · Voice · Designed · My sounds*.
- A list of entries, each with a ▶ to hear it and a short plain description ("Warm pad, slow start").
- Click = hear it; **double-click, Enter or drag** = use it: with no track selected (or a track of another kind
  selected) it makes **a new track with that sound**; with a matching track selected it **places it there at the
  playhead** (sounds, recordings from the library) or **changes that track's instrument** (asks first: "Change
  Piano to Strings? The notes stay." — one undo step either way).
- Bottom line: "From a file…" and "Add a folder of my sounds…".
- Closes with L, ×, or Esc while it has focus. It stays open while you work when the window is wide (pushes the
  arrangement); it floats over the arrangement and closes after each use when the window is narrow (§2.5).

**Arrangement** (centre, always)
- **Ruler** (two lines high): bars on top, seconds below; the **section band** (names as labels you can drag); the
  **marker band** (project markers dashed, Sound's own solid; tied items show a small flag); the loop range and a
  time-range selection as a shaded band; the playhead.
- **Track headers** (left column): colour stripe, name, **M** (mute) **S** (solo), **Rec** on tracks that can record,
  a small level meter while playing; "Auto" (automation lanes, A) on hover or when the track has automation.
  Below the last track: **+ Track**. The **Master** row is last, always.
- **Lanes:** notes as a mini piano roll, drum hits as ticks, clips as waveforms, designed sounds as shaded blocks,
  voice lines as word blocks, automation lanes opened under their track.
- **Action bar** (with a selection that allows actions): floats just under the selection; if the selection is off
  screen it sits at the bottom edge of the arrangement.
- **Picture** (with a tool: only while a picture is set): a floating, resizable panel at the arrangement's top right;
  drag its title to move it, its corner to resize; "−" folds it to its title; "×" removes the picture (one undo step).
- **Header strip of the arrangement** (above the ruler, 28 px): *Grid 1/16 ▾* · *Snap* on/off · zoom −/+ · fit.

**Bottom dock** (one click away; one of two at a time; folds away)
- A tab row: **Editor (E)** · **Mixer (X)** · fold ▾. Drag the top edge to resize; height remembered per tab.
- **Editor** shows the selection's detail, built from what is selected: notes → piano roll with the velocity strip;
  drum hits → drum grid; a clip → its waveform with fades, trim and clean-up; voice lines → the lines as text you can
  edit, with "Speak again"; a designed sound → its shape (length, pitch curve) over its sound. With several tracks
  selected it shows them stacked (a piano roll shows other selected tracks' notes faint, for writing against them).
  Its own header: the track's name (a menu of all tracks), *Grid* and *Snap* (shared with the arrangement), zoom.
- **Mixer**: one strip per track, then groups, then **Master** pinned at the right. A strip: name, colour, effects
  (slots, "+ effect"), sends and ducks (folded, with a count), pan, fader, meter, M S. Master: fader, meter, the
  loudness curve against the target. Selection is shared: clicking a strip selects that track everywhere.

**Settings panel** (right, always, 300 px)
- Title: the selection's name and kind ("Piano · Track", "5 notes", "3 notes, 2 clips").
- **Find a setting** (Ctrl+F). **Essentials** open; other groups folded to their names; settings that don't apply
  now are absent. Several items of one kind: shared settings, a differing value shows "Mixed"; a change sets all.
- Mixed kinds: a line per kind ("3 notes ›", "2 clips ›"): click narrows the selection to that kind.
- Nothing selected: the song (§2.1).

### 2.3 What appears when

| Always | With a selection | With a tool | One click away |
|---|---|---|---|
| Top bar: File, song name, changes ↶ ↷, ⏮ ▶, click, position, tempo/beats/key, + Add, Search, Help | The selection's highlight (accent outline) | **Armed track** → ● Record, input meter, input picker, count-in in the top bar; the track's lane shows the take growing | Sounds panel (L) |
| Arrangement: header strip, ruler with sections and markers, track headers, lanes, + Track, Master row | **Action bar** with the selection's top actions + More | **Picture set** → Picture panel; its markers on the ruler | Editor (E), Mixer (X) |
| Settings panel (song when nothing is selected) | Settings panel: the selection's settings | **Automation open (A)** → lanes under the track, point editing | Deliver dialog (once there is sound) |
| Once there is sound: Deliver, loudness readout | Editor content follows the selection | **Loop range set** → ⟳ in the top bar and the shaded band | Song popover (click tempo/key), Settings (Ctrl+,), history list (click "N changes") |
| | Velocity strip (notes or hits in the Editor) | **A job running** (clean-up, voice, deliver) → progress line on the item and in the top bar's message | Right-click menu, Ctrl+K, + Add menu, File menu, Help |
| | Rename field (F2) on one track / marker / section | **Agent connected** → "Agent" names in the message line and history | Connect an AI agent, About |

### 2.4 Dialogs and popups

Rule for all: a popover closes on Esc or a click outside, and keeps what you changed (every change is already one
undo step). A dialog that starts work (Deliver, model download) has one main button and Cancel; Esc = Cancel.

| What | Opens from | What's in it | How it closes |
|---|---|---|---|
| **Deliver** (dialog, 560×auto) | Top bar Deliver, Ctrl+Shift+E, File › Deliver…, Ctrl+K | Rows of deliveries (one by default): *Target* (Streaming −14 · YouTube −14 · Podcast −16 · Broadcast −23 · Film −27 · None; each with a hover sentence), *File* (WAV / MP3 / FLAC / AAC), *Quality* (48 kHz 24-bit by default; folded), *What* (whole song · loop range · a section), *Stems* (off / each group / each track). Live check per row: "Will pass: −14.1, loudest peak −1.2" or "Will be turned down 2.8 to reach −14". *Where* (song folder; "Also give it to the project" on when the song is in a project). "+ Another version" adds a row (job H). Buttons: **Deliver**, Cancel. | Deliver → the dialog shows progress per row, then "Done · Show file" / "Play it"; Esc or Close. A failure keeps it open with the one-sentence reason on that row. |
| **Song popover** | Click tempo / beats / key in the top bar | Tempo (type, drag, *Tap* button), beats per bar, key (note + major/minor), "Add a tempo change here" (at the playhead), "Add a key change here". Sections are made on the ruler (§3.0), not here. | Esc, click outside |
| **+ Add menu** | Top bar + Add | Track with a sound… (L) · Picture to work to… · From a file… (audio, MIDI, video) | Choosing, Esc |
| **Picture chooser** | + Add › Picture…, Ctrl+K "Set picture" | The project's items that have a render (newest first, thumbnail + name), then "A video file…" | Choosing (Picture panel appears), Esc |
| **Record setup popover** | The input name beside ● Record (only while armed) | Input picker, big level meter with "good level" zone, *Hear myself* (on/off, with "use headphones" hint), *Count-in* (off / 1 bar / 2 bars), *Measure the delay* (plays a sweep; shows the result) | Esc, click outside |
| **Clean-up popover** | Action bar *Clean up* on clips | Voice only · Less noise · Less echo · Split into parts (stems); before/after switch; **Clean** button | Clean starts the job (progress on each clip); Esc |
| **Inline name field** | M (marker), *Make a section*, F2, *Send to a new group* | One text field at the place it names, default text selected ("Marker 3", "Section 2", "Drums + Bass") | Enter keeps, Esc cancels the whole action |
| **Settings** (dialog) | Ctrl+, , File › Settings | Audio device and buffer, input, MIDI devices, the models (downloaded, size, remove), folders of my sounds, theme, keys list (read only) — with Find a setting | Close, Esc |
| **Connect an AI agent** | File › Connect an AI agent…, Ctrl+K | How to connect (copy button for the MCP line), what the agent can do, "Agents can change your song; every change is in the history and can be undone" | Close |
| **Model download question** | First use of voice, clean-up, stems | "Voice needs a 1.2 GB download (Qwen3-TTS, Apache-2.0). Download now?" Download / Not now. Then a progress line in the top bar. | Choosing |
| **Plug-in window** | Double-click a plug-in effect or instrument | The plug-in's own window, our title bar with Bypass and the preset name | Close (settings stay) |
| **Open / Save as** | Ctrl+O, Ctrl+Shift+S, first Ctrl+S | The system file dialog | System |
| **Unsaved changes** | Closing with an unsaved, named song | "Save changes to 'Logo sting'?" Save / Don't save / Cancel (untitled songs are kept automatically and offered back) | Choosing |
| **Missing file** | Opening a song whose recording or video moved | "2 files are missing: take-3.wav, logo.mp4." Find them… / Open anyway (the clips show "missing" and the render fails loudly naming them) | Choosing |
| **Offered back after a crash** (exists, S27) | Next start after a crash | Plain sentence, where the log is, "Open the song as it was" | Choosing |
| **Ctrl+K** | Ctrl+K, the top bar search | Every action valid for the selection first, then every command, every setting ("Edit Tempo"), every sound by name | Running one, Esc |
| **Right-click menu** | Right-click anywhere | §3.0 | Choosing, Esc |
| **Hover words** | Hover 600 ms over any icon or sound word | One plain sentence, and the key | Moving away |

### 2.5 Window sizes

Sizes (px). The arrangement's lanes never get narrower than 520 and the arrangement never lower than the ruler plus
two tracks (160). Things give way in this fixed order and never slide under each other:

1. **Sounds panel** floats over the arrangement instead of pushing it (below 1500 wide) and closes after each use.
2. Top bar: "what just happened" shortens to the change count (hover shows it all).
3. Top bar: the search box becomes its icon ("Ctrl K" on hover).
4. Top bar: position shows bar.beat only (time on hover); the key shows short ("Cm").
5. Song name shortens with "…" (min 80 px).
6. Settings panel 320 → 300 → 260.
7. Track headers 200 → 140 (the small meter goes; M S Rec stay).
8. Mixer strips 84 → 68 wide; strips that don't fit scroll sideways; Master stays pinned.
9. Bottom dock below 240 high: effect slots and sends fold to counts ("3 effects ▸").
10. Below 1280×720 (down to the window's minimum, 1024×600): the settings panel becomes a 40 px strip that opens as
    an overlay; the dock opens over the arrangement instead of beside it.

Never shrink or hide: File, ↶ ↷ and the count, ▶ ⏮, ● Record (when armed), tempo, + Add, Deliver, Help, the Rec / M / S
buttons, the action bar's first action.

| Size | Top bar | Sounds panel | Settings panel | Track headers | Dock default height | Picture default |
|---|---|---|---|---|---|---|
| 1280×720 | steps 2–4 applied | overlay, 260 | 260 | 140 | 300 (of 676) | 256×144 |
| 1366×768 | steps 2–3 | overlay, 260 | 280 | 160 | 320 | 288×162 |
| 1646×900 (Sam) | step 2 when an agent message is long | pushes, 260 | 300 | 180 | 380 | 320×180 |
| 1920×1080 | everything | pushes, 280 | 320 | 200 | 460 | 384×216 |

The look pass checks all four sizes for overlap and cut-off automatically (memory: look-pass-automatic).

### 2.6 Wireframes

Drawn at Sam's 1646×900 unless the title says otherwise. `[ ]` = a button, `▾` = a menu, `●` = record,
`░` = shaded selection, `▓` = selected item.

**W1 · A new, empty song**

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ File  Untitled song   0 changes ↶ ↷   ⏮ ▶ click   1.1.1 · 0:00.0  ♩120 · 4/4 · C major  [+ Add] [Ctrl K] ? │
├──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ Grid 1/16 ▾  Snap ✓                                               − + fit    │ Untitled song · Song        │
│ ┌ 1        2        3        4        5        6        7       8 ─────────┐ │ [ Find a setting  Ctrl F ]  │
│ └ 0s       2s       4s       6s       8s      10s      12s      14s ───────┘ │ Name     Untitled song      │
│                                                                              │ Tempo    120 bpm            │
│                                                                              │ Beats    4 per bar          │
│                    Start with a sound.                                       │ Key      C major            │
│                    [ Add a track ]   or drop a sound, recording or video     │ Length   until the last     │
│                    here. Already have a film? [ Bring in a picture ]         │          sound              │
│                                                                              │                             │
│                                                                              │ Select a track, a note or a │
│ + Track                                                                      │ clip to change it here.     │
│ Master                                                                       │                             │
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────┘
No Deliver, no loudness readout, no dock, no Record: nothing to deliver, measure, edit or record yet.
```

**W2 · Writing notes, the Editor open** (piano track selected, five notes selected)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ File  Sample song •  You: moved 5 notes · 14 changes ↶ ↷  ⏮ ▶ click  5.3.1 · 0:09.6  ♩100 · 4/4 · C major  │
│                                       Loudness −16.8 · target −14 ●  [+ Add] [Deliver] [Ctrl K] ?          │
├──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ Grid 1/16 ▾  Snap ✓                                               − + fit    │ 5 notes                     │
│ │verse                        │chorus                    ▼logo lands         │ [ Find a setting  Ctrl F ]  │
│ 1      2      3      4      5      6      7      8      9                    │ Velocity   Mixed            │
│ ▌Piano   M S  ═ ══ ═ ═══ ═ ══ ═ ═══ ═ ══ ═ ═══                               │ Length     1/4              │
│ ▌Bass    M S  ━━━  ━━━  ━━━  ━━━  ━━━  ━━━                                   │ Pitch      Mixed            │
│ ▌Drums   M S  ' ' ' ' ' ' ' ' ' ' ' ' ' ' ' '                                │ ▸ Timing                    │
│ + Track                                                                      │                             │
│ Master                                                                       │ Piano · Track ›             │
├─ [Editor E] [Mixer X] ───────────────────────────────────────────── ▾ ───────┤                             │
│ Piano ▾   Grid 1/16 ▾  Snap ✓                                                │                             │
│ C5 │                                                                         │                             │
│ B4 │      ▓▓▓▓▓▓                                                             │                             │
│ A4 │  ▓▓▓▓▓▓      ▓▓▓▓▓▓      ░░ bass notes faint ░░                         │                             │
│ G4 │                    ▓▓▓▓▓▓▓▓▓▓                                           │                             │
│ F4 │              ▓▓▓▓▓▓                                                     │                             │
│    │ [ Quantise Q ] [ Transpose ± ] [ Velocity ] [ Duplicate ] [ More ▾ ]    │                             │
│ vel│  ▮   ▮     ▮   ▮       ▮   (velocity strip: drag a bar, or across)      │                             │
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────┘
```

**W3 · Mixing, the Mixer open** (Drums strip selected; at 1646 the strips fit)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ File  Sample song   22 changes ↶ ↷  ⏮ ▶ click  9.1.1 · 0:19.2  ♩100 · 4/4 · C major                        │
│                                  Loudness −13.6 · target −14 ●  [+ Add] [Deliver] [Ctrl K] ?               │
├──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ 1      2      3      4      5      6      7      8      9     10             │ Drums · Track               │
│ ▌Piano   M S  ═ ══ ═ ═══ ═ ══ ═ ═══ ═ ══ ═ ═══                               │ [ Find a setting  Ctrl F ]  │
│ ▌Bass    M S  ━━━  ━━━  ━━━  ━━━  ━━━  ━━━                                   │ Instrument  Drum kit ▾      │
│▓▌Drums   M S  ' ' ' ' ' ' ' ' ' ' ' ' ' ' ' '                                │ Level       −4.0            │
│ ▌Voice   M S  ▁▃▅▃▁   ▂▅▆▃▁    ▁▄▅▂                                          │ Pan         centre          │
│ Master                                                                       │ Plays into  Master ▾        │
│                      [ Send to a new group Ctrl G ] [ Add effect ] [ More ▾ ]│ ▸ Effects (1)               │
├─ [Editor E] [Mixer X] ───────────────────────────────────────────── ▾ ───────┤ ▸ Sends and ducking         │
│  Piano    Bass     Drums▓   Voice   │ Master                                 │ ▸ Sound of the kit          │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐ │ ┌─────────────────────────────────┐    │                             │
│  │+ eff│  │Warm │  │Squee│  │Voice│ │ │ loudness over the song          │    │                             │
│  │     │  │+ eff│  │+ eff│  │+ eff│ │ │ ‾‾‾‾‾‾‾‾‾‾‾‾‾‾ target −14 ‾‾‾‾‾ │    │                             │
│  │ ◜ ◝ │  │ ◜ ◝ │  │ ◜ ◝ │  │ ◜ ◝ │ │ │   ╱╲╱‾‾╲__╱‾‾‾╲                 │    │                             │
│  │ ┃ ▌ │  │ ┃ ▌ │  │ ┃ ▌ │  │ ┃ ▌ │ │ └─────────────────────────────────┘    │                             │
│  │ ┃ ▌ │  │ ┃ ▌ │  │ ┃ ▌ │  │ ┃ ▌ │ │  ┃ ▌▌  Now −13.6  Whole song −14.2     │                             │
│  │ M S │  │ M S │  │ M S │  │ M S │ │  ┃ ▌▌  Loudest peak −1.1               │                             │
│  └─────┘  └─────┘  └─────┘  └─────┘ │                                        │                             │
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────┘
◜ ◝ = pan, ┃ = fader, ▌ = meter. Clicking a strip selects its track in the arrangement too.
```

**W4 · Recording a voice-over** (Voice track armed, recording)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ File  Explainer VO •   3 changes ↶ ↷   ⏮ ■ ● Recording 0:42   Mic: USB mic ▾ ▕████████░░▏ good level       │
│                     1.1.1 · 0:42.1   ♩120 · 4/4 · C major   [+ Add] [Ctrl K] ?                             │
├──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ 0s        10s        20s        30s        40s        50s                    │ Voice · Track (recording)   │
│ ▌Voice  Rec● M S ▁▃▅▆▃▁▂▅▆▅▃▁ ▁▂▄▆▅▃▂▁▂▃▅▆▄▂▁▃▅▆▅▃▂▁▁▃▅▆│ ← the take grows   │ Input      USB mic          │
│ + Track                                                                      │ Hear myself  off            │
│ Master                                                                       │ Count-in   off              │
│                                                                              │                             │
│                                                                              │ Space stops. The take lands │
│                                                                              │ on this track, ready to cut.│
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────┘
While recording, the Editor folds (nothing to edit yet); after Stop the take is selected and the Editor opens on its
waveform with the action bar: [ Clean up ] [ Even out level ] [ Split at playhead Ctrl T ] [ More ▾ ].
Deliver appears once the take exists.
```

**W5 · Scoring with the picture** (a 2D film set as the picture; marker "logo lands" selected)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ File  Launch film score   9 changes ↶ ↷  ⏮ ▶ click  5.1.1 · 0:08.0  ♩120 · 4/4 · D minor                   │
│                                  Loudness −18.0 · target −14 ●  [+ Add] [Deliver] [Ctrl K] ?               │
├──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ Grid 1/8 ▾  Snap ✓                                     ┌ Picture ─── − × ┐   │ logo lands · Marker         │
│ │intro            │build              ┊▼logo lands ┊▼cut│                │   │ (from the project)          │
│ 1        2        3        4        5        6        7 │   [ the frame  │   │ At        0:08.00           │
│ 0s       2s       4s       6s       8s       10s      12│     at 0:08.0 ]│   │ Used by   2 sounds, 1 note  │
│ ▌Strings  M S  ━━━━━━━━━━━━━━━━━━━━━━━━━┓               │                │   │                             │
│ ▌Hits     M S                   ▓ riser ▓┃▓ impact       └───── resize ◢ ┘   │ Moving it in 2D moves them. │
│ + Track                                  ┃                                   │                             │
│ Master                                   ┃                                   │                             │
│        [ Place a sound here ] [ Land a bar here ] [ Rename ] [ More ▾ ]      │                             │
├─ [Editor E] [Mixer X] ───────────────────────────────────────────── ▾ ───────┤                             │
│ (Editor of the last edited track, or folded)                                 │                             │
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────┘
Project markers are dashed (┊), Sound's own are solid. Items tied to a marker show a small flag at their tied edge.
```

**W6 · The Deliver dialog** (two versions: job H)

```
               ┌ Deliver "Launch film score" ─────────────────────────────────────────────── × ┐
               │                                                                               │
               │  1  Target  [ Streaming −14 ▾ ]   File [ WAV ▾ ]   What [ Whole song ▾ ]      │
               │     Stems   [ Off ▾ ]                                                         │
               │     ✓ Will pass: loudness −14.1, loudest peak −1.2                            │
               │                                                                               │
               │  2  Target  [ Podcast −16 ▾ ]     File [ MP3 ▾ ]   What [ Whole song ▾ ]   ×  │
               │     Stems   [ Off ▾ ]                                                         │
               │     Will be turned down 2.0 to reach −16. Loudest peak stays under −1.        │
               │                                                                               │
               │  [ + Another version ]                                                        │
               │  ▸ Quality: 48 kHz, 24-bit                                                    │
               │  Where  C:\Users\Sam\Music\Launch film score\  [ Change… ]                    │
               │  ✓ Also give it to the project (2D's "Launch film" can use it)                │
               │                                                                               │
               │                                                       [ Cancel ] [ Deliver ]  │
               └───────────────────────────────────────────────────────────────────────────────┘
After Deliver: each row shows a progress line, then "Done · [ Play it ] [ Show file ]". A failure keeps the dialog
open and says on its row what failed and what to do ("The voice clip 'take-3' is missing. Find it, then Deliver again.").
```

**W7 · A selection with the action bar and the right-click menu** (three clips on two tracks)

```
┌──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────┐
│ 0s        5s        10s       15s       20s                                  │ 3 clips                     │
│ ▌Voice  Rec M S  ▓▓take 1▓▓  ▓▓take 2▓▓     take 3                           │ [ Find a setting  Ctrl F ]  │
│ ▌Room   Rec M S       ▓▓room tone▓▓▓▓▓                                       │ Level      Mixed            │
│                 [ Clean up ] [ Even out level ] [ Fade ▾ ] [ More ▾ ]        │ Fade in    0.05 s           │
│                       ┌──────────────────────────────────┐                   │ Fade out   Mixed            │
│                       │ Clean up…                        │                   │ ▸ Clean-up                  │
│                       │ Even out level                   │                   │ ▸ Effects on these clips    │
│                       │ Fade in / out ▸                  │                   │                             │
│                       │ Layer as one sound       Ctrl G  │                   │                             │
│                       │ Split at playhead        Ctrl T  │                   │                             │
│                       │ Split into parts (stems)         │                   │                             │
│                       │ Add effect to these ▸            │                   │                             │
│                       ├──────────────────────────────────┤                   │                             │
│                       │ Copy  Ctrl C     Cut  Ctrl X     │                   │                             │
│                       │ Duplicate                Ctrl D  │                   │                             │
│                       │ Delete                   Delete  │                   │                             │
│                       └──────────────────────────────────┘                   │                             │
└──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────┘
"Join" and "Crossfade" are absent: these clips are on two tracks. Select take 1 and take 2 alone and both appear.
```

---

## 3. Features

Every feature uses the grammar of 3.0 (select first, the action bar, right-click, Ctrl+K, one undo step per gesture).

### 3.0 Selection and actions

**Goal.** "I point at the things I mean, then say what to do with them" — for one note or forty, for a clip or a
whole verse, the same way every time.

**Who / when.** Every job, every minute. A (notes, ranges), B (markers, ranges), C (clips), D (sounds, markers),
E (tracks, strips), F (the person's selection is what they hand to the agent).

**How it works.**

1. **What can be selected** — and where it shows (the same item is selected in every place it appears):

   | Kind | Where you click it | Also shows selected in |
   |---|---|---|
   | Track (and group, master) | Track header; Mixer strip | Mixer / arrangement, settings panel |
   | Notes | Arrangement mini-roll; Editor piano roll | both |
   | Drum hits | Arrangement ticks; Editor drum grid | both |
   | Clips (recordings, imported audio) | Arrangement lane; Editor waveform | both |
   | Designed sounds (placed) | Arrangement lane; Editor | both |
   | Voice lines | Arrangement word blocks; Editor text | both |
   | Markers | Marker band on the ruler | Picture panel's time line |
   | Sections | Section band on the ruler | — |
   | A time range | Drag on the ruler (seconds/bars line) | Shaded band over every lane |
   | Automation points | An open automation lane (A) | — |
   | Sounds in the Sounds panel | The panel's list | (panel only: they aren't in the song yet) |

2. **How to select** (one rule set for every place):
   - **Click** an item: selects it alone. **Click empty space**: clears (Esc does too).
   - **Ctrl+click**: adds or removes one item. **Shift+click**: selects everything between the last clicked and this
     one — the run of notes in time on one track, the tracks between two headers, the strips between two strips.
     (Same as 2D's layer list. 2D's canvas uses Shift to add; Sound has no canvas, so no conflict.)
   - **Drag a box** on empty lane space (arrangement or Editor): selects every item it touches; with Ctrl it adds.
     In the arrangement the box can span tracks.
   - **Drag on the ruler**: a **time range** (snaps to the grid). Shift+drag: the range only on the selected tracks.
     A time range and items are separate selections: the range's action bar offers "Select what's inside".
   - **Ctrl+A**: everything of the kind in the focused area — all notes of the Editor's track; in the arrangement,
     all items on the selected tracks (all tracks if none); in the Mixer, all strips.
   - **Double-click** an item: selects it and opens the Editor on it. **Double-click a name** (track, marker,
     section): rename.
   - **Clicking a marker** selects it **and** moves the playhead to it (it sits on the ruler, where a click moves the
     playhead; job D places sounds at the playhead next).
   - **Selecting never changes the song**: it is not an undo step and is not saved.

3. **The action bar** — what it shows for each kind (top actions by importance, the rest in **More ▾**; Delete,
   Copy, Cut, Paste are keys and in the right-click menu, never on the bar). An action that doesn't apply is absent.

   | Selection | Action bar (in order) | In More | Operation (agent) |
   |---|---|---|---|
   | 1 track | Open in Editor (E) · Add effect · Colour | Duplicate track · Move up/down · Record (arm) · Export MIDI | `effect.add`, `track.set {colour}`, `track.duplicate` **(new)**, `track.set {order}` **(new field/op)** |
   | 2+ tracks | **Send to a new group** (Ctrl+G) · Mute · Solo · Colour | Add effect to each · Duplicate · Delete | `bus.from_tracks`, `track.set {mute/solo/colour}` |
   | Tracks in one group | Ungroup (Ctrl+Shift+G) · as for tracks | — | `bus.remove` (routes them back to its output) |
   | Notes | **Quantise** (Q) · Transpose ± · Velocity · Duplicate (Ctrl+D) | Humanise · Select same pitch · Export MIDI | `note.quantize`, `note.transpose`, `note.set {vel}`, `note.duplicate`, `note.humanize` |
   | Drum hits | Quantise (Q) · Velocity · Humanise · Duplicate | Change drum ▸ | `hit.quantize`, `hit.set`, `hit.humanize`, `hit.duplicate` |
   | 1 clip | **Clean up** · Even out level · Split at playhead (Ctrl+T, only when the playhead is inside it) · Fade ▾ | Split into parts (stems) · Add effect to this · Duplicate | `clip.set {isolate…}` + `render_cleanup`, `clip.normalize`, `clip.split`, `clip.set {fadeIn…}`, `clip.split_stems`, `effect.add`, `clip.duplicate` |
   | 2+ clips | Clean up · Even out level · **Join** (Ctrl+J, only when they play one file back to back) · **Crossfade** (only when two touch on one track) | Layer as one sound (Ctrl+G) · Fade · Split at playhead · Duplicate | `clip.join`, `clip.crossfade`, `clip.set {group}` |
   | Designed sounds | Hear · Make another like it · Layer (Ctrl+G) | Duplicate · Effects | `sound.set {seed}`, `sound.duplicate` **(new)**, `sound.set {group}` |
   | Voice lines | Speak again · Voice ▾ · Edit words | Duplicate | `line.set`, `render_voice`, `line.duplicate` **(new)** |
   | 1 marker | **Place a sound here** · Land a bar here · Rename (F2) | Delete marker (Sound's own; a project marker: "Delete from the project", says what is tied to it first) | `marker.set`, `marker.add`, tempo fit **(new: `tempo.fit_bar`)** |
   | 1 section | Duplicate section · Rename · Select what's inside | Delete section (label only) | `section.move`, `section.set`, `section.duplicate` **(new)** |
   | Time range | **Loop** (C) · Make a section · Duplicate (Ctrl+D) · Select what's inside | Deliver this range · Bounce to audio (both later, §9) | screen state; `section.add`; `<kind>.duplicate {by: range length}` |
   | Automation points | Flatten · Duplicate | Curve shape (later) | `automation.set` |
   | Mixed kinds (e.g. notes + clips) | Duplicate · Move to playhead | Only the notes › · Only the clips › | each kind's `.duplicate` / `.move`, one batch |

   The bar starts with a count chip ("5 notes") so you see what you are acting on.

4. **Right-click menu** — the same list as the bar, all of it, grouped by importance, then a line, then Copy · Cut ·
   Paste · Duplicate · Rename (one named item) · Delete, each with its key. Right-click on an **unselected** item first
   selects it alone; on a **selected** item it keeps the selection. On empty space: *Paste here* · *Add a sound
   here…* (opens the Sounds panel with the playhead moved there) · *Add marker here* (M) · *Select all on this track*.
   On the ruler: *Add marker here* · *Loop from here…* · *Make a section from here*. On a track header: the track's
   actions.

5. **Ctrl+K** — the selection's actions first (same list), then every command and setting. Typing filters. The
   palette title says what it will act on ("5 notes").

6. **Copy, cut, paste, duplicate.**
   - Ctrl+C / Ctrl+X: the selected items with their relative times (cut is one undo step).
   - **Ctrl+V: pastes at the playhead on the selected track** (first item's start at the playhead, the rest keep their
     distances). Several tracks were copied: they paste onto the selected track and the ones below it, in order;
     if a track can't hold the kind (notes onto an audio track) the paste fails loudly naming it. Nothing selected:
     onto the tracks they came from.
   - **Ctrl+D: a copy right after the selection's end** (by its span; by the range's length for a time range).
     Times keep their form: beats stay beats, an item tied to a marker stays tied with its offset.
   - **Alt+drag**: drags a copy (as in 2D).

7. **Moving.**
   - **Drag** any selected item: all selected items move together, in time and (notes) in pitch or (clips, sounds)
     to another track of the same kind. It snaps (§5); **Ctrl** while dragging = free; **Shift** while dragging =
     only in time (no pitch / track change), like 2D's Shift for "straight".
   - **Drag an end**: length (notes, clips, sounds); a clip's left end trims its start; a clip's top corners = fades.
     With several selected, every selected item's same end changes by the same amount.
   - **Arrows**: ← → one grid step (Shift: one bar; Ctrl: fine, 10 ms or 1/32 of a beat). ↑ ↓: notes a half step
     (Shift: an octave); clips and sounds to the track above / below. Tracks: Ctrl+] / Ctrl+[ move them down / up in
     the list (2D's "order" keys).
   - **Delete** removes; on a time range inside one clip it cuts that part out and closes the gap on that track
     (voice editing, job C; op **(new: `clip.cut_range`)**); elsewhere a time range's Delete is later (§9).

8. **One undo step per gesture.** A whole drag, a box-move, a paste, a duplicate, an action on 40 notes, a key nudge
   = one step. Holding an arrow down repeats: the run of repeats is one step (ends 500 ms after the key is let go).
   Undo puts the selection back on what the undone step touched, so the next action is on the same things.

**Feedback.** Selected items get the accent outline and a lighter fill at once (one frame). The action bar fades in
next to the selection within 100 ms and moves with it while scrolling; it never covers the selection (it flips above
if there is no room below). The settings panel title changes at once. While dragging, a faint copy stays where the
item was until release; the snap line shows what it caught (§5). After an action, the message line says what
happened ("Quantised 16 notes to 1/16").

**Undo and adjust.** Ctrl+Z / Ctrl+Shift+Z, ↶ ↷ in the top bar, or click any step in the history list. Every action
with an amount (quantise strength, transpose steps, fade length) keeps its last amount as the default next time, and
the settings panel shows the result's values to change afterwards.

**Keys.** Click, Ctrl+click, Shift+click, box, ruler drag, Ctrl+A, Esc · Ctrl+C / X / V / D · Delete · arrows (Shift,
Ctrl) · Alt+drag · Ctrl+] / [ · F2 · Ctrl+K · the per-action keys (Q, Ctrl+G, Ctrl+T, Ctrl+J, C). Full list §6.

**Agent.** Every action is one operation with `target: [ids]` — the table above names them. The selection itself is
screen state; the agent reads it with **`inspect_selection` (new)**: the selected ids with kind, track, start, end
and a one-line description, plus the time range if one is set. The agent never changes the person's selection (2D's
rule); its own changes show live and are named in the message line. Paste for agents = `<kind>.add_many` (exists).

**Why this way (3E).** *Effective:* one grammar covers every kind, and an agent calls the very same operations.
*Efficient:* the next step sits beside what you selected (the bar), and several items take one action (today: one
item at a time; job A's repeat took 24 clicks, now 2). *Easy:* select → see what you can do; nothing greyed; the same
keys as 2D and as the DAWs people know.
**Rejected:** *tool modes* (a pencil tool to add notes, a scissors tool to cut, as in Logic's tool menu): a mode is one
more thing to remember and to forget to switch back; we add with a click on empty space and cut with Ctrl+T or
Delete on a range. *A fixed toolbar of every edit action* (Reaper style): shows things that don't apply. *Separate
selections per panel* (Ableton's arrangement vs clip view): two selections that disagree.

**Studied.** Logic: Shift-click toggles, marquee select, right-click tool menu — we take marquee and the right-click
list, not the tool menu. GarageBand: few actions, all on the region — we take "act on what's selected". Ableton: Ctrl+D
duplicate after the selection, Ctrl+E split — we take Ctrl+D (shared with 2D) but keep Ctrl+T for split (reserved).
Reaper: everything is an action in one list (its Actions window) — the same idea as our one operation list, without
its expert-only surface. Descript: delete a stretch of voice and the gap closes — we take that for clips (Delete on a
range inside a clip).

**Later.** Select same pitch / same velocity ("select similar") beyond the simple version; select by colour; a
selection memory (recall a saved selection); Delete / insert time across all tracks (`range.remove`, `range.insert`).

**Today.** **Partial:** single selection only (kit `bridge.select(id)`); one-item drag moves; Ctrl+K lists what applies
to one item. Missing: multi-select, box, ranges for items, action bar, right-click, clipboard, nudge, end drags. The
operations for move / duplicate / quantise / split / join / crossfade / normalise / transpose / group exist.

---

#### Dragging items and their handles (used by every feature below)

- **Dragging an item:** it snaps to the grid, markers and the playhead (a thin line shows what it snapped to);
  **Ctrl while dragging turns snapping off**; **Alt drag drags a copy**; **Shift drag keeps it on its track** (only
  the time changes). These are 2D's meanings. DESIGN.md's first round said "Shift free" for snapping; it is Ctrl now, so the
  same key means the same thing in both apps.
- **Dropping on a marker ties the item to that marker:** its time is stored as `"#logo"`, and if 2D moves the marker,
  the item moves with it. A tied edge shows a small flag. The arrow keys nudge a tied item and keep the tie
  (`"#logo+0.2"`).
- **Item handles (audio clips and designed sounds).** These appear when the pointer is over the item, or always while
  it is selected:
  - **left / right edge** trims;
  - **top corners** set the fades;
  - **bottom-right corner** stretches the sound to a new length;
  - the **level line** across the clip sets its volume.
  The pointer changes shape over each handle, and a tooltip names it the first three times.
- **One gesture = one undo step.** The step's name says what happened ("Trim clip", "Fade in 0.4 s").

### 3.1 Songs, tracks and parts

#### 3.1a A new song

**Goal.** "Start a new piece and get to the first sound quickly."
**Who / when.** A, B, D at the start of every job; C starts the same way with an audio track. Once per song.
**How it works.**
1. **Ctrl+N** or File › New song. The song opens untitled (saved per change in the untitled area, as today).
2. The arrangement is empty and shows one centred hint with one button: **Add a track** ("Pick a sound to start
   with: an instrument, drums, your voice or a sound file"). The **Sounds panel opens by itself** on a new song,
   with the search field focused.
3. The top bar shows tempo **120**, beats per bar **4/4**, key **"No key"** (a muted chip). Each is one click to change
   (3.6). Length is automatic (last sound + 2 s), so nobody sets it.
4. The settings panel shows only a hint ("Select something to see its settings. Nothing selected: the song") and,
   under it, the song's own essentials: name, tempo, key, beats per bar. Master settings are not shown here (they
   live on the master's row and in the Mixer).
5. Picking a sound in the Sounds panel makes the first track (3.1b). The hint goes away.

**Feedback.** The new empty song appears in under a second; the Sounds panel slides in; the cursor is in its search.
**Undo and adjust.** A new song has an empty history. Tempo / key / metre are edited any time (3.6).
**Keys.** Ctrl+N new · Ctrl+O open · Ctrl+S save (names an untitled song) · Ctrl+Shift+S save a copy · L Sounds panel.
**Agent.** `run_open_project` / the project service makes the document; `doc.set {tempo, beatsPerBar}` (exists);
`key.add {key, at: 0}` (exists). `inspect_project` returns the empty song.
**Why this way (3E).** Effective: the first real step (pick a sound) is the only one asked. Efficient: 2 clicks to a
playable track. Easy: one hint, one button; no master jargon at step 1 (DESIGN §4 decision 10).
**Rejected:** a "new song" wizard (tempo, key, template) — slows the start and leans toward templates (tools, not
taste); a song pre-filled with default tracks — the person deletes what they didn't ask for.
**Studied.** GarageBand opens a project chooser and then a "choose a track type" dialog; Logic asks for a track type
first. We take "the first thing you do is pick a sound"; we skip the dialog and the project templates.
**Later.** A person's own starting song ("open this as new") — File › New from a song… — when people ask; it is a copy, not a shipped template.
**Today.** Partial: File › New song exists; the new song's settings panel shows master settings; the Sounds panel does not exist.

#### 3.1b Adding a track

**Goal.** "I want a piano / drums / my voice / this sound file in the song."
**Who / when.** All jobs, several times per song.
**How it works.** A track is made by choosing what it plays — never an empty track first (select first, then act).
1. **+ Track** (at the bottom of the track headers, always; and in the top bar) or **L** opens the Sounds panel.
2. Find a sound (3.7). Then any one of:
   - **double-click** it or press **Enter**: a new track with that sound, placed **below the selected track** (or last
     when none is selected), selected, its header name in edit mode for an optional rename;
   - **drag it** into the empty space below the last track: a new track there; dragged between two tracks: a new
     track at that place (a blue line shows where).
3. The kind of track follows from what was picked; nobody chooses a "track type":

| Picked | Track kind | Holds | Editor (E) shows | Header icon |
|---|---|---|---|---|
| An instrument (built-in, played, synth, SFZ, plug-in) | Instrument | notes | piano roll (3.3) | keys |
| A drum kit | Drums | hits | drum grid (3.4) | drum |
| A voice | Voice | spoken lines | the lines (another part of this spec) | mouth |
| A sound file, a library sound, or **Audio track** (Sounds panel, top row "Empty audio track — to record into") | Audio | clips and designed sounds | waveform | wave |

4. The empty audio track is the one exception to "no empty track": recording needs a place to land. It is the first
   row of the Sounds panel and also offered on a track header's right-click as "New audio track to record".
5. The new track's name is the sound's name ("Grand piano"); a second one is "Grand piano 2". Its colour is the next
   free colour of the track palette (below), and the inspector shows that same colour (fixes DESIGN §7 point 6).

**Feedback.** The track appears at once with its colour, icon and name; the Editor dock opens on it if it is an
instrument or drum track and the dock was open; the sound plays a short audition when picked (3.7).
**Undo and adjust.** One `track.add` = one undo step (with the clip, when made from a file: one batch). Swap the
sound later without losing notes (3.2c).
**Keys.** L Sounds panel · Enter add the highlighted sound · Esc close the panel.
**Agent.** `track.add {name, instrument, …the form's settings}` (exists; takes the instrument in the same call);
from a file: `track.add {instrument: "none"}` + `clip.add` in one batch (exists). **(new)** `track.add` gains `after`
(a track id) so an agent can place it, same as the screen. Reply: the new track id.
**Why this way (3E).** Effective: the track can play the moment it exists. Efficient: one double-click instead of
add → choose type → choose instrument. Easy: the kind is never a question; the icon tells it afterwards.
**Rejected:** a "track type" dialog (GarageBand, Logic) — a question the person can't answer before knowing the
sound; an empty "+ Track" that adds a default piano (today) — the person then changes it.
**Studied.** Logic's library on the left changes the selected track's patch; Ableton makes a track when you drop an
instrument in empty space. We take drop-to-make and the library on the left; we drop the track-type dialog.
**Later.** Multi-output instruments (a plug-in drum kit with one track per drum output) — rare, needs routing work.
**Today.** Partial: `+ Track` with a fixed menu of 8 kinds (`screensound/adder.py`); no Sounds panel; no `after`.

#### 3.1c Naming, colouring, ordering, deleting tracks

**Goal.** "Keep my tracks tidy: names I understand, colours I can spot, in the order I think."
**Who / when.** All jobs; often in A and E.
**How it works.**
- **Select tracks:** click a header; **Ctrl+click** adds / removes one; **Shift+click** selects the run between.
  Selected headers are highlighted; the settings panel shows the track (or the shared fields of several).
- **Rename:** double-click the name or **F2**; Enter keeps, Esc cancels. Several selected + F2: renames the first,
  then Tab moves to the next.
- **Colour:** the colour strip on the left edge of the header is a button: click → a small palette of 16 swatches +
  "Custom…". With several tracks selected, it colours them all. The palette is a set of clearly different hues, a
  tool for telling tracks apart, not a look.
- **Order:** drag a header up or down by its grip (the left strip); a blue line shows where it lands; several selected
  move together and keep their order. **Ctrl+] / Ctrl+[** moves the selected tracks one place (2D's "order" keys).
- **Duplicate:** **Ctrl+D** with tracks selected: copies with everything on them, placed below each original.
  Right-click also offers **"New track with this sound"** (same instrument and settings, no notes: for doubling a
  part).
- **Delete:** **Delete** with tracks selected. No confirmation: Undo brings it back whole. The action bar shows "Delete
  3 tracks (412 notes)" so the size is visible before the click.
- The action bar for selected tracks shows, most used first: Send to a new group (Ctrl+G), Colour, Mute / Solo,
  Duplicate, Delete; the rest (Add effect…, New track with this sound, Export as MIDI) in "More…" and right-click.

**Feedback.** Rename in place; colour changes the header, lane items and mixer strip at once; drag shows the drop
line and the tracks re-flow on release.
**Undo and adjust.** Each rename, colour change, drag (whole drag) and delete is one undo step.
**Keys.** F2 rename · Ctrl+D duplicate · Delete · Ctrl+] / Ctrl+[ move · Ctrl+A select all tracks (when the
headers have focus).
**Agent.** `track.set {name}` / `{colour}` (exists; colour field landed in S26) · `track.remove` (exists) ·
**(new)** `track.move {after: <track id> | "top"}` (targets keep their order) · **(new)** `track.duplicate {notes:
true|false}` (false = "New track with this sound").
**Why this way (3E).** Effective: every tidy-up a person needs. Efficient: all on the header, no dialog. Easy: the
same gestures as any list on Windows and as 2D's layer list.
**Rejected:** colour by kind automatically and unchangeable — people colour by role ("all the strings blue").
**Studied.** Logic / Reaper: drag headers, colour from a palette, multi-select colours all. Same here; nothing to reject.
**Later.** Track icons chosen by the person (purely cosmetic).
**Today.** Partial: rename and colour through the inspector; no reorder, duplicate or multi-select (needs the kit's selection list, DESIGN §6.1).

#### 3.1d Folders vs groups of tracks — we do one thing: groups that also fold

**Goal.** "These eight drum and percussion tracks belong together: fold them away, and turn them up or down together."
**Who / when.** A and E; songs past ~8 tracks.
**Decision.** Rostrum has **one** concept: the **group** (a group channel, i.e. a bus the selected tracks play into).
A group's header sits above its tracks in the arrangement with a **fold arrow**; folded, its tracks hide behind one
row that shows all their notes and clips faintly. There is no separate "folder" that does not mix.
**Why one, not two.** A group at its default settings (level 1, no effects) sounds exactly like the tracks going
straight to the master, so it costs nothing for tidiness alone. Two look-alike containers (Logic's "folder stack" vs
"summing stack", Reaper's folders that are also buses) are a known source of confusion: people put tracks in a
folder and then wonder why the folder's fader does nothing. One container, one rule: "a group folds, and it is a
fader for everything in it".
**How it works.**
1. Select tracks → **Ctrl+G** (or action bar "Send to a new group"). A group header appears above the first
   selected track; the selected tracks move under it (indented, contiguous), and play into it. Name field opens
   ("Group 1"; type "Drums").
2. Fold / unfold: click the arrow on the group header, or **Alt+click** it to fold / unfold all groups.
3. Add a track to a group: drag its header into the group's indented area; take it out: drag it out (its output
   goes back to where the group plays to).
4. **Ctrl+Shift+G** with a group selected: ungroup — its tracks play where the group played (the master, or a
   parent group), the group's effects are dropped (the action bar says so: "Ungroup (removes 2 effects)"), one step.
5. A group can contain groups (drums inside "Band"); fold state is per person (screen state, not the song).

**Feedback.** The tracks re-flow under the header; the Mixer shows a group strip with the tracks beside it.
**Undo and adjust.** Ctrl+G is one step (`bus.from_tracks`); dragging in / out is one step; ungroup is one step.
**Keys.** Ctrl+G group · Ctrl+Shift+G ungroup · Alt+click arrow: fold all.
**Agent.** `bus.from_tracks {name}` (exists) · moving in / out = `track.set {output: <bus id>}` (exists) ·
**(new)** `bus.ungroup` (targets: buses; sets each track's output to the bus's output, removes the bus). Fold state
is not in the document; agents don't need it.
**Why this way (3E).** Effective: tidiness and mixing in one move. Efficient: one key from a selection. Easy: one kind of container to understand.
**Rejected:** separate folders (above); "+ Bus" then routing each track (today: 10 clicks for 3 tracks).
**Studied.** Logic track stacks (folder vs summing), Reaper folder tracks (always buses), Ableton group tracks (always
buses, foldable). We take Ableton's: a group is always a bus and always folds.
**Later.** Sends from a whole group (works today per track).
**Today.** Partial: `bus.from_tracks` exists; groups show as a separate lane row, tracks are not drawn under them, no fold, no ungroup.

#### 3.1e Parts (a named block of notes you move, repeat and loop as one)

**Goal.** "This 4-bar riff is one thing: I move it, repeat it 4 times, open it, and see 'chorus riff' on the track."
**Who / when.** A constantly (building a song is repeating and arranging blocks); B and D rarely.
**What a person needs from a part.** (1) grab a phrase as one block; (2) repeat it by dragging, without counting;
(3) see its name and its extent on the track; (4) open it in the Editor; (5) change one copy without the others —
and, later, sometimes all copies at once.

**Decision — in the document: a `part` name on notes and hits (new, schema, Team Sam).** Exactly like the `group`
name that layers clips (`ops_group.py`): notes and hits carry an optional `part: "chorus riff"`. There is **no
separate list of parts** that could disagree with the notes. A part's **extent** is derived: from the bar line at or
before its first note to the bar line at or after its last note's end (if the whole part is shorter than a bar: the
beat lines). A copy gets its own name ("chorus riff 2"), so changing one copy never changes another.
- Ops (all **new**): `part.make {name}` on selected notes / hits (one track) · `part.rename {name}` (targets: one
  note of the part, or the part name + track) · `part.dissolve` (removes the name, notes stay) ·
  `note.duplicate` / `hit.duplicate` gain **`times`** (n copies back to back) — copies of a part get the next free name.
- A note inside a part still has its own `at` (seconds, beats or a marker), so ties to markers keep working.

**How it looks and behaves (with parts).**
1. In the arrangement, a part is drawn as a **rounded block** across its extent on its track lane, tinted the track's
   colour, name at top-left, its notes drawn inside as a mini roll. Notes not in any part are drawn as today (loose).
2. **Make a part:** select notes (in the Editor or by box on the lane) → action bar **"Make a part"** (proposed key
   **P**) → name field inline (default "Part 1"). Also: drag across an empty bar range on a lane with nothing
   selected, then "Make a part" from the action bar takes every note in that range.
3. **Click** a part = selects all its notes (the selection is still notes: every note action works on it).
   **Double-click** = opens the Editor (E) on that track, zoomed to the part.
4. **Drag** the block body = move all its notes (snaps to bars; Ctrl free). **Alt+drag** = copy.
5. **Repeat:** hovering the block's **top-right corner** shows a loop handle (a circular arrow). Drag it right: each
   time the pointer passes another full extent, a ghost copy appears; release = that many copies, one undo step.
6. **Ctrl+D** = one copy right after. **Rename:** double-click the name or F2.
7. Notes added in the Editor between a part's start and end on its track join the part (it's where they visibly are);
   notes added outside stay loose.

**Interim behaviour (until Team Sam lands `part`).** Everything except the name works on a **range selection on a
track**: drag across empty space on a lane selects the notes / hits in that bar range and draws the same block
outline around the selection (unnamed, gone when deselected). Drag moves it, Ctrl+drag copies, the loop handle
repeats it (`note.duplicate {times}` — the `times` param is ours, not a schema change), Ctrl+D duplicates. So the
gestures people learn now are the same ones parts will use.

**Feedback.** Ghost copies while dragging the loop handle with a count ("× 4"); the name on every block.
**Undo and adjust.** Make / move / repeat / rename = one step each. Dissolve to get loose notes back.
**Keys.** P make a part (proposed) · Ctrl+D duplicate · F2 rename · Delete deletes the part's notes.
**Agent.** As listed; `inspect_project` reports parts per track as `{name, from, to, notes: n}` (derived) **(new)**.
**Why this way (3E).** Effective: covers grab / repeat / name / open. Efficient: repeat by one drag, no counting.
Easy: a block you can see, like every music app. And: one source of truth (the notes), no second list.
**Rejected:** a `parts[]` list on the track with notes inside (Logic regions / Ableton clips) — two places hold
timing, an agent's note edit could fall outside its region, and moving a note between regions is a hidden operation;
**linked copies** (edit one, all change: Ableton's linked clips, Logic aliases) now — useful but invisible links
confuse; it can come later as a `part` option, because copies already know they came from one name.
**Studied.** Logic regions (loop by dragging the corner), GarageBand (same), Ableton clips (a separate container
that loops its contents). We take the corner loop drag and the named block; we reject the separate container.
**Later.** Linked copies ("edit all copies"); parts on audio clips (the clip `group` already does layering).
**Today.** Missing. Range-on-a-track selection is also missing (needs the kit's box selection, DESIGN §6.6).

---

### 3.2 Instruments

#### 3.2a The kinds of instrument, in plain words

| Shown as | What it is | In the document (`instrument` =) | Its essentials (settings panel, top) |
|---|---|---|---|
| **Built-in sounds** | Ten ready instruments that ship with Rostrum (felt piano, grand piano, warm pad, strings, choir, brass, sub bass, marimba …) | `builtIn` | Sound |
| **Played instruments** | Instruments simulated as they are played: guitar, nylon guitar, marimba, vibraphone, glockenspiel, tubular bell, violin | `model` | Model, where it's struck / plucked, damping (strings) |
| **Synth** | A simple synthesiser: a wave shaped by attack, brightness, release | `synth` | Wave, attack, brightness |
| **Sampled (SFZ)** | An SFZ file from your folders or a free library | `sfz` | File, legato, swell, other playing styles |
| **Plug-in instruments** | CLAP / VST3 instruments installed on the computer | `plugin` | "Open plug-in window", its changed settings |
| **Drum kits** | The synth kit, or an SFZ kit | `kit` / `kitSfz` | Kit (3.4) |
| **Voices** | Text to speech: lines spoken by a chosen voice | `voice` | Voice, language, how it speaks (style) |

#### 3.2b Choosing and auditioning an instrument

**Goal.** "Which pad sounds right *for this part*?"
**Who / when.** A every song, several times; B often.
**How it works.**
1. Select the track (click its header), then **L**. The Sounds panel opens filtered to what this track can play (an
   instrument track: instruments; a drum track: kits; a voice track: voices). A small line at the top says "Trying
   sounds on **Pad**"; "Show everything" removes the filter.
2. **Click** a sound (or move with **↑ / ↓**): Rostrum **plays this track's own notes with that sound** — the loop
   range if one is set, otherwise 4 bars from the playhead — looping while you browse. Nothing is written yet; the
   track header shows the sound's name in italics ("trying").
3. **Enter** or **double-click** keeps it (one change). **Esc**, or clicking another track, puts the old sound back.
4. With **no track selected**, or a track with no notes yet, the audition is neutral: one held middle C, then the same
   note soft and loud (instrument); one hit per drum (kit); one sentence (voice: "This is how this voice sounds",
   in the chosen language). With a MIDI keyboard connected, playing keys plays the highlighted sound.
5. Auditions play through the engine (the same render path as playback and export).

**Feedback.** Sound within ~300 ms of the click (built-ins, synth, played); SFZ shows "Loading 120 MB…" on its row
the first time, then plays; a plug-in may take a few seconds (row shows "Loading plug-in…"). A voice that needs its
model first asks the model download question (shared dialog: size and licence).
**Undo and adjust.** Trying is not a change. Keeping is one `track.set {instrument, …}` step.
**Keys.** L · ↑/↓ try next / previous · Enter keep · Esc put back.
**Agent.** `inspect_instrument` (exists: what an instrument is and can play), `inspect_plugins` (exists),
`inspect_library kind="instruments"` (exists); keep = `track.set {instrument, builtIn | model | synth | sfz | plugin
| kit | kitSfz | voice}` (exists). An agent "hears" by `render_mix` + `look_*` tools; **(new)** `render_audition {track,
instrument…, from, to}`: renders the track's notes with another instrument without changing the song, returns the
file, so an agent can compare like a person does.
**Why this way (3E).** Effective: you judge a sound on your own part, not on a demo. Efficient: browse with arrows,
hear at once, one key to keep. Easy: nothing changes until you say so; Esc is always safe.
**Rejected:** a separate demo phrase per instrument (shipped "looks" — and misleading on your part); swapping on
every click with undo as the way back (Logic does this: history fills with tries).
**Studied.** Logic's library swaps the selected track's patch on each click; GarageBand the same. Ableton's browser
previews a short demo. We take "on your track"; we reject writing each try into the history.
**Later.** A/B: pin two tries and flip between them with one key.
**Today.** Partial: the instrument is chosen from a picker on an Instruments-page card or the inspector; no audition on your part; the library audition plays through Qt Multimedia, not the engine (STATUS gap 2).

#### 3.2c Swapping an instrument without losing notes

**Goal.** "Same melody, but on strings instead of piano."
**Who / when.** A often; B sometimes.
**How it works.** As 3.2b: select the track, try, keep. Notes never move: the instrument is a setting of the track,
the notes are separate. What happens to settings:
- Each instrument form's settings stay stored when you switch away (the document keeps every form's value), so
  switching back to the synth brings its old attack and brightness back.
- Note playing settings the new instrument can't use (an articulation, where a string is plucked) stay on the notes,
  are not heard, and are not shown. The settings panel shows one quiet line when that happens: "12 notes have
  playing settings this instrument doesn't use" with **"Remove them"**.
- **Instrument ↔ drum kit:** notes and hits are different things. Dropping a kit on an instrument track is not a
  swap; the panel's filter hides kits there. "Show everything" + double-click a kit makes a new drum track. Turning
  notes into hits (by General MIDI drum numbers) is a right-click action on a note selection: **"Copy to a drum
  track as hits"** **(new)** — rare, so not a swap.

**Feedback.** The track's name follows the instrument only while it still has the old instrument's name (a renamed
track keeps its name). The notes keep playing in the loop.
**Undo and adjust.** One step; undo brings back the old instrument and its settings.
**Keys.** As 3.2b.
**Agent.** `track.set {instrument: …}` (exists). **(new)** `note.to_hits {track}` for the rare conversion.
**Why this way (3E).** Effective: nothing written is lost. Efficient: one key. Easy: you never have to re-enter a part.
**Rejected:** clearing settings on swap (loses a person's shaping silently).
**Studied.** Every DAW keeps MIDI on a patch change; Logic also loses plug-in settings when you change the plug-in slot. We keep each form's settings.
**Later.** Keeping several plug-in states per track (switching between two plug-ins keeps only the last plug-in's state today).
**Today.** Exists in the document (`SWITCHES` keep every form's value); no audition; no "unused settings" line.

#### 3.2d Shaping the sound in the settings panel

**Goal.** "The pad a little softer at the start and darker."
**Who / when.** A often, B and D sometimes.
**How it works.**
1. Select the track. The settings panel shows the track: **Instrument** group first, open; then **Mix** (level, pan,
   output, reverb, tone); everything else folded.
2. Inside Instrument, only the settings this instrument uses, essentials first, from each setting's importance (data,
   never hand-made per panel): e.g. Synth — Wave, Attack, Brightness; then a folded "More" (release, resonance,
   voices, detune); then "Fine detail" (decay, sustain, envelope amount, octave, drive, width, drift, noise, sub).
   Every number shows its unit small ("0.30 s", "2,400 Hz").
3. Change a value by dragging the number left / right, scrolling over it, or typing. **While the song plays (or the
   loop runs) the change is heard on the next render** (~300 ms after you stop dragging).
4. **Ctrl+F** searches every setting of the selection ("bright" finds Brightness).
5. Several tracks selected: shared settings show, differing values show "—", a change sets all.
6. Each setting has a hover hint in plain words (from its `help`: "Attack: how long the sound takes to reach full
   level when a note starts").

**Feedback.** The value updates at once; sound follows after the re-render; the header's instrument name stays.
**Undo and adjust.** One drag = one step; typing = one step.
**Keys.** Ctrl+F find a setting · Tab next field · Esc leave the field.
**Agent.** `track.set {attack, brightness, …}` (exists; the same Params the panel shows). `inspect_instrument`
returns the settings with ranges, units and what applies now.
**Why this way (3E).** Effective: every setting reachable. Efficient: the three that matter most are on top. Easy:
nothing shown that this instrument can't use (rule of individuality).
**Rejected:** a big "synth face" with knobs (looks like gear, hides what matters, can't be built from data); the
Instruments page's cards (removed: they repeated the inspector).
**Studied.** GarageBand shows 4–8 "smart controls" per instrument, full editor behind a button; Logic the same. We
take the few-on-top idea, built from importance.
**Later.** Automating instrument settings over time (STATUS: not automatable yet: "Not: instrument controls").
**Today.** Exists (inspector built from `playing.py` with valid_when and importance); the Instruments page repeats it and goes.

#### 3.2e Plug-in instruments and their windows

**Goal.** "Use the synth I bought, and its own screen."
**Who / when.** A for people with plug-ins; B sometimes.
**How it works.**
1. **Finding plug-ins:** Settings › Plug-ins lists the folders searched (the standard CLAP / VST3 folders, plus
   "+ Add folder"). Rostrum scans once at first start and when a folder changes; a plug-in that fails to load is listed
   with the reason ("crashed while loading", "64-bit only"), never hidden.
2. Plug-in instruments appear in the Sounds panel under **Plug-in instruments** with their maker's name.
3. Choose one like any instrument (3.2b). The settings panel's Instrument group then shows **Open plug-in window**
   (first) and, folded, the settings you have changed (by name, each with its own lane for automation).
4. **Open plug-in window** (or double-click the instrument name on the track header): the plug-in's own window
   floats above Rostrum, titled "Pad — Vital". One window per plug-in; it remembers its place; it stays on top of
   Rostrum while open.
5. Turning a knob in that window is heard live. When you stop touching it for one second (or close the window), the
   plug-in's state is saved into the song as **one change** ("Changed Vital's settings").
6. The plug-in's own presets live in its own window; Rostrum doesn't wrap them.

**Feedback.** The window opens within a second (or "Loading Vital…"); the history gains one line per pause in tweaking.
**Undo and adjust.** Ctrl+Z (with Rostrum focused) restores the plug-in's previous state and its window updates.
**Keys.** None special; Esc in the plug-in window goes to the plug-in.
**Agent.** `inspect_plugins` (exists: installed, with parameter lists); `track.set {instrument: "plugin", plugin:
{format, path, id, params}}` (exists). Agents set parameters by id; they can't see the window.
**Why this way (3E).** Effective: full access to the plug-in. Efficient: one click to its window. Easy: Rostrum's own
undo covers it.
**Rejected:** recording every knob movement as a separate undo step (hundreds of steps).
**Studied.** Every DAW floats the plug-in's window; Reaper records a step per touch; Logic per touch end. We take
"per pause" for a clean history.
**Later.** Plug-in presets in the Sounds panel; MIDI controller lanes to plug-ins (STATUS gap).
**Today.** Partial: plug-ins load and their parameters are automatable (`PluginList.qml`, `PluginSettings.qml`); no plug-in window opener on the new layout; scanning is through `inspect_plugins`.

#### 3.2f Voices (text to speech) as an instrument

**Goal.** "A calm male narrator reading these lines."
**Who / when.** C (instead of recording), D for temp voice, F often.
**How it works.** Pick a voice in the Sounds panel (Voices section; each row is a name + language + a short plain
description). The audition speaks one sentence. The voice track's settings panel shows Voice, Language, **How it
speaks** (a text field: "warm, close to the microphone"). Writing and timing the lines is the voice section (another
part of this spec). Changing the voice re-reads every line (a job with progress; the old audio plays until the new is
ready).
**Feedback.** First use: the model download question (size, licence) → progress → "Downloaded and checked."
**Undo and adjust.** One step per change; the old reading is cached so undo is instant.
**Agent.** `track.add {instrument: "voice", voice, language, style}` (exists), `render_voice` (exists).
**Why this way (3E).** One place to choose any sound, voices included. **Rejected:** a separate "voice" app area.
**Studied.** Descript's voice picker plays a sample per voice; we audition the person's own first line when there is one.
**Later.** A person's own cloned voice (needs a vetted model and consent rules).
**Today.** Exists in the document; the screen shows voices on the Instruments card only.

#### 3.2g Sounds you save yourself

**Goal.** "I spent ten minutes on this bass; I want it in the next song."
**Who / when.** A, occasionally.
**How it works.**
1. Track selected → right-click › **Save as my sound…** (also in Ctrl+K). A small field asks the name ("Round bass").
   A tick box "Include its effects" (on by default when the track has effects).
2. It is saved outside the song, in the person's own sounds folder (`%USERPROFILE%\.rostrum\sounds\Round bass.rsound`),
   and appears at once in the Sounds panel under **My sounds**.
3. Using it is the same as any sound: pick → new track; or on a selected track → try → keep.
4. Right-click a saved sound in the panel: Rename, Delete, Show in folder.

**Feedback.** "Saved to My sounds" toast; the row appears.
**Undo and adjust.** Saving is not a song change (not in the song's history); applying it is one `track.set` (+
`effect.add` per effect) batch. Deleting a saved sound asks once (it is outside undo).
**Agent.** **(new)** `edit_save_sound {track, name, effects: true}` and `inspect_library kind="my-sounds"`; applying
= `track.set` + `effect.add` (exists).
**Why this way (3E).** Effective: reuse your own work. Easy: saved sounds sit beside every other sound.
**Rejected:** shipped presets beyond the instruments themselves ("Epic cinematic pad") — tools, not taste.
**Studied.** Logic / GarageBand "Save patch" into the user library: we take exactly that.
**Later.** Sharing a sound with another person (it's a file already).
**Today.** Missing.

---

### 3.3 Notes and the piano roll

The piano roll is the **Editor** (E) for an instrument track. It opens in the bottom dock when you double-click a part
or a track's lane, or press E with notes or an instrument track selected; it follows the selected track.

Layout, left to right: a **keyboard** (note names on the C keys, plus every row when tall enough; names spelled in the
song's key), the **grid** (rows = pitches, columns = time, the same ruler as the arrangement), and under the grid the
**velocity strip** (one bar per note). A thin **toolbar** at the top of the dock, always: tool (Select / Draw), grid
size, snap on/off, "Show other tracks", "Keep in key", follow playhead, and "Play with keys" (3.5).

#### 3.3a Adding notes: click, draw, play in

**Goal.** "Put these notes in."
**Who / when.** A constantly; B often.
**How it works.** Two tools, the same idea as 2D's Move / Draw:
- **Select tool (V)** — the default in the piano roll. **Double-click** on an empty spot adds one note there (snapped),
  with the **last-used length** (first time: one grid step) and the last-used velocity (first time 0.8).
- **Draw tool (B, proposed — 2D's key for Draw)**. **Click** an empty spot adds a note; **click-drag right** sets its
  length as you drag; **click a note** deletes it; drag a note moves it. The tool is remembered per editor (the drum
  grid starts in Draw, the piano roll in Select).
- **Chords:** with the Draw tool, the toolbar shows **Chord: Off** — choose Triad, Seventh, or **"As selected"**
  (the shape of the notes you last selected). Then one click places that chord with its lowest note at the click,
  built from the key at that time (in D minor a triad on E is E–G–Bb). Each chord note is its own note (selectable).
- **Hear while placing:** each new note sounds once (the track's own instrument).
- **Click a key on the keyboard** to hear that pitch (no note is added).
- **Play in** with a MIDI keyboard or the computer keyboard: 3.5.

**Feedback.** The note appears under the pointer and sounds; its length follows the drag; the bar label shows "D4"
while dragging.
**Undo and adjust.** One note (or one chord, or one drag) = one step.
**Keys.** V Select tool · B Draw tool (proposed) · double-click add (Select).
**Agent.** `note.add` / `note.add_many {notes: [{pitch, at, dur, vel}]}` (exist; `pitch` may be a list = a chord
held as one note). Chords by key: an agent calls `inspect_harmony` (exists) for the key and spells them itself.
**Why this way (3E).** Effective: click, draw and chords. Efficient: Draw for writing many notes, Select for editing.
Easy: double-click adding works in both tools.
**Rejected:** single-click adds in Select (today) — then a click can't deselect, and a stray click writes a note; a
global mode switch with no visible state — the tool is shown in the toolbar and the pointer (pencil).
**Studied.** Logic: pencil tool / Cmd-click adds; Ableton: Draw mode (B) and double-click adds; GarageBand:
Cmd-click. We take Ableton's B + double-click; Logic's chord-from-key idea comes from its Chord Trigger, simplified.
**Later.** Strumming a chord (spread its notes by a few ms) as an action; scale-locked keyboard rows (hide out-of-key rows).
**Today.** Partial: click adds, drag moves (`PianoRoll.qml`); no Draw tool, no chord tool, no hear-on-place.

#### 3.3b Selecting notes

**Goal.** "These ones."
**How it works.**

| Gesture | Selects |
|---|---|
| Click a note | that note (others deselected) |
| Ctrl+click | adds / removes one |
| Shift+click | every note between the last clicked and this one in time (all pitches) |
| Drag on empty space (Select tool) | a box; Shift+drag adds to the selection |
| Click a key on the keyboard **with Ctrl** | every note of that pitch on this track (Ctrl+Shift: adds) |
| Drag on the editor's ruler | every note starting in that time range (shows the range) |
| Ctrl+A | every note on the track |
| Right-click › Select › | Same pitch · Same velocity range · Higher / lower than this · Every 2nd · Top / bottom note of each chord · Out of key |
| Esc or click on empty space | nothing |

**Feedback.** Selected notes are bright with an outline; the velocity strip highlights their bars; the action bar
appears just above the selection ("8 notes · Quantise · Transpose · Make a part · Duplicate · More…"); the settings
panel shows the shared fields ("8 notes": pitch "—", length, velocity).
**Undo and adjust.** Selection is not a change (not in history), as in 2D.
**Keys.** Ctrl+A · Esc · Ctrl/Shift+click.
**Agent.** Agents select by ids: `inspect_project` lists notes; `look_events` and `inspect_harmony` say where they
are. **(new, kit)** `inspect_selection` returns the person's current selection (ids), so a person can hand
"these notes" to an agent (job F).
**Why this way (3E).** Every way people pick notes, the Windows-standard modifiers. **Rejected:** a lasso (box is enough for a grid).
**Studied.** Logic's "Select › Same pitch / Higher pitch / Every 2nd" menu is the model for our Select menu.
**Later.** Selecting across several tracks in one editor (with "Show other tracks" editable).
**Today.** Missing beyond single click (needs the kit's selection list, DESIGN §6.1).

#### 3.3c Moving, copying and lengths

**How it works.**
1. **Drag a selected note**: all selected move together in time and pitch; the grab point stays under the pointer;
   snaps to the grid (and to markers, 3.3f); **Shift** while dragging = free; a tag shows "+1 beat, +3 st".
2. **Ctrl+drag** = copy (the originals stay).
3. **Arrows:** ←/→ one grid step (Shift: a bar; Alt: 10 ms free); ↑/↓ a semitone (Shift: an octave). With **Keep
   in key** on (toolbar), ↑/↓ and vertical drags move by steps of the scale playing there.
4. **Length:** the pointer becomes a ⟷ near a note's **right end** (the last 6 px, or the last third of a short note):
   drag = new length for all selected (each by the same amount). **Left end**: moves the start, keeps the end.
5. **Hold to the next note** (action bar › More, or right-click): each selected note lasts until the next note starts
   (a "legato" line). Written as `dur: "next"`, so it keeps holding when you move the next note.
6. Copy / cut / paste: Ctrl+C / X / V; paste lands at the playhead on the selected track, times relative.
7. **Ctrl+D** duplicates right after the selection.

**Feedback.** Moving notes sound their new pitch once on release (for a single note: while dragging, on each new row).
**Undo and adjust.** A whole drag = one step (`doc.gesture`); arrows: each press one step (held arrow: one step).
**Keys.** arrows · Shift / Alt modifiers · Ctrl+C/X/V · Ctrl+D · Delete.
**Agent.** `note.move {by}` (exists: time) · `note.transpose {semitones}` (exists) — **(new)** param `in_key: true`
· `note.duplicate` (exists) · lengths: `note.set {dur}` (exists) — **(new)** `note.resize {by, end: "right"|"left"}`
for "everything longer by a beat" in one call · `note.set {dur: "next"}` (exists).
**Why this way (3E).** Direct manipulation for every property you can see. **Rejected:** lengths only by typing (today).
**Studied.** Logic / Ableton: drag ends, Alt/Ctrl-drag copy, arrows nudge. Standard; we match it.
**Later.** "Fix overlaps" (trim notes that overlap the next of the same pitch).
**Today.** Partial: one-note drag moves (time and pitch, quarter-beat snap); end drag mentioned in the guide but not for several notes; no arrows, copy/paste, Ctrl+D on screen (ops exist).

#### 3.3d Velocity

**How it works.**
1. The **velocity strip** sits under the grid whenever the piano roll shows (it can be folded to a thin line with its
   own arrow). One vertical bar per note at the note's start, height = velocity; notes in the grid are also shaded by
   velocity (soft = paler).
2. **Drag a bar's top** up / down. If that note is selected, all selected notes change **by the same proportion**
   (relative); **Alt+drag** sets them all to the same value.
3. **Draw a line across the strip** (drag on empty strip space): every note under the line (only the selected ones if
   any are selected) takes the line's height — a crescendo in one gesture.
4. The settings panel shows Velocity for the selection ("—" if mixed); typing sets all.
5. A number shows next to the pointer while dragging ("0.72"); the note sounds at the new velocity on release.

**Undo and adjust.** One drag = one step (one `note.set` batch).
**Agent.** `note.set {vel}` (exists, one value for all targets); **(new)** `note.scale_velocity {by: 0.8 |
from: 0.4, to: 1.0}` for relative and ramp changes in one call (what the drag does).
**Why this way (3E).** Effective: single, group and ramp edits. Efficient: crescendo in one drag. Easy: you see loud vs soft.
**Rejected:** velocity only in the inspector (today).
**Studied.** Logic's velocity lane and Ableton's velocity editor with line drawing — taken.
**Later.** Other lanes in the strip: the note's dynamics, bend, articulation (the fields exist; shown in the settings panel until then).
**Today.** Missing (inspector number only).

#### 3.3e Chords, scale and key highlighting

**How it works.**
- Rows of notes **in the key** playing at that time are slightly lighter; out-of-key rows darker. At a key change the
  shading changes at that time. With "No key", all rows are equal.
- A note **out of key** gets a small dot at its start (not red; out of key is often right). Right-click › Select ›
  Out of key finds them.
- The keyboard names the root ("D") in bold.
- Chord names: above the grid, a thin row shows the chord each bar / beat makes across **all** instrument tracks
  (from `inspect_harmony`), spelled in the key ("Dm", "Bb", "A7"). Shown only when the song has a key.
- **Keep in key** (toolbar) makes ↑/↓, vertical drags and new notes from the Draw tool land on scale notes.

**Agent.** `inspect_harmony` (exists: key, chords per bar, out-of-key notes, range, voicing facts); `key.*` (exists).
**Why this way (3E).** Helps without forbidding: shading and a dot, never a lock. **Rejected:** hiding out-of-key rows by default.
**Studied.** Logic's scale quantise, Ableton 12's scale awareness (rows highlighted, "fold to scale"). We take the
highlight and the in-key movement; fold-to-scale is later.
**Later.** Fold to scale (show only in-key rows).
**Today.** Partial: note names spelled in the key (P12/P13); no row shading, no chord row, no keep-in-key.

#### 3.3f Snapping and the grid

**How it works.**
- **Grid** (toolbar): **Auto** (the default: the grid line spacing follows zoom — bars when zoomed out, 1/16 when
  in), or fixed: Bar, 1/2, 1/4, 1/8, 1/16, 1/32, each also as triplets (1/8T …). The ruler shows the same lines.
- **Snap** (toolbar, magnet, on by default): starts and ends snap to the grid, to **markers** and to section edges,
  whichever is nearest within 8 px; the line it snaps to lights up with its name ("#logo"). **Shift** while dragging
  ignores snapping.
- When a note's start or end snaps to a marker, it is **written on the marker** (`"#logo"` / `{"to": "#logo"}`): it
  follows the marker when 2D or the music moves it (3.3g).

**Agent.** Grid and snap are screen state; agents write times directly (seconds, `{"beat": n}`, `"#marker+0.5"`).
**Why this way.** Auto grid means the first try is right at any zoom. **Rejected:** a fixed 1/4-beat snap (today).
**Studied.** Ableton's adaptive grid; Logic's snap menu. Taken both (Auto by default, fixed on demand).
**Today.** Partial: a fixed quarter-beat snap, Shift free (becomes Ctrl free, as in 2D).

#### 3.3g Quantise, transpose, humanise

**How it works.** All three act on the selection (notes, or hits in the drum grid), from the action bar, right-click,
Ctrl+K, or a key.
- **Quantise (Q):** snaps the selected notes' starts to the editor's grid at full strength — the first try just works.
  The action bar button has a small ▾: **Grid** (defaults to the editor grid), **Strength** (0–100 %; 50 % = halfway,
  keeps feel), **Ends too** (off). The ▾ choices are remembered for the next Q.
- **Transpose:** ↑/↓ for one step; action bar "Transpose…" opens an inline field: semitones (±), **In key** tick box.
- **Loosen (humanise):** action bar › More › "Loosen timing…": Timing (up to ms, default 10), Velocity (spread,
  default 0.05), **Another take** button (a new seed, so the same settings give a different result; the same seed
  always gives the same result, so an agent's re-run is stable).

**Feedback.** Notes slide to their new place (a short animation, 120 ms) and the selection stays selected.
**Undo and adjust.** One step each; repeat Q after changing Strength only re-quantises from the current positions.
**Keys.** Q quantise · ↑/↓ transpose.
**Agent.** `note.quantize` / `hit.quantize {grid, strength, ends}`, `note.transpose {semitones}`,
`note.humanize` / `hit.humanize {timing, velocity, seed}` (all exist). **(new)** `in_key` on transpose.
**Why this way (3E).** Defaults that are right first time; settings one ▾ away. **Rejected:** a quantise dialog.
**Studied.** Logic's region quantise (non-destructive) vs Ableton's (destructive with strength). We store the result
(plain values the person can edit), Ableton-style; the grid in the action bar is Logic's directness.
**Later.** Quantise to a groove taken from another track (Ableton groove extraction).
**Today.** Ops exist (S26); no screen access.

#### 3.3h Ties: a held note that ends on a marker

**Goal.** "Hold this chord until the logo lands, wherever that ends up."
**Who / when.** B constantly, D sometimes.
**How it works.**
1. Drag the note's **right end** onto a marker line: it snaps and the end becomes tied (a small chain mark at the
   end; the marker line lights up).
2. Several selected notes: drag any one's end to the marker: all selected notes end on it.
3. Right-click › **End on marker ▸** lists the markers after the note (for when the marker is off screen).
4. **Untie:** drag the end away with **Shift**, or right-click › "Untie end" (keeps today's length in beats).
5. The settings panel shows the tied length as **"Until #logo"** (not seconds); typing a number unties with a hint.

**Feedback.** When the marker moves (here, from 2D, or by `marker.set`) the note's end follows on the next render.
**Undo and adjust.** One step per tie / untie.
**Agent.** `note.set {dur: {"to": "#logo"}}` / `{dur: "next"}` (exist).
**Why this way (3E).** Sync by markers (rule 8) with one drag. **Rejected:** numbers that must be retyped when the cut changes.
**Studied.** Logic can lock events to SMPTE position, but not to a named marker; nobody ties ends to markers — ours.
**Later.** Ties for clips and designed sounds (STATUS gap 5).
**Today.** Partial: the document supports it; the inspector shows a tied length as seconds and typing replaces the tie.

#### 3.3i Zoom, scroll, seeing other tracks

**How it works.**
- **Ctrl+wheel**: zoom time at the pointer · **Alt+wheel** (proposed): zoom pitch rows (taller / shorter) ·
  **wheel**: scroll up / down in pitch · **Shift+wheel**: scroll in time · middle-drag: pan both · **Z**: zoom to the
  selection (or the part) · **Ctrl+0**: fit the track's notes · **Ctrl+= / −**: zoom time.
- The piano roll's time follows the arrangement's when "Link zoom" is on (toolbar; on by default) so bars line up
  above and below.
- **Follow playhead** (toolbar, on): while playing, the view turns the page when the playhead reaches the right edge.
- **Show other tracks** (toolbar, on): notes of other instrument tracks drawn faintly (grey, behind the grid) — handy
  to write a bass under the chords. Its ▾ picks which tracks. **Double-click a faint note** switches the Editor to
  that track. Faint notes can't be selected or moved.
- Opening the Editor on a track first time: scrolled to its notes (or to middle C on an empty track).

**Agent.** Screen state; not in the document.
**Why this way (3E).** Same wheel grammar as the arrangement and 2D's timeline. **Rejected:** editing several tracks at once by default (too easy to edit the wrong one).
**Studied.** Logic shows other regions' notes in the piano roll when chosen; Ableton's multi-clip editing. We take faint context, read-only.
**Later.** Editable multi-track view (Ableton 11 multi-clip editing).
**Today.** Partial: zoom and scroll exist; no Z, no other tracks, no follow toggle.

---

### 3.4 Drums

The drum grid is the **Editor** (E) for a drum track: a **row per drum**, named in words ("Kick", "Snare", "Open
hat"), time across, the same ruler and velocity strip as the piano roll.

#### 3.4a The drum grid and adding hits

**Goal.** "A kick on 1 and 3, snare on 2 and 4, hats on every eighth."
**Who / when.** A every song; D for rhythmic hits.
**How it works.**
1. Rows: the drums this kit has, in a fixed order (low to high: kick, snare, clap, rim, toms, hats, cymbals). Rows the
   song uses come first in that order; unused rows of a big General MIDI kit (18 drums) fold under **"More drums
   (11)"**. Click a row's name to **hear** that drum.
2. The drum grid starts with the **Draw tool**: **click** an empty cell adds a hit; **click** a hit removes it;
   **drag along a row** paints a hit on each grid step it passes (one step); drag along a row starting on a hit
   erases along the drag. Velocity of a new hit: 0.85; **Shift+click** = accent (1.0), **Alt+click** = soft (0.5)
   (proposed).
3. **V** switches to Select (box select, drag moves hits, double-click adds) — the same tools as the piano roll.
4. Grid default for drums: **1/16** (Auto in the piano roll); same grid menu.
5. Hits are diamonds; size and brightness show velocity.

**Feedback.** Each hit sounds once when placed; painting sounds each new hit.
**Undo and adjust.** A click = one step; a paint drag = one step.
**Keys.** B Draw (default here) · V Select · Delete · Q quantise · Ctrl+D duplicate.
**Agent.** `hit.add` / `hit.add_many {hits: [{drum, at, vel}]}` (exist); drums by name or General MIDI number.
**Why this way (3E).** Effective: a beat in seconds. Efficient: paint a hat line in one drag. Easy: the step-grid
everyone knows from drum machines.
**Rejected:** double-click to add hits (too slow for drums); a separate step-sequencer view (one grid is enough).
**Studied.** Logic's Step Sequencer and Drum Machine Designer, Ableton's drum rack lanes, GarageBand's Beat Sequencer:
all click-to-toggle on a row grid. Taken. GarageBand's "Drummer" (an AI drummer making the part) is an agent's job
here, not a hidden generator.
**Later.** Probability / "sometimes" hits (Ableton 11 chance) — a playback feature, not needed for the jobs.
**Today.** Partial: drum rows exist (`a-drums-1646x900.png`); click adds one hit; no paint, no toggle-remove, no accents, no folding of unused rows.

#### 3.4b Patterns and repeating them

**Goal.** "This one-bar beat, for the whole verse."
**How it works.** A drum pattern is a **part** on a drum track (3.1e): select the bar's hits → **Make a part**
("Beat A") → drag its loop corner to the end of the verse, or right-click › **Repeat to section end** (fills up to
the section's end, one step). Interim (no `part` field yet): the same with a range selection on the drum lane.
A variation: Ctrl+drag a copy, then edit the copy (it is its own part, "Beat A 2").
**Agent.** `hit.duplicate {times}` (exists; **(new)** `times`), `part.make` (new, schema). **(new)** `to: "#section"`
on duplicate = "repeat until this section's end".
**Why this way.** One concept (parts) for melodies and beats. **Rejected:** a separate pattern list (Logic's pattern
regions, FL Studio's patterns) — a second place for the same hits.
**Studied.** Logic pattern regions; Ableton loops a clip. We use the same loop corner as melodic parts.
**Today.** Missing (`hit.duplicate` exists without `times`).

#### 3.4c Swing

**Goal.** "Make the hats bounce."
**How it works.** Drum (and instrument) tracks get **Swing** in the settings panel's essentials for drums (Timing group
for instrument tracks): 0 % (straight) … 100 % (full triplet feel), and **Swing on** 1/8 or 1/16 (folded, default 1/16).
Dragging the value is heard on the next render. The hits stay on the grid in the document; swing is applied when the
song plays, so it can be changed or removed any time, and quantising keeps working.
**Decision: swing is a track setting, not a move of the hits** (new, schema: `swing`, `swingGrid` on tracks, Team
Sam; applied in compile, which delays every off-beat by the swing amount; no engine change).
**Interim:** right-click › "Swing these hits…" moves the selected off-beat hits now (op **(new)** `hit.swing {amount,
grid}` / `note.swing`), stored as plain times.
**Agent.** `track.set {swing, swingGrid}` (new, schema).
**Why this way (3E).** Effective: feel without losing the grid. Easy: one slider on the track.
**Rejected:** destructive only (can't take it back after editing).
**Studied.** Logic region swing (non-destructive), Ableton grooves (applied then committed), MPC swing per pattern. We take the non-destructive track setting.
**Later.** Grooves taken from a recording.
**Today.** Missing.

#### 3.4d Choosing and swapping kits

**How it works.** Select the drum track → L → Drum kits (synth kit, SFZ kits from your folders) → click to hear **your
own beat** on that kit (3.2b) → Enter keeps. Hits are named drums, so they move to the new kit by name. Hits on a drum
the new kit lacks show their row in amber, labelled "Cowbell — not in this kit (6 hits)", with **"Play on…"**: pick
another drum of this kit (one `hit.set {drum}` step) or leave them (silent, warned in the problems list).
**Agent.** `track.set {instrument: "kit"|"kitSfz", kit | kitSfz}` (exists); `inspect_instrument` lists the kit's
drums; `hit.set {drum}` (exists).
**Why this way.** Never silently drop hits. **Rejected:** auto-remapping by guess.
**Studied.** General MIDI mapping in every DAW; Ableton's drum rack swaps pads by note. Same principle, said in words.
**Today.** Partial: kit choice in the inspector; one synth kit ships (`KITS = ["synth"]`); no missing-drum warning on screen.

#### 3.4e Per-drum level, pan and tune

**Goal.** "Snare a bit quieter, hats a little right."
**How it works.** Click a **row name** in the drum grid → the settings panel shows **"Snare (32 hits)"**: Level, Pan,
Tune (synth kit), Length (decay). These are the drum's settings on this track, applied to every snare hit, now and
added later. A hit's own velocity and pan still vary inside that.
**Decision:** a per-drum settings map on the track **(new, schema: `drums: {"snare": {volume, pan, tune, decay}}`,
Team Sam)**, applied in compile.
**Interim:** clicking the row name selects all that drum's hits and the settings panel edits them together
(`hit.set`, exists); new hits copy the values of that row's last hit.
**Agent.** `track.set {drums: {...}}` (new, schema); interim `hit.set` (exists).
**Why this way.** People think "the snare", not "these 32 hits". **Rejected:** a mini-mixer per kit inside the editor (a second mixer).
**Studied.** Ableton drum rack chains (each pad a mixer channel), Logic Drum Machine Designer (a channel per pad).
Their full per-drum effects can come later as "Split drums into tracks".
**Later.** Split a kit into one track per drum (for effects per drum), needs routing.
**Today.** Partial: per-hit pan / tune / decay exist; no per-drum settings.

---

### 3.5 Playing in

#### 3.5a A MIDI keyboard: playing live

**Goal.** "Play the part on my keyboard and hear the track's sound."
**Who / when.** A; people who own a keyboard.
**How it works.**
1. Plug the keyboard in. Rostrum notices within a second; a toast says "MIDI keyboard connected: Arturia KeyStep".
   Settings › MIDI input lists devices (all on by default).
2. **Playing plays the selected track** (instrument or drums), no arming needed — like playing a real instrument. A
   small key icon on that track's header lights while it receives notes.
3. The keyboard sounds through the engine's live transport (the same process that plays the song); the latency is
   shown in Settings › Sound device.

**Agent.** Not applicable (live input); agents write notes.
**Why this way (3E).** Efficient: no arm just to try an idea. **Rejected:** keyboard plays only an armed track (today) — one more click before every idea.
**Studied.** Logic and Ableton route the keyboard to the selected track by default. Taken.
**Today.** Partial: the keyboard is opened only for an armed track (`keys_record.py`); not tried on a real keyboard (none on this laptop).

#### 3.5b Recording into the arrangement

**Goal.** "Record what I play, in time with the song."
**How it works.**
1. **Arm**: the **Rec** pill on the track header (or **R** with no track armed arms the selected one — proposed: R
   arms first, R again records). The top bar shows the Record cluster: ● Record, Take ▾, input meter.
2. **Take ▾** (only while armed) holds: **Count-in** (off / 1 / 2 bars), **Click while recording** (on), **New notes:
   Add to what's there** (default) / **Replace in the recorded range**, **Quantise as played** (off; uses the editor
   grid), **Punch in** (record only inside a range on the ruler).
3. Move the playhead (or set a loop) → **R**. Count-in clicks, then recording; notes appear on the lane as you play.
4. **Loop on (C):** each pass adds on top (overdub) while "Add"; with "Replace", each pass replaces the last pass
   (keep trying until it's right).
5. **R** or **Space** stops. The take is one change. Notes land where you heard them (engine clock, to the sample).
6. **Metronome (K)**: toggles the click for playback too; the click is never in an export (it is not in the song).
   The click's level and sound are in Settings › Recording.

**Feedback.** REC with elapsed time in the top bar; notes drawn live; after stop the Editor shows the track.
**Undo and adjust.** One take = one step (or one step per loop pass). Then quantise, edit as any notes.
**Keys.** R arm / record / stop · Space stop · K metronome · C loop.
**Agent.** Recording is a person's action; the result is `note.add_many` / `hit.add_many` (exist) attributed to the
person. **(new)** "replace" = `note.remove` in range + `note.add_many` in one batch (screen-side).
**Why this way (3E).** Every common recording choice in one ▾, defaults right for most takes.
**Rejected:** a separate "record settings" dialog.
**Studied.** Logic's record settings (merge / replace, cycle takes); Ableton's overdub button. We take merge/replace and per-pass behaviour; take folders for MIDI (Logic) are later.
**Later.** Keeping every pass as an alternative take (take folders); "capture what I just played without recording" (Logic / Ableton capture) — a good idea, needs the engine to keep a short buffer.
**Today.** Partial: arm, count-in, punch, quantise-on-record, one undo per take exist; metronome during playback, overdub/replace and loop passes are missing.

#### 3.5c The computer keyboard as a piano — yes, as a mode

**Decision.** Yes. Many people (Sam's laptop included) have no MIDI keyboard; being able to play an idea in is worth
it. Because single letters are shortcuts in Rostrum, it is a **mode you switch on** with visible state.
**How it works.**
1. Toolbar of the Editor › **Play with keys** (or Ctrl+K "Play with keys"; key **Ctrl+Shift+K**, proposed).
2. A banner across the top of the Editor: "Your keyboard plays notes — A S D F … = C D E F · Z / X octave · C / V
   softer / louder · Esc to stop". Single-letter shortcuts pause; Space, Ctrl shortcuts and Esc still work.
3. Row A S D F G H J K = white keys from C; W E T Y U = black keys. Z / X octave down / up; C / V velocity down / up.
4. It plays the selected track and records like a MIDI keyboard (3.5b) when armed.
5. Esc, or clicking outside the Editor, turns it off.

**Why this way (3E).** Effective: anyone can play in. Easy: a banner says it's on and how to leave.
**Rejected:** always-on letter playing (breaks shortcuts); an on-screen piano only (mouse can play one note at a time).
**Studied.** Logic's Musical Typing (a window), Ableton's computer MIDI keyboard (toggle with M; A-row layout). We take Ableton's layout and Logic's visible window, as a banner.
**Today.** Missing.

#### 3.5d MIDI files in and out

**Goal.** "Bring in a part I wrote elsewhere" / "give my notes to someone using another app."
**How it works.**
- **Import:** drag a `.mid` file onto the arrangement (or File › Import MIDI…). Dropped on empty space below the
  tracks: one new track per MIDI track, starting at the drop's bar. Dropped onto an existing instrument track: its
  notes go onto that track at that bar. Tracks get a built-in instrument from the file's instrument number; drums
  (channel 10) become hits on a drum track.
- If the song is empty, the file's tempo, metre and key come with it. If not, a bar asks inline: **"Use the file's
  tempo and key?"** [Keep mine] [Use the file's].
- **Export:** File › Export MIDI… (the whole song), or right-click selected tracks › **Export as MIDI…** (just those).
  What MIDI can't carry is listed afterwards ("2 hits on 'whoosh' skipped"), never dropped silently.
**Agent.** `edit_import_midi {path, song_map}` (exists) — **(new)** `at` and `track` params; `render_midi {path}`
(exists) — **(new)** `tracks` param.
**Why this way (3E).** Drag-and-drop where you want it. **Rejected:** import always at bar 1 into new tracks only.
**Studied.** Logic / Ableton: drop a MIDI file on a track or empty space; same.
**Today.** Partial: both MCP tools exist; no screen access (STATUS: "No screen button for either").

---

### 3.6 Tempo, key, metre and sections

#### 3.6a Tempo and the tempo map

**Goal.** "Faster" / "slow down into the last chorus" / "make bar 5 land on the cut."
**Who / when.** A once or twice; B constantly.
**How it works.**
1. **Top bar tempo** (always): shows the tempo **at the playhead** ("♩ 100"). Click → type; or drag up / down on it.
   It changes the tempo in force at the playhead (the song's start tempo or the tempo change before it). **Tap**
   (proposed: click the tempo while holding Alt, tap 4 times) sets it from your taps.
2. **Tempo changes:** right-click the ruler › **Tempo change here**, or double-click in the **song lane** (a thin row
   under the ruler that shows tempo flags and key changes; shown once the song has any change, or via right-click
   ruler › Show song lane). A flag shows "♩ 92"; drag it sideways to move (snaps to beats), up / down to change bpm;
   Delete removes it.
3. **Ramps (slowing down / speeding up gradually):** select a tempo change → action bar **"Ramp from here"**: the
   tempo glides from this change to the next instead of jumping. Drawn as a slope between flags.
   - **Decision:** a ramp is a real setting (**new, schema: `ramp: true` on a tempo change, Team Sam**, and the tempo
     map + engine contract learn linear segments). **Interim:** "Ramp from here" writes a tempo change on every beat
     between the two (op **(new)** `tempo.ramp {to}`), grouped as one step; they are drawn as a slope with one handle.
4. **Land a bar on a marker** (job B): right-click a marker › **"Make a bar land here…"** → an inline field asks which
   bar ("5") → Rostrum changes the tempo of the stretch before it (from the previous tempo change) so bar 5 starts
   exactly on the marker. Notes in beats follow the new tempo; things on seconds or markers stay put.
5. Changing the tempo moves everything written in beats (notes, hits, sections); things written in seconds or on
   markers stay (the picture's sync isn't broken by a tempo tweak).

**Feedback.** The ruler re-spaces at once; the seconds line under the bars shows where bars now fall.
**Undo and adjust.** Each change, drag, ramp or fit is one step.
**Keys.** None by default (Alt+click tempo = tap, proposed).
**Agent.** `doc.set {tempo}`, `tempo.add {bpm, at}`, `tempo.set`, `tempo.remove` (exist) · **(new)** `tempo.fit {bar,
to: "#marker"}` · **(new)** `tempo.ramp` (interim) / `ramp` field (schema).
**Why this way (3E).** Effective: steady, changing, ramped and fitted tempos. Efficient: bar-to-cut in one action
instead of trial and error. Easy: tempo where you look (top bar).
**Rejected:** a separate tempo-map window; tempo changes on markers (they can't: a marker in beats would place itself — `tempo.py`).
**Studied.** Logic's tempo track (curves, "Beat Mapping" to fit bars to events); Ableton's tempo automation. We take
the tempo row and Logic's fit-to-event, as one action.
**Later.** Fitting several bars to several markers at once (a full beat map).
**Today.** Partial: tempo map with changes exists (doc + screen popup + ruler flags, P11); no ramps, no fit, the popup covers the roll.

#### 3.6b Key and key changes

**How it works.** Top bar **key chip** ("D minor" or "No key"): click → a picker: root (12 buttons, spelled C, C#/Db …)
and scale (major, minor, dorian, mixolydian, … the list `keys.py` knows). It sets the key **at the playhead** (the
first key, or the key change in force there). **Key change here:** right-click the ruler; it appears as a flag in the
song lane ("→ F major"). The key is **not heard**: it drives the piano roll's shading, "Keep in key", chord names,
transpose-in-key and `inspect_harmony`. A plain line in the picker says so: "The key helps you write; it doesn't
change the sound." "Find the key" (picker button) suggests one from the notes written (`inspect_harmony`).
**Agent.** `key.add {key, at}`, `key.set`, `key.remove` (exist); `inspect_harmony` (exists).
**Why this way.** **Rejected:** "transpose the song when the key changes" — moving notes must be a deliberate action (Transpose on a selection).
**Studied.** Logic's key signature track; Ableton 12 scale per clip. We keep one key map for the song.
**Today.** Partial: key changes exist in the document and the song popup; no shading uses them yet.

#### 3.6c Beats per bar (metre)

**How it works.** Top bar "4/4": click → choose beats per bar (2–12, plus 6/8 written as 6). One metre for the song.
**Decision:** metre changes mid-song (a 7/8 bar) are **later** (new, schema: metre changes like tempo changes); none
of the six jobs needs them.
**Agent.** `doc.set {beatsPerBar}` (exists).
**Today.** Exists (song popup).

#### 3.6d Sections (intro, verse, chorus)

**Goal.** "Mark the song's parts and rearrange them: chorus twice, swap verse 2 and the bridge."
**Who / when.** A always; B to mark scenes; E for navigating.
**How it works.**
1. **Make from a range:** drag on the ruler (a range) → action bar **"Make a section"** → name field inline (last used
   names offered as chips: "verse", "chorus"). The section appears as a labelled band above the ruler. Ranges snap to
   bars.
2. **Select:** click the label (Ctrl+click adds). Its whole time range highlights across all tracks.
3. **Resize:** drag a section's edge (changes only the label's range, not the music).
4. **Move with everything in it:** drag the label. The others **make room**: dropping the bridge before verse 2 moves
   verse 2 and what follows later, and closes the gap where the bridge was (ripple). Everything that starts inside the
   section moves with it: notes, hits, clips, sounds, lines, markers, tempo and key changes, automation points.
   **Alt+drag** = move without making room (overlaps what's there).
5. **Duplicate:** **Ctrl+D** with a section selected: a copy right after it, everything later pushed later. Named
   "chorus 2". Ctrl+drag the label = copy to the drop point (making room).
6. **Delete:** **Delete** removes the label only (the music stays). Right-click › **"Delete with its music"**
   (Shift+Delete, proposed) removes everything inside and closes the gap.
7. **Loop a section:** double-click the label = set the loop to it and play.
8. **Rename:** F2 or double-click the name text.

**Feedback.** While dragging, a ghost of the section and a gap line show where it lands and what moves.
**Undo and adjust.** Each is one step.
**Keys.** Ctrl+D duplicate · Delete label · Shift+Delete with music (proposed) · F2 · C loop (with a section selected).
**Agent.** `section.add {name, at, end}`, `section.set`, `section.remove`, `section.move {by}` (exist) ·
**(new)** `section.place {after: <section id> | at, ripple: true}` (move with making room) · **(new)**
`section.duplicate` · **(new)** `section.cut` (delete with music, close gap) — these use the planned `range.insert` /
`range.remove` (DESIGN §1, "later") as their base, so build those first.
**Why this way (3E).** Effective: arranging a song is moving sections. Efficient: one drag, not select-all-cut-paste.
Easy: the result has no gaps or overlaps unless you ask.
**Rejected:** sections as labels only (today: `section.move` moves content but overlaps).
**Studied.** Logic's arrangement track (drag to move, Alt to copy, others make room) — taken; Ableton has locators only.
**Later.** Section colours (from a palette, like tracks).
**Today.** Partial: sections on the ruler, edge drags and `section.move` exist (P11); no ripple, duplicate, cut or make-from-range.

#### 3.6e How the ruler shows bars and seconds

**How it works.**
- The ruler has two lines: **bars** (big numbers, beat ticks between) and, under it, **time** in small grey
  ("0:09.6"). Above it: the section band and the marker band.
- Right-click the ruler › **Show: Bars and time** (default for songs) · **Time only** (for voice-over: the bar line
  hides, and so does the song lane) · **Bars only**.
- With a picture set, time shows **timecode with frames** at the picture's frame rate ("00:00:09:14").
- Click the ruler = move the playhead; drag = a time range (loop / make section / bounce / export); **Home** =
  playhead to start; double-click a marker = playhead there.
- The **position** in the top bar shows both (bar.beat and time); click it to type a place ("17" goes to bar 17,
  "1:30" to 90 s, "#drop" to the marker).
**Agent.** Times in any form (seconds, `{"beat": n}`, `"#marker"`); screen state otherwise.
**Why this way.** One ruler serves music and picture. **Rejected:** separate rulers per mode.
**Studied.** Logic's dual ruler (bars + timecode), Hindenburg's time-only. We take both, switchable.
**Today.** Partial: bars + seconds exist; no timecode, no time-only, no go-to by typing.

---

### 3.7 Finding sounds: the Sounds panel and the library

#### 3.7a The Sounds panel

**Goal.** "Find the right sound fast, hear it, put it where I want."
**Who / when.** A (instruments), D (effects) constantly; B, C sometimes.
**How it works.**
1. **L** or **+ Track** opens it on the left; L again closes it (the arrangement takes the room back). Its width can be
   dragged; remembered.
2. Top: **search** (focused when opened). Searching looks in everything at once; results grouped by section, best
   matches first. Under the search, filter chips appear only when they help (after a search with many results): for
   files — Kind (whoosh, impact, riser, click, ambience …), Length (short / medium / long), Brightness (dark / mid /
   bright), Attack (sharp / soft); for instruments — Kind (keys, strings, pads, bass, plucked, mallets …).
3. Sections (folded except the first two; each remembers being open):

| Section | Contents | Source |
|---|---|---|
| Recent | the last 12 sounds you used | settings |
| Built-in & played | built-in sounds, played instruments, synth | ships with Rostrum |
| Drum kits | synth kit, SFZ kits in your folders | ships + your folders |
| Sampled (SFZ) | SFZ instruments in your folders | your folders |
| Plug-in instruments | installed CLAP / VST3 | scanned |
| Voices | text-to-speech voices | voice model (download on first use) |
| Designed sounds | whoosh, click, riser, hit, sub drop — sounds Rostrum makes from settings | ships |
| My sounds | sounds you saved (3.2g) | your sounds folder |
| My files | your sound-effect folders, each sound found inside each file | your library folders |

4. **Hear:** click a row (or ↑/↓ with **Auto-play** on, a toggle at the panel's foot). Files play from the sound's
   own start in the file (a file with 20 hits plays just the one you picked); a small waveform is drawn on the row.
   Designed sounds play with default settings. Instruments: 3.2b. Auditions play through the engine.
5. **Place** — any of:
   - **drag** onto a track lane: a ghost shows where it lands and what it snaps to; **dropped on a marker, a library
     sound puts its onset (where the ear hears it start) on the marker**; a whoosh puts its **loudest moment** there
     (both from the library's measurements, so a drop is in sync without nudging). The tag reads "on #logo".
   - **double-click / Enter**: onto the selected track at the playhead (tied to the marker if the playhead sits on
     one); with no suitable track selected, a new track.
   - **drag** into empty space below the tracks: a new track with it.
   What gets made: a **file** → a clip (only that sound's slice of the file: `in` and `length` set); a **designed
   sound** → a sound item; an **instrument / kit / voice** → a track (or a swap, 3.2b–c). Files and designed sounds
   go on audio tracks; dropped onto an instrument track, a new audio track is made right under it.
6. Right-click a row: Show in folder, Copy path, Add to My sounds (instruments), "Find similar" (same kind, nearest
   length and brightness).

**Feedback.** Hearing starts in ~100 ms for files (they are indexed); the placed item is selected, ready to adjust in the settings panel.
**Undo and adjust.** Hearing is not a change; placing is one step (a batch when it also makes a track).
**Keys.** L · ↑/↓ · Enter · Esc · Ctrl+F (in the panel: the search).
**Agent.** `inspect_library {kind, find, length, brightness, attack_ms, seconds, lufs…}` (exists), `inspect_instrument`,
`inspect_plugins` (exist); placing = `clip.add {media, at, in, length}`, `sound.add {design, at}`, `track.add`
(exist); `edit_sounds_from_motion` (exists) for the whole "sounds on the 2D motion" job. **(new)** `clip.add` gains
`align: "onset" | "peak"` so an agent drops on a marker the way the screen does, instead of computing `at - onset_s`.
**Why this way (3E).** Effective: one place for every kind of sound (job D was blocked). Efficient: search + arrows +
drag; sync by measurement, not nudging. Easy: hear before placing; the kind of thing made follows from what was dropped.
**Rejected:** separate browsers for instruments, files, plug-ins (Logic has Library + Loops + File browser: three
places); placing a whole multi-sound file (the next sound in the file plays too).
**Studied.** Logic's Library / Loop / All Files browsers; Ableton's one browser with categories and preview; Soundly
and Reaper's media explorer (search, waveform, preview, drag). We take Ableton's one browser and Soundly's slice-aware
preview; the onset / peak alignment is ours, from the library's measurements.
**Later.** Tags you add yourself; favourites (a star) — Recent covers most of it now.
**Today.** Missing on screen: `LibraryPanel.qml` is built but not shown; designed sounds have no screen; the indexer and search exist (`inspect_library`).

#### 3.7b The person's own library folders

**Goal.** "Use my sound effects collection."
**How it works.**
1. In the Sounds panel, at the foot of **My files**: **+ Add a folder…** (a folder picker), or drag a folder from
   Explorer onto the panel.
2. Indexing runs in the background: the row shows "Reading Sonniss GDC 2024 — 1,240 of 8,000 files"; you can keep
   working; sounds appear as they are read. Later starts re-read only new or changed files.
3. Files that can't be read are listed under the folder ("12 files skipped" → the list with reasons), never hidden.
4. Right-click a folder: Re-read, Remove from library (files are not touched), Show in Explorer.
5. Nothing is copied: the song refers to the file where it is. **File › Collect files into the song folder (new)**
   copies every outside file a song uses into its `media` folder, for moving or sending the song; Deliver offers it
   too. A clip whose file is missing is drawn red with "File missing — Find…" (relink by picking the file or its folder).
6. The folder list is the person's (settings), not the song's.

**Agent.** `inspect_library {folder}` (exists: adds and indexes); **(new)** `edit_collect_media` (copy outside files
into the song, one change rewriting the paths); `inspect_library` reports missing files of the open song **(new)**.
**Why this way (3E).** Effective: big libraries usable in seconds after the first read. Easy: nothing copied silently, nothing lost silently.
**Rejected:** importing (copying) files into a Rostrum library on add — doubles disk use (disk rule).
**Studied.** Soundly / Reaper media explorer index in place; Logic copies on import (optional). We index in place and collect on demand.
**Today.** Partial: indexing, search and settings-held folder list exist (`library.py`, `guides/library.md`); no screen; no collect / relink.

#### 3.7c Free libraries and online sources (later, as optional connectors)

**Decision.** Later, as connectors the person turns on in Settings › Sources, never on by default. Each shows its
licence on every result and is filtered to licences safe to use in a product (CC0, CC-BY; "non-commercial" results
hidden unless the person turns them on, with a plain warning). A CC-BY sound placed in a song is added to the song's
**credits list** (who to credit), which Deliver writes next to the export.
- **Free instrument packs** (CC0 / permissive SFZ libraries): a "Get more instruments" row at the foot of Sampled
  lists a vetted few with size and licence; download with one click into the person's library folder.
- **Online sound sources** (e.g. Freesound, Poly Haven audio when it exists, ambientCG for textures in 3D): search
  results appear in the panel's search under their own heading, hearable from a preview; placing downloads the file
  into the song's `media` folder (so the song works offline).
**Agent.** **(new)** `inspect_sources {find, licence}` / `edit_fetch_source {id}`, when the connectors exist.
**Why later.** None of the six jobs is blocked without them; the person's own folders and the built-ins cover them.
The licence handling must be right first time (the licence rule).
**Studied.** Ableton Packs, Logic's downloadable sound library, Freesound's API (licence per sound). We take per-sound licences shown in the list.
**Today.** Missing (by plan).

---

### 3.8 Recording

**Goal.** "Plug in my mic, see that it hears me, record the line (or the guitar part) as many times as I need, and keep
the best bits."

**Who / when.** Job C (voice-over) every time. Job A (sing or play a part) often. Job D (record foley: a door, keys,
paper) sometimes. Job F: an agent can't sing, but it can set up the take (track, punch range, count-in) for the person.

**How it works.**
1. **Choose the input, once per machine.** Go to File › Settings (Ctrl+,) › Sound device › **Microphone**; empty
   means the system default. This exists. The microphone also shows **where you need it**, in the Take panel
   (step 3): the panel's first line reads "Microphone: *Laptop microphone* ▾" as a picker **(new on screen)**, so you
   never leave the recording screen to change it. If the device has more than one input (an audio interface), each
   armed track's header gets a small **Input** picker ("In 1", "In 2", "In 1+2 stereo"). With one input the picker is
   absent. The input is a track field `input` **(new)**.
2. **Arm a track.** Click the **Rec** pill on the track's header; it turns red. This exists. If no track is selected
   and you press **R**, the app arms the selected track. If nothing is selected, it makes a new "Voice" audio track
   and arms it: one undo step, `track.add {instrument: none, armed}`. So the first take needs no setup. Arming is
   screen state, not the song (an agent's re-run never un-arms you).
3. **The Record cluster appears in the top bar** while any track is armed (exists). In order:
   - **● Record**;
   - the **input meter** (a horizontal bar: green, then yellow from −12 dB, red at −1 dB; a red **peak dot** stays lit
     for 2 s after a clip);
   - **Take ▾**, which opens the Take panel.

   The meter moves as soon as a track is armed, before you record, so you can check your level first.
4. **The Take panel** (one click away; it shows only what applies now):
   - **Microphone** (picker, above).
   - **Hear input**: you hear yourself through the headphones. A **Volume** slider appears only while it is on.
     Off by default.
   - **Count-in**: off / 1 / 2 bars (default off for audio, 1 bar for a notes track).
   - **Punch in**: on/off. While on, red edges appear on the ruler. Drag across the ruler to set them, or drag either
     edge.
   - **Loop recording**: shown only while the loop (C) is on. "Record every pass of the loop as a new take."
   - **Delay of this microphone** (calibration, below).
5. **Record.** Press **R** or click ● Record. Play starts from the playhead, or one bar before the punch-in. During
   count-in a big "Count-in 2… 1…" shows over the arrangement. Then:
   - the Record button reads **■ Stop  0:07.4**;
   - the **take draws on the lane as you speak**: a red clip growing with its waveform;
   - the armed track's header shows a pulsing red dot.
6. **Stop.** Press R, Space or Stop. The take becomes one clip, `land_take` → `clip.add` (exists). The file is named
   `<track>-take-<n>.wav` and saved in the song's `media` folder.
7. **Several passes over the same range = a take stack (new).** When you record over a place that already has a clip
   on that track, the new take does not sit on top as a second sound. It joins a **take stack**: one clip on the lane
   with a badge **"Take 3 ▾"**. Only the newest take plays. With loop recording, every pass adds a take to the stack.
8. **Choose the best (comping, kept simple).**
   - **Whole take:** click the badge "Take 3 ▾". A short list shows Take 1 … 3, each with its length and a tiny
     waveform. Hover a row to hear it from the start of the range. Click a row to make that take play. One undo step.
   - **Best parts:** double-click the stack, or press **E**. The Editor dock shows **the takes one under another**,
     like lanes, with the playing parts lit and the rest dimmed.
     1. Put the playhead between two phrases and press **Ctrl+T** (split). It cuts **every take in the stack** at
        that point, so they all have the same pieces.
     2. Click a piece in any take's row to make it the one that plays there. The other takes dim in that piece.
     3. A crossfade of 10 ms is put on every boundary automatically, so the joins don't click.

     That is all there is. You can't swipe across takes with the mouse (that is **Later**). Split and click do the same
     job with two gestures everyone already knows.
   - **Flatten:** "Keep only the chosen parts", in the stack's right-click or action bar. It throws away the unused
     takes from the song (their files stay in `media` until Clean up files) and leaves ordinary clips.
9. **Recording on several tracks.** Arm several tracks (click each Rec pill, or select tracks, then right-click ›
   Arm). One press of R records them all at the same moment, each from its own **Input**. Each lands as its own take.
   One undo step for all of them.
10. **Microphone delay (calibration).** The Take panel's last line says either "Delay measured: 147 ms ✓" or "Delay not
    measured: takes may land a little late. **Measure now**" **(new button; the engine's `play --calibrate` exists)**.
    Clicking **Measure now**:
    1. A small panel opens: "Turn the speakers up a little and keep the room quiet. You will hear 8 short sweeps (about
       10 s)."
    2. **Start** plays the sweeps, with a progress bar and **Cancel**.
    3. The result is shown in plain words: "Measured 147 ms (steady). Takes from this microphone will now line up
       with the music."
    4. The value is saved per microphone in Settings, not in the song. Measuring again overwrites it.

    The same line appears in Settings › Sound device.

**What happens when something is wrong.** The message is plain, says what to do, and shows where you are looking:
the top bar's Record cluster, or the Take panel. It never fails silently.

| Problem | What you see |
|---|---|
| No microphone at all | The Rec pill still arms, but the meter shows "No microphone found. Plug one in, or choose one in Settings." (link) and ● Record is absent. Plugging one in brings it back within 2 s. |
| Microphone busy (another app holds it) | "The microphone *USB Mic* is being used by another program. Close that program (Zoom, Teams, a browser tab) and try again." **Try again** button. |
| Windows blocks microphone access | "Windows is not letting RostrumSound use the microphone. Open Windows' microphone privacy settings" (a button that opens them). |
| Microphone unplugged while recording | Recording stops. What was captured is kept as a take: "The microphone was unplugged at 0:12. The first 12 seconds are kept as Take 2." |
| Disk full | Recording stops and the take so far is kept: "The disk is full: the take stopped at 1:40 and is kept. Free some space to record more." |
| Input too loud (red peak dot during the take) | After Stop, the take's clip shows small red ticks where it clipped, and the status reads "This take was too loud in 3 places (red marks). Move back or turn the input down, and record again." |

**Feedback.**
- The meter starts within 100 ms of arming.
- The take draws live as you record.
- The status line names each take: "Take 3 recorded, 0:42, on Voice".
- The take-stack badge shows how many takes there are; the chosen pieces are lit in the Editor.

**Undo and adjust.**
- One take is one undo step. Undo removes the clip; the file stays in `media` so redo works.
- Choosing a take or a piece is one step. Flatten is one step.
- The punch edges and count-in are settings, not history (screen state saved with the song's view).

**Keys.** **R** record / stop · **Space** stop · **C** loop (then loop recording) · **Ctrl+T** split all takes of a
stack at the playhead · **E** opens the stack in the Editor · ↑ / ↓ in the take list (proposed) choose the take
above or below.

**Agent.**
- Recording itself is the person's job (an agent has no microphone); `record_take(doc, track, at, seconds)` exists for
  scripts.
- Arming: `track.set {armed}` **(new, screen-state field)** — or keep arming out of the document. **Open point.**
- Take stacks: a `stack` name field on clips (like `group`), with `take.choose {target: clip ids}` **(new)**. It makes
  the targets play and mutes the overlapping takes in the same stack over the same range.
- Split all takes: `clip.split` with the stack's clips as targets (exists; the screen passes the whole stack).
- Flatten: `take.flatten` **(new)**.
- Input: `track.set {input}` **(new)**.
- Calibration: `run_calibrate` MCP tool **(new)**, wrapping the engine call. It answers delay in ms and spread.
- The agent sees takes as clips with `stack` and which one plays (`inspect_document`).

**Why this way (3E).**
- *Effective:* takes, best parts, several tracks, calibration and plain error messages cover real recording sessions.
- *Efficient:* R on nothing selected records straight away; comping is split + click, both gestures used everywhere
  else.
- *Easy:* the stack badge says "there are more takes here", and nothing about takes shows until you have two.

**Rejected:**
- Logic-style swipe comping as the first version: a new gesture to learn, and it can't be done by an agent the same
  way.
- Takes as separate overlapping clips that all play: confusing, and a doubled voice is a common beginner bug.
- A separate "recording page": jobs A and C record in the middle of other work.

**Studied.**
- Logic: take folders, swipe comping and quick-swipe; very fast once learned, invisible until then. We take the
  folder idea (one stack, one badge) and leave the swipe for later.
- GarageBand: a "Take 2 ▾" badge on the region, a menu to pick a take. We take this as the first, simplest level.
- Reaper: takes as lanes under the item, with free-form splitting. We take "split cuts all takes".
- Hindenburg: a per-microphone level check before recording. We take "the meter works before you press Record".

**Later.**
- Swipe comping: drag across a take's row to choose that range. It is a shortcut over split + click, which already
  work.
- A "record keys" track for MIDI keyboards already exists separately (`keys_record.py`) and is untouched here.
- Automatic input level (gain) setting.
- Recording a stereo pair as two linked tracks.

**Today.** **Partial.** Arming, the meter, count-in, punch, hear input and a take landing as one clip all exist. Take
stacks, comping, flatten, choosing the microphone on the panel, per-track input, recording several tracks at once, the
calibration button and the plain error table are missing.

---

### 3.9 Editing audio clips

**Goal.** "Put sound files on the timeline and shape them: shorter, later, faded, louder, longer or higher, cut in
two, glued back."

**Who / when.** Job C (cutting fluffs, levelling) every session. Job D (placing and fitting effects) constantly.
Job B (placing a stinger on a cut). Job A (a recorded part, a sample loop). Job E (levelling clips before mixing).

**How it works.**
1. **Bring a file in.** Drag one or more sound files from Explorer (wav, flac, mp3, ogg, aif):
   - **dropped on a track's lane:** the files land on that track at the drop point, snapped. Several files go one
     after another.
   - **dropped below the last track:** each file gets a new audio track named after the file, all starting at the drop
     point.

   A ghost shows where they will land while you drag. One undo step per drop (`track.add` + `clip.add` in one batch).
   Also: File › Import sound… (Ctrl+I, proposed), which places the files at the playhead on the selected track.
2. **Select.**
   - Click a clip to select it. Ctrl-click adds or removes one. Shift-click selects the clips between, on the same
     track.
   - Drag a box on empty lane space to select everything inside it. Ctrl+A selects all on the focused track.
   - The selected clips get a bright outline, and the **action bar** appears under them.
3. **Move.** Drag the clip body. It snaps to the grid, markers, the playhead and other clips' edges. Dragging up or
   down moves it to another track. Several selected clips move together. One `clip.move` for the whole gesture (exists).
4. **Trim.** Drag the **left edge**: the clip starts later in its file and the sound underneath stays where it was
   (`at` and `in` change together). Drag the **right edge**: it ends sooner or later (`length`). A trimmed-away part
   shows as a faint waveform beyond the edge while you drag, so you see what you are cutting. You can't trim past the
   file's ends; the edge stops there. A grouped (layered) clip's edge trims only that clip (`clip.set_one`).
5. **Split.**
   - Press **Ctrl+T** to cut every selected clip at the playhead (`clip.split`, exists).
   - Or click the action bar's **Split** and then click the clip where you want the cut. The pointer becomes a thin
     blade line until the click; Esc cancels.

   Fades stay on the outer ends.
6. **Join.** Select two or more pieces that were cut from one file and still sit back to back. **Join** (Ctrl+J)
   appears in the action bar (`clip.join`, exists). For clips that aren't from one file and back to back, Join is
   absent, not greyed out; Crossfade or Bounce is offered instead.
7. **Fades.** Hover a clip: a small square appears at each **top corner**. Drag it inward: the fade's curve is drawn
   over the waveform and its length is shown ("Fade in 0.40 s"). Drag back to the corner to remove it.
   `clip.set {fadeIn}` / `{fadeOut}` (exists). Selected clips: the drag on one sets all of them to the same length.
8. **Crossfade.**
   - Select two neighbouring clips on one track. **Crossfade** appears in the action bar; its default overlap is
     0.05 s (`clip.crossfade`, exists).
   - Or drag the seam between two touching clips: a small "⋈" handle shows at the seam on hover. Dragging it sideways
     sets the overlap length directly (same op, `length` from the drag).

   **Overlapping clips that are not crossfaded both play.** This is deliberate: layering effects needs it. The overlap
   is shaded so it is visible.
9. **Stretch (time).** Drag the clip's **bottom-right corner**. The sound gets longer or shorter **without changing
   pitch**, and the label shows "×1.25". It snaps to markers and the grid, so you can drag a whoosh's end onto a marker
   (`clip.set {stretch}`, exists). Dropping the corner on a marker ties the clip's end to it: if the marker moves, the
   stretch follows. That is `length: {"to": "#land"}` on clips **(new: ties exist for notes only — STATUS gap 5)**.
10. **Pitch.** In the inspector, the clip's **Pitch** group has two fields:
    - **"Pitch and speed together"** (tape-style, `pitch`, semitones);
    - **"Pitch only, same length"** (`shift`, semitones).

    Both exist. **Ctrl+↑ / Ctrl+↓** change "Pitch only" by a semitone on the selected clips. The inspector shows
    the result in words: "plays 1.19× faster".
11. **Normalise.** The action bar's **Normalise** sets each selected clip so its loudest moment reaches −1 dB
    (`clip.normalize`, exists). While the action runs, a small inline field next to the button shows "−1 dB" and can
    be edited. A second choice in the same field, **"by loudness"** (each clip at the same average loudness, for
    voice), needs `by: loudness` **(new)**. The measurement is analysed once and cached by file and range.
12. **Gain (level) by dragging a line.** A thin **level line** runs across every clip, at the clip's volume. Drag it
    up or down; the number shows beside the pointer ("−3.5 dB"). `clip.set {volume}` (exists); on a layered clip it
    scales the whole group (exists). Double-click the line to reset it to 0 dB. Points on the line, a level that
    changes inside one clip, are **Later** (below).
13. **Layer several clips as one sound.** Select the clips, then **Ctrl+G** or the action bar's "Layer as one sound".
    This sets the same `group` name on all of them (`clip.set {group}`, exists). Ctrl+G with tracks selected makes a
    group channel instead (3.x, another writer); either way it means "group what I selected". A layered set draws a
    thin bracket on its left, moves and levels as one, and Ctrl+Shift+G un-layers it. To change just one layer, use
    **Alt-click** (proposed) to pick one clip inside the layer; the inspector then edits only that one
    (`clip.set_one`, exists).
14. **Reverse.** Right-click or the action bar › **Reverse**: the clip plays backwards. This is a field `reverse`
    **(new in the contract; the engine already has it)**. It is in now, not Later, because a reversed cymbal or whoosh
    is one of the most common sound-design moves (3.13).
15. **Slip** (move the sound inside the clip without moving the clip). In the Editor (E), drag the waveform sideways:
    the clip's window stays put and the file slides under it (`clip.set {in}`, exists). In the arrangement:
    **Ctrl+Alt drag** on the clip body does the same (proposed). The waveform slides; the edges stay.
16. **Delete and close the gap.**
    - **Delete** removes the clips and leaves the gap. This is the default, because closing gaps would move everything
      later out of sync with the picture.
    - **Shift+Delete** (proposed) = "Delete and close the gap": the clip goes, and everything after it **on the same
      track** moves earlier by its length. This is what cutting a fluff in a voice-over needs.
    - Items on other tracks never move. Times written on a marker keep their form; the offset changes.

    The op is `clip.remove {close: true}` **(new)**. "Close gaps" on several selected clips pulls each one up to the end
    of the one before, with an optional pause to leave between them. The inline field defaults to 0.3 s:
    `clip.close_gaps {pause}` **(new)**.
17. **The waveform at detail** (Editor dock, E, or double-click a clip):
    - The **whole file** is drawn faint, with the part that plays bright, and you can zoom down to single samples.
    - Fades, the level line and split points are drawn on it and can be dragged there too.
    - A time ruler shows seconds and bars.
    - When the clip has a clean-up set, the **Before / After** switch from 3.10 sits in its header, and you can
      **draw the waveform of the original faint under the cleaned one**.
    - With a stack, the takes are shown one under another (3.8).

**Feedback.**
- Every drag follows the pointer at screen rate with the grab point kept, and shows the value as it changes
  ("Trim: 2.40 s", "×1.25", "−3.5 dB").
- Snapping shows a line and the snapped thing's name ("logo", "bar 5").
- The sound updates after release (render debounced about 300 ms).
- The action bar shows only what the selection allows.

**Undo and adjust.**
- Every drag, split, join, fade, stretch, normalise or drop is one step, named.
- Everything can be adjusted afterwards: drag again, or type exact numbers in the inspector (Clip: Starts at, Length,
  Level; Pitch; Fades; Time).

**Keys.** Ctrl+T split at playhead · Ctrl+J join · Ctrl+G layer / Ctrl+Shift+G un-layer · Ctrl+D duplicate right
after · ← → nudge one grid step (Shift: a bar; Alt: 10 ms) · Delete · Shift+Delete delete and close the gap
(proposed) · Ctrl+↑ / ↓ pitch only ±1 semitone · Ctrl+I import (proposed) · Z zoom to selection ·
E editor · Esc deselect / cancel a blade.

**Agent.**

| Action | Operation |
|---|---|
| Import a file | `clip.add {media, at}` |
| Move | `clip.move {by}` |
| Duplicate | `clip.duplicate` |
| Trim, fades, level, pitch, stretch, slip | `clip.set` (`clip.set_one` for one clip inside a layer) |
| Split / join / crossfade / normalise | `clip.split` / `clip.join` / `clip.crossfade` / `clip.normalize` |
| Layer | `clip.set {group}` |

All of the above exist. New:
- `clip.normalize {by: loudness}`
- `reverse` field
- `clip.remove {close}`
- `clip.close_gaps`
- clip length tied to a marker

The agent sees clips (with `at`, `in`, `length`, `stretch`, `group`) in `inspect_document`, and hears them with
`look_levels` and `look_events`.

**Why this way (3E).**
- *Effective:* every everyday clip edit, including the voice-over essentials (split, delete and close the gap,
  normalise).
- *Efficient:* most edits are a drag on the clip itself, with no inspector trip.
- *Easy:* the handles appear where the pointer is, and each one does one thing.

**Rejected:**
- Modifier-drags for stretch and slip on the clip edges (Reaper's Alt-drag-stretch): they clash with 2D's Alt = copy
  and are invisible.
- Automatic crossfade on every overlap (Reaper's default): it breaks layering, which job D lives on.
- Ripple delete across all tracks: it breaks sync with picture and markers.

**Studied.**
- Logic and GarageBand: fade handles on region corners, trim by edges, a gain line in Logic's audio editor; we take
  corners and edges.
- Reaper: free-form fades, a crossfade handle at the seam, ripple per track; we take the seam handle and ripple per
  track (opt-in).
- Ableton: warp markers for stretch; too much for job D, so a corner stretch is enough.
- Hindenburg: delete closes the gap by default in voice. We keep it opt-in (Shift+Delete), because Sound is often
  locked to picture.

**Later.**
- Points on a clip's level line (clip automation; needs the engine to accept clip lanes). Split + level covers a
  breath or a loud word until then.
- Fade curve shapes.
- Warp markers / speed ramps (the engine has them; not in the contract).
- Bounce selected clips into one file (waits for the block-by-block render, DESIGN.md).

**Today.**
- **Partial (operations mostly exist, screen gestures mostly missing).** The ops exist: split, join, crossfade,
  normalise, move, duplicate, the stretch / shift / pitch / group fields.
- The screen has single-clip move only. Edges, corners, the level line, the seam handle, dropping files in, reverse,
  close gap and the detailed clip waveform are missing.

---

### 3.10 Clean-up

**Goal.** "Make this recording sound clean: no hiss, less room, no music under the voice. Or pull the drums out of
this song. Let me hear before and after."

**Who / when.** Job C (almost every voice-over), job D (field recordings), job A (a sample's stems), job E
(dialogue from a video's own sound). An agent cleans and then checks with `look_cleanup`.

**How it works.**
1. **Select the clips.** One clip or many, on any tracks. The action bar shows **Clean up**. Right-click and
   Ctrl+K have it too.
2. **Click Clean up.** The inspector jumps to its **Clean up** group, already unfolded, for all the selected clips
   (mixed values show "—"). The group lists what can be taken out, in plain words:
   - **Background noise** (hiss, hum, air conditioning): slider 0–1, off at 0 (`denoise`).
   - **Room echo**: slider 0–1 (`dereverb`).
   - **Music and effects under the voice**: a switch, "Keep only the voice" (`isolate`). It is absent while a single
     part is chosen.
   - **Keep one part of a song**: a choice of none / vocals / drums / bass / other (`stem`). Beside it is a button,
     **"Split into four tracks"** (`clip.split_stems`, exists).

   Each line has a one-sentence hint ("Start low: too much makes a voice sound watery"). The first time you open it,
   **Background noise** is pre-set to 0.5 on voice clips, so one click does something you can hear. No look presets.
3. **The cleaned take is made as soon as you let go (recommended; §10, point 1).** After the slider is released or
   the switch is flipped, the job starts (`render_cleanup` for those clips). The clip on the lane shows a thin
   progress stripe along its bottom ("Cleaning 40%"). A progress line with **Cancel** appears in the Clean up group.
   - It is made **once and kept**: in the shared cache, keyed by the file's content, the step, the model version and
     the settings (AGENTS rule 7).
   - Changing only the echo amount redoes only that step.
   - Setting a slider back to an earlier value is instant, because it comes from the cache.
4. **The first time a model is needed**, a question appears **in the Clean up group**, not as a window (the screen
   exists: `ModelDownload.qml`):

   > To take out background noise, RostrumSound needs a small helper model (16 MB, licence MIT or Apache 2.0, made by
   > the DeepFilterNet project). It is downloaded once and stays on this computer. **Download** · Not now

   For voice isolation and parts: "… a model of 142 MB (licence MIT, Open-Unmix)". Then a progress bar with
   **Cancel**, a "Downloaded and checked" line, and the cleaning job starts by itself. On failure: "The download
   stopped (no internet?). **Try again** · Close", and nothing half-downloaded is kept. Room echo needs no download
   (it is built in).
5. **Before / after.** While a cleaned clip is selected, a **Before | After** switch appears:
   - in the Clean up group;
   - in the Editor's header;
   - as **B** (proposed), held down while playing.

   It is a plain toggle of `useCleaned` (exists). It flips instantly, without restarting playback, so you hear the
   same word both ways. In the Editor, the original's waveform is drawn faint behind the cleaned one, so you can see
   the noise floor drop.
6. **"Did it help?"** Under the switch is a one-line measurement from `look_cleanup` (exists): "Background noise
   −18 dB · voice level unchanged · room echo shorter". If speech level dropped more than 3 dB, it adds a warning:
   "The voice got quieter too: try less." It is measured once per take and kept.
7. **Play and export** use the cleaned take (preview ≡ export). While a take is still being made, pressing Play
   shows "Waiting for 2 cleaned takes (40%) · **Play the originals instead**". The second choice turns
   `useCleaned` off for those clips (one undo step). The original is never played silently in place of a cleaned
   take (CLEANUP.md rule, kept).

**Feedback.**
- Progress on the clip itself and in the group.
- The before/after switch.
- The measurement line.
- The status line: "Cleaned 3 clips (2 from earlier, 1 new, 4 s)".
- Errors are plain and named: "Not enough free memory to separate the voice (needs 2 GB, 1.1 GB free). Close other
  programs and press Try again."

**Undo and adjust.**
- Each slider release / switch flip is one undo step (the settings).
- The cleaned audio is cache, not history, so undo is instant and redo comes from the cache.
- Cancel stops the job and keeps nothing partial.
- To change it later, select the clip and move the slider again.

**Keys.** H held = hear the original ("before") · Ctrl+K "Clean up" · Esc cancels a running clean-up while its group has
focus.

**Agent.**
- `clip.set {denoise, dereverb, isolate, stem, useCleaned}` on many ids (exists).
- `render_cleanup {ids}` (exists; one clip at a time inside the job).
- `clip.split_stems` (exists).
- `look_cleanup {clip}` (exists): numbers and spectrograms.
- `run_model_install {id}` (exists).
- The agent sees per clip whether the take is made, from the job's answer and the check's "not made yet" lines.

**Why this way (3E).**
- *Effective:* the four clean-ups we have models for, on many clips at once, checked by ear and by number.
- *Efficient:* select → Clean up → move one slider, and it is done; no "Make" step and no window.
- *Easy:* the words describe the problem you hear ("background noise", "room echo"), not the technique.

**Rejected:**
- A separate "Clean up" window or page, as in iZotope RX: that is a different app's worth of complexity.
- Effects-chain plug-ins for clean-up: they would run on every play and break rule 7.
- A one-button "Enhance" that guesses everything (Descript Studio Sound): it can't be adjusted and it hides what it
  changed. It is noted as Later: "Clean up for me" can be an agent run that sets the sliders, visible and editable.

**Studied.**
- Descript's Studio Sound: one switch with an intensity. Easy, but opaque.
- Hindenburg: voice profiling and noise reduction per clip. We take "per clip, in place".
- Logic: Voice Isolation is a channel slider. We take the slider and reject the channel (it should be per clip, and
  cached).
- iZotope RX: before/after spectrogram. We take the faint original under the cleaned waveform.

**Later.**
- "Clean up for me" (an agent sets the sliders from `look_spectrum` / `look_cleanup`).
- Mouth clicks and breath removal (no qualifying model yet).
- Hum removal at a chosen frequency (an EQ can do it today).

**Today.** **Partial.**
- Everything below the screen exists: fields, job, cache, models, download question, `look_cleanup`, the "Make cleaned
  take" bar (P10) and model download (P21).
- Missing:
  - Clean up on several clips from the action bar;
  - making the take automatically on release;
  - the Before/After switch and H (today you flip "Use cleaned take" in the inspector);
  - the measurement line;
  - the faint original in the Editor.
- Blocked: the 142 MB isolation model is not uploaded (NEEDS_DECISIONS 7) and the installer lacks the `cleanup` extra
  (STATUS #20).

---

### 3.11 Voice-over and spoken lines

**Goal.** Two different wishes:
- **Recorded voice:** "I read the script. Make it sound clean, even and at podcast loudness, without my fluffs."
- **Generated speech:** "Type the lines, pick a voice, and have it say them, on time."

**Who / when.** Job C (recorded), job B and job D (a generated scratch voice or a final one for a launch film), and
job F (an agent writes and places lines, a person re-takes the ones they don't like).

**How it works — recorded voice (job C, end to end on one screen).**
1. **Record**, as in 3.8. R with nothing armed makes a "Voice" track and records. Read the whole script; re-read
   fluffed sentences straight away, without stopping.
2. **Cut the fluffs**, as in 3.9. Play, and at a fluff press **Ctrl+T** at its start and end, select the piece, then
   **Shift+Delete** (delete and close the gap). Or, if you re-read straight away, select the bad reading and
   Shift+Delete. Each cut is one undo step.
3. **Clean**, as in 3.10. Select all the voice clips (click the track's lane, then Ctrl+A), then **Clean up** and set
   background noise and room echo.
4. **Level.** With all the clips still selected, use **Normalise › by loudness** (all clips equally loud, `by:
   loudness` new). For a smoother voice, the track's inspector has **Even out the level** (a compressor with voice
   settings, from `effect.add`): one switch, shown only on tracks with clips. The proposed name is "Level the voice".
   It adds the existing compressor effect, visibly, in the track's effects.
5. **Check loudness.** The top bar's loudness readout says "−17.2 · target −16 (podcast)" in amber or green. The
   target is chosen in Deliver, and "Podcast −16" is one of its targets.
6. **Deliver** (Ctrl+Shift+E): podcast target, MP3 or WAV. This is another writer's section; nothing voice-specific is
   needed.

**How it works — generated speech (a voice track).**
1. **Make the track.** In the Sounds panel (L) › **Voices**, each voice is a row with a ▶ to hear a sample sentence
   (pre-made once per voice and kept in the cache, `voice.sample` job **(new)**). Drag a voice onto the arrangement,
   or double-click it, to make a voice track (`track.add {instrument: voice, voice}`, exists). The inspector shows the
   track's **Voice**, **Language** and **How it should sound** (style, plain words: "warm, unhurried").
2. **Add a line.** Do one of these:
   - double-click the voice track's lane at a time;
   - with the voice track selected, press **Enter** on the lane, or use the action bar's **Add line at playhead**;
   - paste text (Ctrl+V) onto a selected voice track: every paragraph becomes a line, placed one after another with a
     0.4 s pause between them.

   A text box opens **in the lane, at that time**. Type, then press Enter to finish; Esc cancels. `line.add {text,
   at}` exists; the paste uses `line.add` in one batch.
3. **Making the audio.** Each line's speech is made right after you finish typing (`render_voice` for that line,
   exists). The line's block shows a progress stripe and then its waveform; its length becomes the true spoken
   length. While it is not made, the block is hatched and says "being made". Play with an unmade line waits with
   "Waiting for 1 line (6 s)", the same rule as clean-up.
4. **Another take.** Select the line, then use the action bar's **Another take** (or **T**, proposed). This is
   `line.set {seed: n+1}`, and the take is made. The line's block shows "Take 2 ◂ ▸": the arrows step back to earlier
   takes **instantly**, because they are kept in the cache. Each take is one undo step.
5. **Change the words.** Double-click the line's block to edit the text inline. The take is made again; the old one
   stays in the cache.
6. **Timing.**
   - Drag the block to move the line. Dropping it on a marker ties it (`"#logo-0.5"`).
   - Lines placed by an agent one after another keep their gaps.
   - "Close gaps" (3.9) works on lines too, with the pause value: `line.close_gaps` **(new)**, or a shared
     `close_gaps` across the timed types.
7. **Level, fades.** Use the level line and the corner fades, as on clips (exists as fields on lines).
8. **Errors, in plain words.**
   - "Not enough free memory to make speech (needs 2.5 GB free, 1.4 GB free). Close other programs and press Try
     again."
   - The first time, the voice model download asks like the clean-up models do: "Speech needs a model of about
     1.4 GB (licence Apache 2.0, Qwen3-TTS). Download · Not now". **The size must be read from the model file
     before shipping**; that number is an estimate.

**Feedback.** Typing shows the words in the lane, making shows a progress stripe on the block, the take is named on
the block, and the status line says "Line made, 5.9 s, Take 2".

**Undo and adjust.** One step per line added, words changed, take changed or move. Speech audio is cache, so undoing
and redoing a take is instant.

**Keys.** Enter on a selected voice track adds a line at the playhead · double-click edits words · T another take
(proposed) · ◂ ▸ step through takes (the block's arrows; Alt+← / Alt+→ proposed) · Ctrl+V paste a script as lines ·
Ctrl+T / Shift+Delete for recorded voice.

**Agent.**
- `track.add {instrument: voice, voice, language, style}`, `line.add`, `line.set`, `line.remove`, `render_voice`
  (all exist).
- `voice.sample` **(new)**.
- `line.add_many` (the generic `add_many`; check that it is registered for lines — `ops_timed.py` does it per type).
- The agent hears the lines with `look_events` / `look_loudness`. `render_voice` answers `start` / `end` per line, so
  the next one can follow.

**Editing a recorded voice by its words — Later, with what it needs.**

The Descript / Hindenburg way: the recording shown as text, where deleting a word deletes that bit of audio.

It needs:
1. A transcript with word timings per recorded file, analysed once and kept in the cache (rule 7): Parakeet v3 /
   Omnilingual via sherpa-onnx, already chosen for 2D captions (memory: captions ASR). It needs a model download
   question like the others.
2. A **Words** view in the Editor dock for a voice track: the text of its clips in order. Selecting words selects that
   time range.
3. Delete / cut / move words, done as the same `clip.split` + `clip.remove {close}` operations, so one history and
   agents get it for free.
4. Optional: "find the fillers" (um, uh, repeated words) highlighted for removal, never removed automatically.

It waits because the cut-and-close-gap tools must exist first (3.9), and the ASR model must be vetted and measured on
this laptop.

**Why this way (3E).**
- *Effective:* both kinds of voice, from the first take to delivery, on one screen.
- *Efficient:* lines are typed where they play, there is no "make voice" step, and takes are browsed with arrows.
- *Easy:* plain names ("How it should sound", "Another take").

**Rejected:**
- Today's voice card on the Instruments page, which shows "add one with line.add": developer words, and the wrong
  place.
- A modal "Generate speech" dialog: it hides the timing.

**Studied.**
- Descript: edit the voice by its words, plus "regenerate" with an AI voice. We take the words editing for later.
- Hindenburg: voice profile, automatic levelling, loudness by target. We take the target in the top bar and
  normalise by loudness.
- ElevenLabs Studio: a script as paragraphs with a regenerate per paragraph. We take "paste a script → lines" and
  per-line takes.

**Later.**
- The Words view (above).
- Choosing an emotion per line beyond the style text.
- Matching a generated voice to a person's recorded voice (needs a voice-cloning model that passes the licence rule;
  none chosen).

**Today.**
- Recorded voice: **partial**, see 3.8–3.10.
- Spoken lines: **partial**. The ops, `render_voice`, the cache and the cards on the old Instruments page exist.
  Typing lines on the lane, making them on finish, take arrows, voice samples, paste-as-lines, "level the voice" and
  normalise by loudness are missing.

---

### 3.12 Scoring to picture and markers

**Goal.** "Show me the film while I write. Let my music and hits land on its moments, and stay there when the edit
changes."

**Who / when.** Job B every time, job D (motion in 2D), job F (an agent places hits on the markers, the person
nudges).

**How it works.**
1. **Bring in the picture.** Do one of these:
   - **drag a video file** onto the arrangement;
   - File › **Picture…**, which shows a small list: "From this project: *Launch film* (2D, rendered 10 min ago) ·
     *Logo sting* …" and "A video file…";
   - Ctrl+K "Picture".

   It sets `picture` (exists; a project item follows its newest render). If the video has its own sound, the status
   line offers "**Put the video's sound on a track**". That makes a track "Picture sound" with one clip at 0 dB, muted by
   default so it never doubles a mix by surprise **(new: extract the audio once into `media`)**.
2. **The Picture panel** appears only while a picture is set:
   - **Where it sits:** it floats over the arrangement's top-right. Drag its title strip to move it and drag any
     corner to resize; it snaps to the arrangement's corners. Its size and place are remembered per song.
   - **What it shows:** the frame at the playhead, plus a footer with **frame number, time and the nearest marker's
     name** ("frame 102 · 4.08 s · logo").
   - **Its buttons:** "–" hides it to a small chip, "Picture ▸", at the top-right; **P** (proposed) shows or hides
     it. "⤢" makes it big, about half the arrangement, while you hold **Shift+P**.
   - **Its menu (⋯):** Choose another… / Starts at… (`pictureAt`, exists; can sit on a marker) / Remove picture.
3. **Scrub with the picture.** Drag the playhead or the ruler, and the picture follows at screen rate. Arrow keys with
   nothing selected step **one frame** (,/. proposed for frame back / forward, like video tools). The ruler can show a
   **frames** row when a picture is set (right-click the ruler › Show frames).
4. **Markers on the ruler.** The ruler has a marker row:
   - **project markers** (shared: made in 2D, or here with "Shared" on) are drawn **solid with a small chain icon**;
   - **song markers** (only this song: "chorus 2") are drawn **hollow**.

   This replaces the dashed style, because dashed reads as "disabled". Hover a marker to see "logo — shared with the
   project, made in Rostrum2D".
5. **Add a marker at the playhead.** Press **M**. A small name field opens on the ruler at the playhead, with the
   text "marker 3" selected. Type "logo", Enter. Beside the field is a switch, **Shared**, on by default when the song
   belongs to a project, off for a stand-alone song. Esc cancels.
   - `marker.add {name, at}` exists for a song marker. A shared marker uses the project's marker list:
     `marker.add {shared: true}` **(new on Sound's side; the project service has the list)**.
   - Pressing M while playing drops the marker at that moment and keeps playing. The name field waits until you stop,
     and the names are "marker 3, 4 …" if you never type.
6. **Move, rename, delete a marker.**
   - Drag its flag: one undo step. A shared marker moves for every app (exists, P15).
   - Double-click or F2 renames it inline. Delete removes it.
   - Right-click: Rename · Share with the project / Make it this song's only · Delete.
7. **Snapping and tying (the grammar at the top).** Notes, hits, clips, designed sounds, lines, sections and
   automation points snap to markers. **Dropping on one ties it.** A tied item shows a small flag on its tied edge;
   hover it to see "On *logo* +0.20 s". Nudging with arrows keeps the tie. In the inspector, a tied time reads
   "**logo** +0.20 s" with a ⋯ menu offering "Unpin (keep the time in seconds)" or "Put on another marker…".
   Note lengths tie their end (`{"to": "#land"}`, exists for notes; clips and designed sounds **new**, STATUS gap 5).
8. **Fit the tempo so a bar lands on a marker.**
   - Click a marker, and the action bar shows **"Land a bar here"**. An inline field asks "Bar [5]", suggesting the
     nearest bar. Enter changes the tempo since the last tempo change so bar 5's first beat falls exactly on the
     marker.
   - Or drag a **bar number** on the ruler's bar row onto a marker (it snaps): the same thing.
   - The status line says what moved: "Tempo 112 → 108.4 bpm from bar 1. 64 notes in beats moved with it; 7 things
     on markers stayed."
   - The op is `tempo.fit {marker, bar}` **(new)**. It sets the bpm of the tempo change in force, or adds one at the
     previous marker when the person holds Alt ("from the last marker only", proposed).
9. **When a shared marker changes elsewhere:**
   - **Moved in 2D:** everything tied to it moves at the next play or render (exists). The status line says "*logo*
     moved 0.3 s later in Rostrum2D. 6 things here moved with it."
   - **Renamed in 2D:** Sound follows the new name by itself (`marker.follow`, exists, one undo step). The status line
     says "*logo* is now called *logo lands* in Rostrum2D. 6 things here follow the new name."
   - **Deleted in 2D:** the things tied to it get a **red broken flag**, and the top bar shows a problem chip: "2
     things are on *logo*, which was deleted in Rostrum2D". Clicking it opens three choices:
     1. **Keep them where they were** (each becomes a time in seconds at the marker's last place: `marker.unpin
        {name}` **(new)**, reading the last place from the project marker list's history);
     2. **Put them on another marker…** (a list; `marker.follow {old, new}`, exists);
     3. **Show me** (selects them).

     Until then, play shows the same chip and export fails, naming the items (exists: loud by design).

**Feedback.**
- The picture follows the playhead at screen rate.
- The marker's name shows in the picture's footer when the playhead is on it.
- A snap line with the marker's name.
- A tied item's flag.
- Status lines after every outside change.

**Undo and adjust.**
- One step per marker added, moved, renamed or deleted, per tie, and per tempo fit.
- A shared marker's change goes into the project's marker history (exists).
- The picture's place and size are view state, not history.

**Keys.** M marker at playhead · F2 rename the selected marker · P show / hide the picture (proposed) · Shift+P
hold for big picture (proposed) · , / . one frame back / forward (proposed) · Alt+M / Alt+Shift+M playhead to the next / previous
marker (proposed) ·
Ctrl while dragging = no snapping.

**Agent.**
- `doc.set {picture, pictureAt}`, `marker.add`, `marker.set`, `marker.remove`, `marker.follow` (exist).
- `inspect_markers` (project markers, exists).
- `look_video` (frames, motion, sheet; exists).
- `tempo.add` / `tempo.set` (exist).
- `look_events {expect: ["#logo"]}` (checks that hits land; exists).
- New: `marker.add {shared}`, `tempo.fit`, `marker.unpin`, clip/sound ties, and extracting the picture's sound
  (`clip.from_picture` or an MCP tool `edit_picture_sound`).

**Why this way (3E).**
- *Effective:* picture, shared markers, ties and tempo fitting make sync survive edits (rule 8).
- *Efficient:* M plus a name makes a marker; dragging a bar onto a marker fits the tempo.
- *Easy:* the picture appears only when you have one; shared and song-only markers look different; every outside
  change is said in words.

**Rejected:**
- A fixed picture pane: it wastes space for jobs A, C and E.
- Making a shared marker always: song-only markers like "chorus 2" would clutter 2D.
- Asking about each marker rename: following it is always right, and undo is there.
- Silently turning orphaned ties into seconds: the person must decide.

**Studied.**
- Logic: a floating movie window, scene markers from cuts, and "beat mapping" (drag a bar onto a point in time). We
  take the floating panel and bar-to-marker dragging.
- Pro Tools: markers with names typed at the playhead while playing (Enter on the keypad). We take "drop while playing,
  name later".
- Reaper: video window plus markers and regions. We take the frame number in the footer.

**Later.**
- Scrubbing that **sounds** (audio grains while dragging).
- Finding cuts in the picture automatically as marker suggestions (`look_video what=motion` exists; a "Suggest markers
  from cuts" action would list them for the person to accept).
- Timecode with a start offset (01:00:00:00).

**Today.** **Partial.**
- Exists: picture corner from a file or project item; markers read and drawn (project ones dashed); dragging shared
  markers; follow on rename; loud failure on delete; ties for notes; the tempo map on the ruler.
- Missing: the floating, resizable panel with footer and hide; M plus inline name; shared vs song switch; the problem
  chip with choices; tempo fit; frame stepping; picture sound; ties for clips and sounds.

---

### 3.13 Sound design for motion

**Goal.** "Every move on screen gets its sound: a whoosh as the card flies in, a click as it lands, a riser into the
logo. Quick to place, quick to swap until it feels right."

**Who / when.** Job D every time, job B (hits), job F (the agent places sounds from the 2D motion, the person
auditions and swaps).

**How it works.**
1. **Find a sound: the Sounds panel (L).** It has three tabs: **Designed**, **My sounds** and **Instruments**. A
   search box sits on top and searches across all three.
   - **Designed:** Whoosh, Click, Riser, Impact (`hit`), Sub drop, each with a one-line description ("a move through
     the air: follows a move's speed"). **Click a row's ▶ to hear it** with its default settings: rendered once and
     kept.
   - **My sounds:** the user's library folders (`inspect_library`, exists). There are kind chips (Whoosh, Impact,
     Click, Riser, UI, Ambience, Foley …), length chips (short / medium / long) and brightness chips. Each row shows
     the name, a mini waveform, the length, and words like "short · bright · sharp". **Hover plays it** (once the
     setting "Play on hover" is on; it is on by default here, off for Instruments). **+ Add a folder** sits at the
     bottom. Indexing a new folder shows progress in place ("Reading 1,240 of 3,800 sounds…") and can be cancelled.
   - With no folder yet, the tab says: "Point RostrumSound at a folder of sound effects you own (a Sonniss bundle,
     your own recordings). Nothing is copied. **+ Add a folder**".
   - The starter set and where it comes from wait on Sam (NEEDS_DECISIONS 2).
2. **Place it.** Do one of these:
   - drag the sound onto a track at a time; it snaps to markers and **ties if dropped on one**;
   - with a track selected, **double-click** the row or press **Enter**, which places it at the playhead.

   Dropping below the last track makes a new track named after its kind ("Whooshes").
   - **A library sound** is placed so that **its loudest moment (whoosh) or its start as the ear hears it (click,
     impact) lands on the drop point**, not the file's first sample. It uses `peak_s` / `onset_s` from the library's
     measurements (exists), so dropping on a marker means it *sounds* on the marker. This is a `clip.add` whose `at` is
     computed (an align helper **(new on screen)**).
   - **A designed sound** is `sound.add {design, at}` (exists).
3. **Shape it.** Select it; the inspector shows **only that design's settings**, essentials first:

   | Design | Essentials (always shown) | Folded |
   |---|---|---|
   | Whoosh | Length, Brightness, Size | Speed curve, Pan path, Doppler, Whistle, Air, Texture |
   | Click | Pitch, Material, Snap | Tight, Body, Air, Knock / pop |
   | Riser | Length, Pitch, Brightness | Curve, Whistle, Air, Texture |
   | Impact | Pitch, Size, Tail | Brightness, Drive |
   | Sub drop | Length, Lands on (pitch), Drop | Drive |

   Volume, Pan and Width are on all of them, plus **Another take**: an action and the key **T** (`seed`). Every value
   is plain words with units. This comes from `fields_design.py` (exists: valid only for the design that has it).
4. **Fit it to the motion.**
   - **Length:** drag the designed sound's right edge. For a library clip, drag the bottom-right corner (stretch,
     3.9).
   - **Riser into a moment:** drop the right edge on the marker. The end is tied (`dur {"to": "#drop"}`), so a riser
     always peaks on "drop" even if 2D moves it. This exists for designed sounds' `dur`, and is new for clips.
   - **Pitch:** a designed sound's Pitch. On a library clip, "Pitch only" (`shift`) or Ctrl+↑/↓.
   - **Reverse** a whoosh or cymbal, as in 3.9 (new field).
5. **Layer.** Select several sounds or clips on one spot, then **Ctrl+G** "Layer as one sound" (3.9). For example a
   designed click plus a library thud plus a riser tail. They move, level and swap position as one; Alt-click edits
   one layer.
   - `group` exists on clips. **Designed sounds need the same `group` field (new)**, so a layer can mix designed and
     recorded sounds.
6. **Audition and swap on the same spot.** Select a placed sound, then the action bar's **Swap…** (or **S**,
   proposed).
   1. The Sounds panel opens, filtered to the same kind and similar length. The current sound is pinned at the top as
      "Now".
   2. **↑ / ↓ step through the candidates.** Each one is put **in place** (aligned the same way, its level matched by
      measured loudness, fades kept). Playback **loops from 1 s before the spot to 1 s after**, so you hear it in
      context with the picture.
   3. **Enter keeps** the one you are on (one undo step). **Esc puts the original back** (nothing in history).
   - For a designed sound, Swap lists the other designs and "Another take" instead.
   - Op: `clip.set {media, in, length, at, volume}` in one call (exists), with the align / level helper on the screen
     side. For agents, `clip.swap {media}` **(new)** does the same alignment.
7. **Sounds placed from 2D motion.** When the picture is a 2D item of the project, the Picture panel's ⋯ menu (and
   Ctrl+K) has **"Add sounds from its motion…"**. A small panel asks:
   - **which layers** (default: all that move on their own, a checklist with the layer names from 2D);
   - **from:** Designed sounds / My sounds (the library);
   - **Add**.

   Rostrum asks 2D for the motion samples itself **(new: today a person must export "Motion samples" in 2D first)**,
   then runs `edit_sounds_from_motion` (exists). The sounds land on tracks "ui whoosh", "ui click" … playing into a
   **ui group channel** with a short shared room and light compressor. Each placed sound is ordinary: select it,
   shape it, swap it. **Running it again** after the animation changes ("Update sounds from motion") moves the sounds
   with the motion and **keeps what you changed** (exists). The status line says "Placed 34 sounds (12 whooshes,
   18 clicks, 4 ticks). Loudest cut for overlaps: −6 dB on ui whoosh."
8. **A recorded effects library** is "My sounds" (step 1). **Recording your own foley** is 3.8 onto an audio track;
   **"Add to my sounds"** on a clip's right-click copies its file into a chosen library folder and indexes it
   **(new)**.
9. **AI-generated effects: Later.** It waits on Sam's choice (NEEDS_DECISIONS 2) and the licence rule. Allowed
   candidates (SFX_SOURCES.md): Stable Audio 3 Small SFX downloaded only after its licence screen, ElevenLabs or
   Stability cloud with the user's own key. On screen it would be a fourth tab, **Make from words**: type "heavy
   metal door slam, short", get 4 candidates to audition and drag like library sounds, made once and kept in the
   cache, with the prompt and model recorded on the clip.

**Feedback.**
- ▶ and hover auditions start within 150 ms (sounds pre-rendered or files read from disk).
- Placing shows a ghost aligned on its peak or onset.
- Swap plays each candidate in context.
- The motion tool reports counts and the overlap cut.

**Undo and adjust.**
- Place, shape (per release), layer, swap (on Enter) and "sounds from motion" are each one step. Running "sounds from
  motion" again is one step and never wipes a person's edit (rule 3).

**Keys.** L Sounds panel · T another take (proposed) · S swap (proposed) · ↑ ↓ Enter Esc inside a swap · Ctrl+G
layer · Ctrl+D duplicate a sound right after (a repeated tick) · Alt drag copy.

**Agent.**
- `sound.add` / `sound.set` / `sound.remove` / `sound.move` / `sound.duplicate` (exist).
- `inspect_library` (search, exists), `clip.add` with `at = moment − onset_s` (exists, documented in library.md).
- `edit_sounds_from_motion {samples, source}` (exists).
- `look_events {expect}` (exists) to check sync.
- New: `clip.swap`, `group` on sounds, `edit_sounds_from_motion {item}` (fetch 2D's samples by item id), "add to my
  sounds".

**Why this way (3E).**
- *Effective:* designed, library and motion-placed sounds, layered and fitted to markers, with a swap loop to find the
  right one.
- *Efficient:* drop on a marker and it sounds on the marker; swapping is arrow keys in place, not delete-and-redo.
- *Easy:* sounds are found by kind and by ear, and settings appear only for the design you chose.

**Rejected:**
- A separate "SFX page": job D happens in the arrangement, against picture and music.
- Swap by opening a browser window and dragging again: it loses alignment and level and costs four times the gestures.
- Stock "look presets" (e.g. "Apple-style whoosh"): tools, not taste.

**Studied.**
- Soundly and Pro Tools' Soundminer: search plus audition, with "spot" placing a sound at the playhead aligned. We
  take audition on hover and place at the playhead.
- Logic's Loop browser: hear in tempo and in context. We take "hear it in context".
- Krotos / Boom's Whoosh plug-ins: designed whooshes with a few settings. We take few essentials and fold the rest.
- Reaper's media explorer: insert at the edit cursor. We take Enter = place at the playhead.

**Later.**
- Make from words (AI effects).
- Automatic variation on repeats (a ±0.3 st pitch and level spread on duplicates; library.md describes it for agents).
- Search by "sounds like this" (similar sounds by measurement).

**Today.** **Partial.**
- Exists: designed sounds (engine, fields, ops), the library index and search, sounds from motion (designed and
  library), ties for designed sounds' length.
- Missing on screen: the Sounds panel itself (the library panel is built but not shown); designed sounds have **no
  screen at all**; auditions; aligned drops; swap; motion from the Picture panel; group on sounds; reverse.

---

### 3.14 Effects and plug-ins

**Goal.** "Make the pad warmer, give the voice some room, glue the drums together — and use the plug-in I bought."

**Who / when.** E (mix to delivery) all the time; A (shaping a sound) often; C (a voice: de-ess, de-hum) once per
job; D (one effect on one clip) now and then. F: agents add effects through the same operation.

**How it works.**
1. **Select first.** Click a track header (or Ctrl-click several), a clip (or several), a group, or the master row /
   strip. The **action bar** under the selection shows **Add effect ▾**; the same entry is in the right-click menu and
   in Ctrl+K ("Add effect: Reverb").
2. **Add effect ▾** opens one menu (the kit's Menu), a search field at the top (typing filters at once):
   - **Built in**, each with a four-word line of what it does: EQ (shape the tone), Compressor (even out loud and
     soft), Reverb (a room around it), Delay (echoes), Saturate (warmth, grit), Tape (wobble and age), Limiter (hold
     the peaks under a line), Width (wider or narrower), Gate (silence between sounds), De-ess (soften sharp "s"),
     De-hum (remove mains hum).
   - **Plug-ins ▸** the installed CLAP / VST3 effects, by maker, newest used first. Shown only when the scan found any
     (rule of individuality); with none, the line reads "No plug-ins found · Look in Settings" and opens 3.22's
     Plug-ins group.
3. Picking one adds it **at the end of every selected chain** (one per selected track / clip / group), as one change.
   The new effect becomes the selection, so the settings panel shows its **essentials** at once (a reverb: Space,
   Mix; a compressor: Amount (threshold), Ratio; an EQ: its bands as a small curve to drag), other settings folded
   below, Ctrl+F to find one. Defaults are chosen so the first try is audible but not extreme (reverb mix 0.25).
4. **Where a chain shows:**
   - In the **Mixer** (X): a row of chips on each strip, in order (`EQ · Squeeze · Reverb`), plus a small "+" at
     the end (the same Add effect menu for that strip).
   - In the **settings panel** of a selected track / group / master: an **Effects** group listing the chain (the
     same chips, one per line). Collapsed to its name when the chain is empty.
   - On a **clip** in the arrangement: a small "fx" mark in its corner while it has effects; click the mark to
     select the clip's chain.
5. **Order:** drag a chip left / right (Mixer) or up / down (settings panel). A line shows where it will land; release
   = one change. Order matters and is the order the sound goes through.
6. **Bypass** (switch an effect off without losing its settings): the dot on the chip. Click it; the chip dims and
   the dot is hollow. Alt-click a chip: bypass all others in that chain except this one, to hear one effect alone
   (Alt-click again restores). One change each.
7. **Remove:** select a chip, Delete (or right-click › Delete effect).
8. **Copy effects elsewhere:** select one or more chips, Ctrl+C; select other tracks; Ctrl+V adds copies at the end
   of each chain with the same settings (one change).
9. **Plug-in window.** A plug-in effect's essentials start with **Open window** (also: double-click its chip). The
   plug-in's own window floats over Rostrum, one per plug-in, stays open while you work elsewhere, and closes with
   its ×. What you change inside it is saved into the song (the plug-in's `state`) and recorded as one change
   when you stop for a second ("Changed Tape in its window"). Settings that the plug-in exposes as parameters
   also show in our settings panel (only those already changed, plus search), so they can be automated (3.17).
10. **When a plug-in fails** (plain words, never silently):
    - **Missing** (the song came from another computer): the chip is outlined red and says "missing". A notice
      in the top bar status: "This song uses Tape (CLAP), which isn't on this computer. Playing stops at this point
      and the song can't be delivered until you install it, or switch it off (bypass) or remove it." Bypass is one
      click on the chip; the song then plays and renders without it (preview ≡ export, so the preview never plays a
      version the export can't make).
    - **Crashed while playing:** playback stops; the chip turns red with "stopped working"; the notice says "Tape
      stopped working while playing. Your settings in it are kept. [Try again] [Switch it off]". Plug-ins run inside
      the sound engine today, so it restarts by itself (logged; "nothing was lost"); a plug-in in its own process,
      so the engine never stops, is later (§10, point 4).
    - **Couldn't load at scan time:** listed in Settings › Plug-ins with the reason in words ("made for 32-bit
      Windows", "needs a licence it can't find", "took longer than 10 s to start").

**Feedback.** Adding / bypassing / reordering re-renders the playing mix within ~0.3 s (the existing debounced
render); while playing you hear it on the next block. The chip shows the effect's short name; hover shows its one-line
purpose and its main setting ("Reverb · Hall · 25 %"). A plug-in window opening takes as long as the plug-in needs;
a spinner sits on the chip meanwhile.

**Undo and adjust.** Add (on all selected), remove, reorder, bypass, a drag in the settings panel, a paste: each one
undo step. Settings can be changed any time by selecting the chip. A plug-in window's edits merge into one step per
pause.

**Keys.** Delete (selected effect), Ctrl+C / Ctrl+V (copy effects), Ctrl+K "Add effect: …", Ctrl+F (find a setting).
No single-letter key for bypass (rarely needed, and B means Draw in 2D).

**Agent.** `effect.add {effect, …settings}` on any list of tracks / clips / buses / master (exists); `effect.set`
including `bypass` (exists); `effect.remove` (exists); **`effect.move {before | after | index}` (new)** to reorder;
plug-ins: `inspect_plugins` (exists: installed ones, their parameters, and which failed with the reason), then
`effect.add {effect: "plugin", plugin: {format, path, id, params}}`. The reply's `changed` lists the new effect ids.
A missing plug-in is a check failure the render reports by name (`RENDER_FAILED`: "pad.plugin_1: Tape (CLAP) is not
installed here").

**Why this way (3E).** *Effective:* every place that has a chain (track, clip, group, master) is reachable the same way,
including clips, which the screen never offered. *Efficient:* select five tracks → one Add effect = five inserts
(today: one strip at a time). *Easy:* the effects are named by what they do, the new effect is selected so its
settings are right there. **Rejected:** a "+ Effect" button on every strip and every clip (clutter; the action bar
appears only with a selection); a separate effects browser window (a menu with search is enough for ~11 built-ins
plus plug-ins); effect presets shipped with looks ("Warm vocal") — tools, not taste.

**Studied.** Logic: insert slots on each strip, plug-in windows float; Reaper: an FX chain window per track, drag
to reorder, a clean failure report on scan. Ableton: effects dropped on a track show in the bottom device view.
*We take* Logic's chips on the strip and floating plug-in windows, Reaper's plain scan report. *We don't take*
Ableton's device rack as the main place (it pushes the arrangement up) or Logic's empty slots (shown before use).

**Later.** Plug-in presets (save / load the plug-in's own settings by name) — the `state` is already saved per
song; the person can copy an effect between songs with Ctrl+C / V. Side-chain inputs to plug-ins (a plug-in compressor
listening to another track) — our own Duck covers the main use (3.16). Parallel chains (split and recombine) — rare.

**Today.** Partial: chains on tracks, buses and master exist in every layer and show as chips on the Mix page
(`MixChain.qml`); clip effects exist in the document but not on screen; no reorder operation; plug-in windows exist
("Open window"); no scan report on screen; missing plug-in behaviour on screen not defined.

---

### 3.15 Groups (buses), sends and routing

**Goal.** "Put the drums together so I can turn them all down at once" and "give the voice, strings and piano the same
room."

**Who / when.** E always; A when the song grows past ~5 tracks; D to keep sound effects under one fader. Not needed
for a first song, so nothing about groups shows until you make one.

**How it works.**
1. **Make a group (select first).** Click a track header, Ctrl-click the others (or Shift-click a run). Press
   **Ctrl+G**, or the action bar's **Group**, or right-click › Send to a new group. One change: a group is made,
   named from its tracks ("Kick + Snare + Hats"; more than three: "Kick + 3 more"), and every selected track now
   plays into it. The name field is selected and editable inline (type to rename, Enter; Esc keeps the made-up name).
2. **Where groups show (refined from DESIGN.md §4, with reason).** In the arrangement a group is a **header row
   above its tracks**, and the tracks that play into it are drawn **indented under it** with a fold arrow (▾) on the
   group. Folding hides the member rows and draws their notes / clips merged in the group's lane, so a 30-track
   song stays readable. This is a view of the routing, not a second list: the indent follows each track's Output,
   and track order in the document is unchanged. *Why:* today buses sit as compact rows at the bottom, far from the
   tracks they hold; seeing "what is inside" where the tracks are is easier, and folding saves room (Logic's summing
   stacks). In the **Mixer** the group's strip sits right after its member strips, with a coloured band over the
   members.
3. **Ungroup.** Select the group's header (or strip) and press **Ctrl+Shift+G** (or right-click › Ungroup). Its
   tracks go back to play where the group played (the master, or the group above). If the group had effects,
   sends feeding it, or automation, the menu label says so: "Ungroup (drops its 2 effects)" — still one step, undoable.
4. **Where a track plays to (Output).** The **Output** picker shows on a track's Mixer strip (under the name) and in its
   settings panel **only once the song has a group** (individuality). It lists Master and the groups. A choice that
   would make a loop (a group playing into itself through another) is **absent**, not greyed. Faster: **drag a track
   header onto a group header** (the group lights up as a drop target; release = one change); drag it out to the
   left edge of the track list to send it back to Master. Groups have the same Output picker (a group can play into
   another group: Strings + Brass → Orchestra).
5. **Sends — a shared reverb in one step.** Select the tracks that should share the room; action bar / right-click
   **Share a reverb** (Ctrl+K "Share a reverb"). One change: a group named "Reverb" is made with one Reverb effect set
   to **only the echo** (mix 100 %, so the dry sound is not doubled), and each selected track gets a send to it at a
   moderate level (0.3). The same menu has **Share an echo** (a Delay instead) and **Send to ▸** an existing group (adds a
   send from each selected track). *Plain words on screen:* "Send: a copy of this track goes to Reverb; the track still
   plays as before."
6. **Adjusting sends.** A track with sends shows a **Sends** row on its Mixer strip: one small knob per send, labelled
   with the group's name. Drag up / down (Shift: fine), double-click to type. In the settings panel the send's
   essentials are its **Level**; folded below: **Before fader** — "On: the send stays at its level when you pull this
   track's fader down (the echo stays while the sound fades). Off (usual): the send follows the fader." Remove a send:
   select it (click its knob's name), Delete.
7. **Loops refused loudly.** The screen never offers a loop. An agent or a script that asks for one gets the call
   refused whole, naming the path: "Error: bus.set › Orchestra: playing into Strings would make a loop: Strings →
   Orchestra → Strings. Accepted outputs: master, Drums."

**Feedback.** After Ctrl+G the new group row appears with the members indented under it, its name field selected,
and the status says "Grouped 3 tracks into Kick + Snare + Hats". Playback continues; the re-render lands within
~0.3 s (the sound does not change: a new group's fader is at 0 dB). Dragging a header onto a group shows the drop
highlight before release. The Mixer's member band shows which strips feed which group at a glance.

**Undo and adjust.** Group, ungroup, an Output change, a header drag, Share a reverb, a send knob drag: one step each.
Rename the group any time with F2 or double-click on its name.

**Keys.** Ctrl+G (group the selected tracks), Ctrl+Shift+G (ungroup), F2 (rename), Delete (selected send or empty
group; a group still fed is refused with the reason, see Agent).

**Agent.** `bus.from_tracks {name?}` on the selected track ids (exists; returns the new bus id; it should also refuse
a loop up front — today only the whole-song check finds loops, `doc/check_mix.py`); **`bus.release` (new)** for
ungroup (tracks to the bus's output, bus removed, one step); `track.set {output}` / `bus.set {output}` (exist; loop
refusal at the operation, **new** check in the operation); **`send.to_new_bus {effect: reverb|delay|none, level}`
(new)** for Share a reverb (bus + effect + sends in one change); `send.add {bus, level, pre}` / `send.set` /
`send.remove` (exist); `bus.remove` (exists, refuses while used: "bus Drums is still used by track kick, send
pad.send_bus_2").

**Why this way (3E).** *Effective:* grouping, sharing a room and routing are each one action that leaves a working
result. *Efficient:* 3 tracks into a group: 4 clicks (was 10: "+ Bus" then route each); shared reverb on 4 tracks: 5
clicks (was ~13). *Easy:* the indent shows what is in a group without opening the Mixer; nothing about groups shows
until there is one. **Rejected:** "+ Group channel" making an empty group to fill (select-first rule); a routing
matrix / patch bay (Pro Tools, Reaper): powerful, unreadable for most people, and every route it can make is
reachable through Output and sends; showing loop targets greyed (individuality: absent).

**Studied.** Logic: select tracks → "Create Track Stack" (folder or summing stack), fold arrow, the stack's strip after
its members. Reaper: folders by indenting tracks, sends in a routing window. Ableton: Group Tracks (Ctrl+G) with
fold, return tracks for shared effects. GarageBand: no groups at all. *We take* Logic / Ableton's select → group →
fold, and Ableton's "returns" idea as one action that makes the shared reverb. *We don't take* Reaper's routing
window or Logic's choice between two kinds of stack (one kind is enough: ours always sums).

**Later.** Groups of groups shown nested in the arrangement deeper than one level (the indent works; deeper nesting
is drawn flat with a "in Orchestra" tag until someone needs it). Sends from groups (only tracks send today).

**Today.** Partial: buses, sends, Output picker exist in every layer; `bus.from_tracks` exists; the screen still has
"+ Group channel" (empty first) and buses as rows at the bottom; no ungroup, no "share a reverb", no header drag,
no loop refusal at the operation.

---

### 3.16 Ducking (sidechain)

**Goal.** "The music should dip whenever the voice speaks, and come back between sentences."

**Who / when.** C and E (voice-over over music) in nearly every such job; D (effects under dialogue) sometimes; B
(score under film dialogue) often.

**How it works.**
1. **Select the tracks that should dip** (the music tracks, or the Music group: a group selects every track that
   feeds it).
2. Action bar / right-click / Ctrl+K: **Duck under…**. A small picker opens right there, listing the **other** tracks,
   voice tracks first (tracks with a Voice instrument or recorded speech), each with a check box. Tick the voice
   (or several), press Enter or click **Duck**. One change: each selected track gets a duck under the ticked ones.
   Default settings so the first try works for speech: dips about 6 dB, quickly down (20 ms), back in 0.3 s,
   **Speech only** on when every ticked track is a voice track.
3. **Seeing it.** On every ducked track's lane the dips are shaded where the duck pulls it down, with the depth written
   at the deepest point ("−6 dB"), from the engine's own report of the render that plays (exists: `DuckDips.qml`).
   The ducked track's header shows a small chip **"under Voice"**; its Mixer strip shows the same chip and a thin
   second needle on the meter showing how far it is pulled down right now.
4. **Adjusting.** Click the chip "under Voice" → the duck is selected; the settings panel shows in plain words:
   **How far down** (shown in dB, −0 to silent), **Which tracks push it down** (the list, add / remove),
   folded: **How fast it dips**, **How fast it comes back**, **Stays down for** (after the voice stops), **Speech only**
   ("listens for speech, lets the music swell back between words, keeps the bass"), and deeper: **Starts early**
   ("dips a moment before the voice, so the first word is clear").
5. **Remove:** select the chip, Delete.

**Feedback.** The dips appear on the lanes after the re-render (~0.3 s, a few seconds on a long song; a thin "updating"
line on the lane meanwhile). While playing, the strip's second needle moves live. Changing How far down redraws the
shading after the render.

**Undo and adjust.** Duck under… (on all selected) is one step; each settings drag is one step; removing is one step.

**Keys.** None of its own (Ctrl+K "Duck under"). Rarely needs speed; a key would cost one of few free letters.

**Agent.** `duck.add {under: [track ids], depth, attack, release, hold, voice, lookahead}` on the ducked tracks (exists);
`duck.set` / `duck.remove` (exist). The render reply carries `ducks` (each stretch below −3 dB, per track), and
`look_levels` / `look_loudness` show the effect. Ducking **under a group** (all of the group's tracks push it down,
including ones added later) is **(new)**: today `under` lists tracks only, so the screen expands a ticked group into
its current tracks and says so ("Under Dialogue's 3 tracks").

**Why this way (3E).** *Effective:* one action covers the whole job, with defaults tuned for speech. *Efficient:*
select music → Duck under… → tick voice → Enter: 4 actions (today: a "+ Duck" on one strip, a picker, then repeat per
track). *Easy:* the words "Duck under" and "under Voice" read as what happens; the dips are drawn where you look.
**Rejected:** "+ Duck" on every strip (clutter, one track at a time); a classic sidechain compressor with threshold /
ratio (jargon, and it needs a send set up first); automatic ducking switched on for every voice track (a choice the
person makes, not a style imposed).

**Studied.** Hindenburg: "auto-ducking" of music under voice as a track setting, depth in dB. Logic / Reaper / Ableton:
a compressor's sidechain input picked from a list. Descript: "ducking" toggle on music. *We take* Hindenburg's
plain, speech-aware ducking and its dB depth. *We don't take* the compressor-with-sidechain route as the main way
(plug-ins can still do it, 3.14 Later).

**Later.** Ducking under a group as a document field (§10, point 13). Drawing the ducked level as an editable
automation lane ("bake the duck") — only if people want to hand-tweak single dips.

**Today.** Partial: ducks exist in every layer, the dips are drawn on the Timeline; the screen adds them with "+ Duck"
per strip, one track at a time; no selection action, no "under a group".

---

### 3.17 Automation

**Goal.** "Fade the strings in over the intro, pull the music down under the line at 0:42, open the filter in the
build."

**Who / when.** E always; B (fades to picture) often; A (builds, filter sweeps) sometimes; D (a whoosh panned left to
right) sometimes.

**How it works.**
1. **Show a lane.** Select a track (or several) and press **A**, or click the small **lane mark** on its header
   (see 7). A lane opens under each selected track, showing **Volume** first (or the last lane you used on that
   track). Press A again to close the selected tracks' lanes. Groups and the master have the same.
2. **Choose what the lane changes.** The lane's header has a picker with **only what this track can automate**: Volume,
   Pan, Expression (notes tracks: dynamics, vibrato), each send's level, every effect setting that can change over
   time (a reverb's Mix, an EQ band's Frequency / Gain, a compressor's Amount …), a plug-in's parameters. Lanes
   that already have points are listed first with a dot. **+ Lane** (beside the picker) opens a second lane under
   the first. The list is read from one catalogue (`doc/lanes.py`), so it never offers what the engine can't do.
3. **From the settings panel (same as 2D's diamond).** Every setting that can be automated has a small **◇** at the
   end of its row in the settings panel. Click it: a point is added at the playhead with the current value, the lane
   opens under the track, and the ◇ fills (◆). With points, the row shows the value at the playhead and changes
   while playing. *Why:* the person is already looking at the setting; 2D uses the same mark for "this changes over
   time".
4. **Edit points.**
   - Click on the lane's line: a point there (snaps to the grid, Shift = free).
   - Drag a point: moves in time and value, stays between its neighbours; the value shows next to the pointer in
     the setting's units (dB, %, Hz).
   - **Several points:** drag a box on empty lane space to select points, Shift-click to add; drag any selected point to
     move them all; Delete removes them; Ctrl+C / Ctrl+V copies them to the playhead (same lane or another track's same
     lane).
   - **Move a stretch up or down:** Alt-drag on the line between two points raises / lowers that whole stretch
     (both its points), the quickest way to "pull this part down 3 dB".
   - **Whole lane up / down:** with points on Volume, the fader in the Mixer shows "automated" and dragging it moves
     every point by the same dB (one step), so a balance change doesn't need redrawing.
   - **Shapes between points** are straight today (see Later: curves).
5. **Range shortcut:** with a time range selected on the ruler and a lane open, right-click › **Fade in here** / **Fade
   out here** / **Dip here…** (asks how many dB, default −6) writes the points for that range (new screen helper over
   `automation.set`).
6. **Recording moves while playing** (touch a fader while playing and have it written) is **Later**.
7. **When a lane is hidden:** the track header shows a small **lane mark** (a tiny curve icon with the number of
   automated settings: "◠ 2") and the track's lane draws a faint line of its Volume shape behind the notes / clips, so
   "this part is faded down" is visible without opening anything. Click the mark to open the lanes.

**Feedback.** Points appear on click; a drag follows the pointer at screen rate (no wait for the engine) and the mix
re-renders after release (~0.3 s). While playing, the Mixer's fader / knob for that setting moves with the lane, and
the settings panel row shows the moving value.

**Undo and adjust.** One click (add), one drag (move one or many), one Delete, one paste, one range helper: one step
each. Every change is one `automation.set` with the lane's whole point list. Times keep their written form (a point on
`#drop` stays on the marker when it moves).

**Keys.** A (show / hide lanes of the selected tracks), Delete (selected points), Ctrl+C / Ctrl+V, Shift (free of grid
while dragging), Alt-drag (move a stretch), arrows (nudge selected points one grid step; ↑ / ↓ one value step,
proposed: 1 dB on Volume).

**Agent.** `automation.set {lane, points}` on a track, bus, master, send or effect (exists; the lane names are the same
as the picker's: `volume`, `pan`, `dynamics`, `level`, `band2.gain`, `param:<id>`); `inspect_operations` lists which
lanes a target accepts; the script's `automate()` writes the same. The reply's `changed` names the lane id.

**Why this way (3E).** *Effective:* everything the engine can change over time is reachable, and only that.
*Efficient:* A and click, or one ◇ click from the settings you are already changing; Alt-drag and fader-offset save
redrawing. *Easy:* the faint shape and the lane mark show "something changes here" without opening lanes; the picker
lists only real choices. **Rejected:** an "Auto" chip on every track header (today's: always present, used rarely);
showing every lane of every track at once (a wall of lines); automation modes (Read / Touch / Latch / Write) — jargon
that only matters for recording moves, which is later.

**Studied.** Logic: A shows automation, lanes under the track, the setting picked from a menu, a mark on regions.
Ableton: automation lanes under the track, "Show automated parameters only". Reaper: envelopes per track, fader
offset ("trim"). GarageBand: a simple volume line under the track. *We take* Logic's A key and picker, Ableton's
"automated first", Reaper's trim as the fader offset, GarageBand's simplicity of the volume line first. *We don't
take* the four recording modes.

**Later.** **Curves between points** (ease in / out shapes) need a per-point `curve` field in the document (Team Sam,
schema; §10, point 5). **Recording moves while playing** (touch a fader or knob, points written; needs the live
transport to report the position of each move). **Drawing freehand** with the pointer (many points, thinned). They can
wait: straight segments with enough points cover fades, dips and builds.

**Today.** Partial: lanes for tracks, buses, master, sends, effect settings and plug-in parameters exist; click adds,
drag moves, Delete removes, one step per gesture; opened by an "Auto" chip; no A key, no ◇ in the settings panel, no
multi-point select / move, no Alt-drag, no fader offset, no hidden-lane mark or faint shape.

---

### 3.18 Mixing, meters and loudness

**Goal.** "Balance the parts, see what's too loud, and know if the song is at the loudness the destination wants."

**Who / when.** E always; C (voice level) every job; A at the end of a song; F: the agent checks with its ears, the
person listens.

**How it works.**
1. **Open the Mixer:** press **X** (or the top bar's loudness readout, or Ctrl+K "Mixer"). It fills the bottom dock
   (one at a time with the Editor; X again folds it). The arrangement stays above, so the playhead and the parts are
   still visible. The dock's height is dragged at its top edge and remembered.
2. **Strips.** One per track in arrangement order, then groups after their members (3.15), the **master pinned at the
   right end** so it never scrolls away. Each strip, top to bottom, shows only what applies:
   name (colour band) · effect chips (3.14) · sends (only if it has any) · Output (only once a group exists) ·
   Pan · **M** / **S** · fader with its meter · the level in dB under it · **Peak** (highest since play started; click to
   reset). An armed track's strip adds the input meter. Narrow windows (1280 wide): strips get thinner and the chips
   collapse into one "3 fx" chip; nothing is cut off.
3. **Faders and pan.** Drag a fader (Shift: fine); double-click to type a dB value; Ctrl-click (or Alt-click) resets to
   0 dB / centre. **With several strips selected** (click names, Ctrl-click, Shift-click a run, or select tracks in the
   arrangement: one selection everywhere), dragging one fader moves all of them by the same dB, one step.
4. **Mute / solo, several at once.** Click M or S on one strip; **drag across** several M (or S) buttons to set them
   all the same way in one move; with several tracks selected, **Shift+M** / **Shift+S** or clicking M / S on
   one of them mutes / solos all selected (the same rule as the action bar: if any is off, all go on). The same M / S
   are on the track headers.
5. **Meters.** Each strip: a bar after the fader (what the strip sends on), a thin line holding the highest point for 2 s,
   red above 0 dB. Master: the bar plus **Loudness now** (the last 3 seconds), **Whole song** (integrated; while
   playing: "so far"), **Loudest peak** against the ceiling ("−1.2 / limit −1.0").
6. **Top bar loudness readout (always).** One small group: **Loudness −14.6 · target −14** with a dot: green within
   ±1 of the target and the loudest peak under its limit, amber otherwise, grey "—" until the first render. Hover:
   "Whole song −14.6 (target −14 for Streaming); loudest peak −1.3 (limit −1). Measured from what plays now." Click:
   opens the Mixer with the master selected. With no target chosen, it shows the number only ("Loudness −18.2").
7. **The loudness curve** sits on the master strip, wide: loudness over the whole song with the target as a dashed
   line, the playhead on it, section names along the bottom. Click on the curve moves the playhead there (find the
   loud bit, hear it).
8. **Listen pictures ("Check the mix").** The Mixer has a **Check** button at its right (Ctrl+K "Check the mix").
   It opens a fold at the Mixer's right (the dock widens it; the strips scroll) with the same pictures and facts the
   agent gets (one source: `rostrum_sound.listen`), from the render that plays:
   - **Loudness over time with the bands** (low / mid / high): where the song gets loud, and from what range.
   - **Spectrum over time** (what pitches / frequencies sound when; hum shows as a steady line).
   - **Facts, plain sentences, each with buttons:** "Pad and Voice cover the same range (1–3 kHz) in bars 9–16; Voice
     is 2 dB above Pad there." [Select both] [Play bars 9–16] · "Bass and Kick both have over half their sound below
     150 Hz." [Select both] · "In mono (one speaker) the Pad drops 6 dB in the chorus." [Play in mono] · "Strings
     are 18 dB under the loudest track." [Select]. These are measurements, **never advice** ("turn the pad down"): the
     person decides by ear. A line at the bottom says what the facts can't tell (from the listening guide).
   - **Play in mono** (a listen switch, not a song change) is beside the pictures.
   Clicking a picture moves the playhead to that time.
9. The **master's own settings** (Loudness matching, Target, Peak limit, Squeeze (glue), master Reverb) are in the
   settings panel when the master is selected, not crammed in the strip; the delivery target is chosen in Deliver
   (3.19) and shows here as one line ("Target: Streaming −14 / −1 · Change…").

**Feedback.** Meters move at screen rate while playing; numbers update ~10 times a second. Fader drags are heard on the
next render (~0.3 s after release; during a drag the live player's gain follows at once where the engine allows,
§10, point 14). "Check" pictures take ~1–3 s for a 3-minute song ("Drawing the pictures…" in the fold, never blocking).

**Undo and adjust.** Every fader drag, pan drag, multi-fader drag, mute / solo click or swipe: one step. Peak reset,
Play in mono, Check, dock height: screen state, not in history.

**Keys.** X (Mixer), Shift+M / Shift+S (mute / solo the selected tracks: M is the marker key in Sound),
Ctrl+A in the Mixer (select all strips), Ctrl+K "Check the mix".

**Agent.** `track.set {volume, pan, mute, solo}` / `bus.set` / `master.set` on any list of ids (exist). Ears (exist):
`look_loudness` (whole-song and short-term loudness, loudest peak, the curve picture, limiter work and which tracks
drove it), `look_levels`, `look_clash`, `look_low_end`, `look_stereo`, `look_spectrum`, `look_events`, `look_beats`.
The screen's Check uses the same functions on the same render. `render_mix {solo, mute}` for a listening check of
parts (writes a check file, never a version).

**Why this way (3E).** *Effective:* balance, loudness and checks in one place, against the real render (preview ≡
export). *Efficient:* the Mixer is one key away from the arrangement, multi-strip moves and swipes cut repeated clicks,
the loudness is always in the top bar (no page to open to check it). *Easy:* plain names (Loudness, Loudest peak, Peak),
a green / amber dot, facts with "Select" / "Play" buttons that lead straight to the place. **Rejected:** a Mix page
(screen hopping; DESIGN.md §4); "+ Duck" on every strip (3.16); a "Fix my mix" button or advice lines (taste, against
"tools, not taste"); jargon units as labels (LUFS-S, dBTP stay small after numbers, hover explains).

**Studied.** Logic: X opens the mixer under the tracks; drag across mute buttons; selected strips move together.
Hindenburg: the loudness meter always visible, the target set per publish. Reaper: master meter with loudness modes.
Ableton: mixer section in the arrangement. *We take* Logic's X and multi-strip moves, Hindenburg's always-visible
loudness against a target. *We don't take* Logic's dozens of meter types or Reaper's meter settings.

**Later.** A loudness-matched A/B ("compare with v003 at the same loudness") once versions are listenable (3.20).
Surround meters (5.1, later in PLAN).

**Today.** Partial: strips, faders, pan, mute / solo, meters, master loudness live, loudness curve, Listen pictures and
plain names (S26) exist on the Mix page; no dock (a page), no top bar readout, no multi-strip moves or swipes, the
master strip holds delivery (Render cut off on small windows), no facts list with Select / Play.

---

### 3.19 Export and delivery

**Goal.** "Give me the final file for Spotify / the podcast host / the video editor — and the stems."

**Who / when.** E at the end of every job; C (podcast mp3 / wav) every job; B (stems to the Editor) every job; A when
sharing a draft (often, quick mp3). D: the 2D / Editor pick up the sound item's render by themselves.

**How it works.**
1. **Open Deliver:** the top bar's **Deliver** button, **Ctrl+Shift+E**, File › Deliver…, or with a time range selected,
   right-click › **Export this range…** (opens Deliver with the range filled in). An untitled song first asks for a
   name in a one-line field inside the dialog ("Name this song to deliver it: [Untitled song] [Save and continue]"),
   because renders go into the song's folder.
2. **The dialog**, one column, top to bottom (each part shows only what applies):
   - **For** — a list in plain words, each with its numbers small after it:
     **Streaming** (Spotify, YouTube, Tidal) −14 / −1 · **Apple Music** −16 / −1 · **Podcast** −16 / −1 ·
     **TV, Europe** (EBU R128) −23 / −1 · **TV, US** (ATSC A/85) −24 / −2 · **For the Editor (film, no loudness
     change)** (new: stems in 32-bit float, no loudness matching, the Editor's Deliver sets loudness on the final mix,
     per `shared\HANDOFFS.md`) · **Custom…** (two numbers). Picking one sets the song's target (one change, the same
     `master.set` the agent uses), so the top bar readout and the Mixer follow. The last choice is remembered per song.
   - **Format** — WAV 24-bit (for video editors) · WAV 16-bit (CD) · WAV 32-bit float (to keep mixing) · FLAC 24-bit
     (lossless, half size) · MP3 320 (small, for listening). Default follows For: Streaming / Apple → WAV 24-bit;
     Podcast → MP3; For the Editor → WAV 32-bit float.
   - **Sample rate** — 44.1 kHz (music) · 48 kHz (video) · 96 kHz (high resolution; absent for MP3).
   - **What** — **Whole song** (default) · **Loop range** (only when one is set) · **Selected section** (only when a
     section is selected) · **From … to …** (times or markers, typed or picked).
   - **Stems** — **None** · **Every track** · **Groups only** · **Every track and group**. Groups only is the natural
     "dialogue / music / effects" split when the person has grouped that way (see §10, point 10).
   - **Trim silence at the end** (on).
   - Folded **More**: **Before mastering** (no loudness matching, squeeze or master effects: for someone else to master),
     **File name** (default `<song>_mix`).
3. **Pass / miss before rendering.** Under the choices, one line from the render that plays now (it is the same render
   as the export, preview ≡ export): "Now: loudness −16.8, loudest peak −0.4. With Streaming it will be raised to −14;
   the limit will hold peaks at −1, working up to 2.1 dB on the loudest moments." Green when the result will meet the
   target; amber with the reason when it can't ("the limiter would have to work 6 dB on the chorus; it will meet the
   number, but the loud parts will be squeezed hard"). Facts, not advice. When the song changed since that render,
   the line says "Measuring…" for a moment.
4. **Render.** The big button names what it makes: **Render mix + 6 stems**. While it works: a progress bar with words
   ("Rendering 1:12 of 3:10"), **Cancel**, and you can close the dialog and keep working (a small progress chip stays in
   the top bar; click it to reopen). Done: a list of what was made (file names, sizes), the measured result with
   **Pass** / **Miss** against the target (within ±1 LU, peak under the limit), **Show folder**, **Copy path**. Fail:
   a red line in words ("Couldn't render: Tape on Pad is not installed. Nothing was written.") plus "Details" (where
   the log is). A cancelled or failed render leaves no file that looks finished (written to a `.partial` folder first).
5. **Where files go.** `<song folder>\renders\<song>\v001\`, `v002` …, never overwritten; the dialog shows the full
   path. Each version's manifest records format, rate, range, loudness and peak of each file and whether stems add up.
6. **Bounce a range of tracks to a new audio track (select first).** Drag a time range on the ruler, Ctrl-click the
   track headers to include (none = all), right-click › **Bounce to audio** (Ctrl+K; proposed key Ctrl+B). It renders
   through the same engine (preview ≡ export) and then, as one change: a new audio track "Bounce of Drums, Bass (bars
   5–9)" with the clip, placed under the last source; the source tracks are **muted, not deleted** (so it can be undone
   and redone by hand). Progress shows on the new track's lane while it renders; Esc cancels.
7. **Handing to the Editor and 2D.** Nothing to press: a render of a song that is an item of a project becomes that
   item's newest render, and the Editor and 2D pick it up (live link, as the picture already does the other way). The
   Deliver dialog says so under the button for a project song: "The Editor and Rostrum2D use the newest version of this
   sound." A song alone (not in a project) says nothing of it.

**Feedback.** Choices update the pass / miss line at once. Render progress every ~0.5 s. Done in about real-time / 2
for a typical song (the block-by-block render, P26 B). The top bar chip shows the % while the dialog is closed.

**Undo and adjust.** Picking **For** / Custom is one change (the song's target), undoable. Rendering is not a song
change (it writes files; nothing to undo — delete the version folder by hand). Bounce is one change (the new track,
the clip, the mutes), undoable; its file stays in `media\` for redo.

**Keys.** Ctrl+Shift+E (Deliver), Enter (Render, when the dialog has focus), Esc (close; a running render keeps going),
Ctrl+B (Bounce to audio, **proposed**).

**Agent.** `render_mix {format, sampleRate, trim, stems, master, solo, mute}` (exists; returns a job), **`from` / `to`
(extend)** for a range, **`stems: "groups"` (extend)** for groups only; `inspect_job` for progress; `run_stop` to
cancel; `master.set {normalize, loudness, truePeak}` for the target (exists); **`edit_bounce {from, to, tracks}`
(new)**: renders and then applies the bounce change, returning the new track id. The reply has loudness, loudest
peak, per-track levels, files, the version folder, `stems_add_up`.

**Why this way (3E).** *Effective:* target, format, rate, range, stems and a check together, plus bounce and the hand-off
to the other apps. *Efficient:* one dialog, defaults by destination (Podcast picks MP3 and −16 at once), the dialog can
close while it works. *Easy:* destinations in plain words with their numbers, a pass / miss line before spending a
render, nothing ever overwritten. **Rejected:** delivery inside the master strip (today's: crowded, Render cut off);
asking for a file path each time (versioned folders, Show folder); presets that change the sound ("radio ready") —
taste; AAC (no encoder we may ship).

**Studied.** Reaper's render dialog: format, range, stems ("selected tracks") and naming in one place. Hindenburg:
publish by destination with a loudness target. Logic: "Bounce in place" turning a region into audio. Descript: export
by destination. *We take* Reaper's all-in-one dialog, Hindenburg's destinations, Logic's bounce-in-place (as select →
bounce, sources muted). *We don't take* Reaper's wildcard file naming or its many dither / normalise options.

**Later.** Several deliveries in one go ("Streaming WAV + Podcast MP3"), a queue of renders; AAC once an encoder can
ship; loudness-matched listening to a finished version (3.18 Later).

**Today.** Partial: format, rate, trim, stems (all), versioned folders, Show folder, Deliver-to targets and pass / miss
after a render exist, crammed into the Mix page's master strip (`MixExport.qml`); no dialog, no range, no groups-only
stems, no pass / miss before rendering, no cancel on screen, no bounce, no "For the Editor" choice.

---

### 3.20 Undo, history and versions

**Goal.** "Take that back. What changed while I was away — and what did the agent do? Get me back to how it was this
morning."

**Who / when.** Every job, many times an hour (undo); F every agent turn (history); E before big changes (versions).

**How it works.**
1. **Undo / redo:** **Ctrl+Z** / **Ctrl+Shift+Z**, or the top bar's ↶ ↷. Every gesture is one step: a whole drag, a
   box-move of 40 notes, a paste, a Group, a multi-fader drag, an Add effect on 5 tracks. Typing in a number box and
   arrow nudges within a second merge into one step (the shared core does this).
2. **Your undo is yours.** Ctrl+Z undoes **your** last change, never the agent's or a script's (`OPERATIONS.md`: undo is
   per author). If a later change by someone else touched the same thing, undo refuses, changes nothing, and says so:
   "Can't undo 'Move chorus': Claude changed those notes since (Add 12 notes). Undo that first, in History." The status
   line shows "Undid: Move chorus" (kit request: today it reads "Undo: …").
3. **Undo across the song and the shared markers.** Moving a project marker on Sound's marker band is a change in the
   project's marker list (shared with 2D and the Editor). Ctrl+Z in Sound undoes your last change **made in this
   window**, whether it was in the song or in the shared markers, in the order you made them. A marker moved in 2D is
   undone in 2D.
4. **The history list (refined: where it opens).** Click the top bar's **"12 changes"** (or Ctrl+K "History"; proposed
   key Ctrl+H). It opens **in the right column, over the settings panel**, full height, with a × (Esc closes; the
   settings panel is back). *Why the right column:* the list needs height, and the arrangement stays fully visible so
   hovering a change can **light up what it touched** (notes, clips, tracks flash in the arrangement). A popup would
   cover the arrangement.
   Each row: who (**You**, **Claude** / the agent's name, **Script: song.py**, **Outside**: the file was changed by
   something else), what in words ("Group Kick + Snare + Hats"), when ("2 min ago"). Rows are newest first.
   - **An agent's turn is one folded row:** "Claude · 14 changes · Build tension cue · 3 min ago" with **Keep** and
     **Undo all**. Unfold (▸) to see each change; each has **Undo this one**. *Keep* only folds it away as reviewed
     (the changes are already in the song: nothing is ever pending, so the person and the agent always hear the same
     song). This is PLAN's kept "agent changes as a reviewable group".
   - **Undo this one** on any row (yours, an agent's, a script's): a new change that reverses it, refused with the
     reason when a later change depends on it.
   - A filter at the top: **Everyone · You · Agents · Scripts**.
5. **Who changed this?** The settings panel's last line for a selected item: "Last changed by Claude, 3 min ago (Add
   strings)" — click it to open History at that change. (from `history.who`)
6. **Versions (new).** File › **Save a version…** (also a button at the top of History): type a name ("before client
   notes"), Enter. Versions show at the top of History under **Versions** (fold). On a version: **Go back to this**
   (a new change back to that point: undoable, so nothing is lost) and **Open a copy** (a new untitled song as it was
   then, to compare). Every delivered render is also marked automatically ("Delivered v003") so "the song as it was
   when I sent v003" is one click.

**Feedback.** Each undo / redo plays nothing new by itself but the mix re-renders (~0.3 s) and the changed items flash
once. The status line says what was undone. History rows light up the items they touched on hover.

**Undo and adjust.** Undo itself is a change in history ("Undid: …"), so undo can be undone; history only grows. Going
back to a version is one step, undoable.

**Keys.** Ctrl+Z, Ctrl+Shift+Z, Ctrl+H (History, **proposed**), Esc (close History).

**Agent.** `inspect_history {limit, group}` (exists: who, what, when, group). Agents' calls in one turn share a `group`
(exists). **`edit_undo {change | group}` (new)**: undo the agent's own last change, one named change, or its whole
group (core has `undo`, `undo_session`, `undo_changes`; the MCP tool is missing). **`version.save {name}` / version
restore (new)** in the shared core (`OPERATIONS.md` describes versions; `history.py` has no version functions yet).

**Why this way (3E).** *Effective:* every change can be found, explained and reversed, including a whole agent turn.
*Efficient:* Ctrl+Z for the usual; one click "Undo all" for an agent turn instead of 14 undos. *Easy:* who / what /
when in words; hovering shows where. **Rejected:** a shared undo for everyone (Ctrl+Z would silently take back the
agent's work while you thought you were undoing your own; Sam can switch to it later, only `history` changes);
accept / reject before agent changes apply (two versions of the song at once, the person hears something the agent
doesn't — against one document); numbered auto-snapshots (versions by name are clearer; the history already holds
every step).

**Studied.** Figma / Google Docs: per-person undo, version history with names, "restore" as a new change. Logic:
undo history window, project alternatives. Descript: version history per composition. *We take* Figma's per-person undo
and named versions restored as a new change. *We don't take* Logic's "alternatives" as separate files (versions are
points in one history).

**Later.** Listening to a version without going back to it (render it in the background, A/B in the Mixer).
Branching versions (two lines of work at once).

**Today.** Partial: one history with who, undo / redo per gesture, per-author undo and session undo in the core, the
change count in the top bar; no history list on screen, no "Undo all" for an agent turn, no "who changed this" line,
no versions, no MCP undo tool; status says "Undo:" not "Undid:".

---

### 3.21 Files

**Goal.** "Start a new song, open the one from yesterday, never lose work, and know where my files are."

**Who / when.** Every session (open / new), rarely (save as, recovery).

**How it works.**
1. **Start:** the app opens the last song, else a new untitled one (exists). **First run:** see 3.22.
2. **New song** (Ctrl+N, File › New song): an empty arrangement with one obvious action ("Add a track (L)") and the
   default tempo / key / sample rate from Settings. The title reads "Untitled song — not saved yet".
3. **Untitled songs are saved on every change** in the untitled area (`~\.rostrum\untitled-songs`): nothing is lost if
   the app closes. **Save…** (Ctrl+S on an untitled song) asks only a name and a place (default
   `Documents\Rostrum Sound\<name>\`) and moves it there.
4. **Named songs are saved on every change** (the document is the one source of truth; agents edit the same file).
   Ctrl+S on a named song says, in the status line, "Saved — every change is saved as you go." **Save a copy as…**
   (Ctrl+Shift+S) makes a separate song folder from this one; the window stays on the original (the status says so,
   with "Open the copy").
5. **Open** (Ctrl+O): pick a song's folder or its `.trk` file; double-clicking a `.trk` in Windows opens it (exists).
   **Open recent:** the File menu lists the 6 newest songs with their folder small under the name; a missing one says
   "moved or deleted" and offers "Remove from list".
6. **Leaving an untitled song with changes** (New, Open, closing the window): "Keep 'Untitled song'? [Save…] [Don't
   keep] [Cancel]" (exists).
7. **Crash recovery:** an untitled song left by a crashed run is offered on the next start as a list: Open / Throw away
   each, Later (exists). A named song needs no recovery (saved per change); after a crash the launcher shows one plain
   sentence and where the log is (S27).
8. **The sample song** (File › **Open the sample song**): opens **a copy** of the Lull sample as an untitled song, so
   the original never changes and the person can play with it freely.
9. **Songs inside a project vs alone.** A song alone is its own folder (`<name>\song.trk`, `media\`, `renders\`). A song
   inside a project is one sound item of the project folder (the same layout under the project); it sees the project's
   shared markers and pictures, and its renders become the item's renders for the Editor and 2D (3.19). The title
   shows "Lull — in project Spring launch". **Move into a project…** (File, only for a song alone) copies it in as an
   item (new).
10. **Damaged or newer files, plain refusals** (nothing is changed, nothing is guessed):
    - Newer: "Lull was saved by a newer RostrumSound (0.3). This is 0.1.2. Update RostrumSound to open it. Nothing was
      changed." [Show folder]
    - Damaged: "Lull can't be opened: song.trk is damaged (it stops partway, at line 812). Nothing was changed."
      [Open the last version that works] (the history can rebuild it, when the history file is intact) [Show folder].
    - A media file missing (a recording moved): the song opens; the clip is drawn red with "file missing"; the
      status says "2 recordings are missing. Playing and delivery stop at them until you find them." [Find…] (pick the
      folder; every missing file found there is re-linked in one change).
11. **Where renders go:** `<song folder>\renders\<song>\vNNN\` (3.19). **Show folder** in Deliver and File › Show song
    folder open Explorer there.

**Feedback.** The title always says the song's name and whether it is in a project or untitled. The status line confirms
saves, moves and copies with the full folder path (hover shows all of it).

**Undo and adjust.** File actions are not song changes (no undo); Re-linking missing files is one change. Save a copy
never touches the original.

**Keys.** Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Shift+S (save a copy as).

**Agent.** `inspect_recent_projects`, `run_open_project {folder}` (exist); any tool takes `item` to work on a song of a
project; the agent works on the same file, so a person's open window receives its changes live. A newer or damaged
file answers `BAD_ARGUMENT` / `CHECK_FAILED` with the same sentence. **`edit_relink_media {folder}` (new)** for missing
files (or `clip.set {media}` per clip, exists).

**Why this way (3E).** *Effective:* nothing is lost (saved per change, crash recovery), nothing is overwritten.
*Efficient:* no Save needed after the first naming. *Easy:* the title says what you have; refusals say what happened,
that nothing changed, and what to do. **Rejected:** a classic Save with "unsaved changes" on every close (agents edit the
same file; two copies of the truth); autosave snapshots as separate files (history already holds every step); silent
repair of a damaged file (guessing).

**Studied.** Logic / GarageBand: a song is a package folder with its media; Ableton: "Collect all and save". Figma:
no save button. Descript: projects saved continuously. *We take* the folder-with-its-media and Figma's no-save model.
*We don't take* Logic's choice between "package" and "folder" (one layout).

**Later.** "Collect all" (copy outside media into the song folder) — today recordings already land in `media\`; library
samples are referenced from the library and travel with the library.

**Today.** Mostly exists (P21–P22): New, Open, recent, Save / Save a copy, untitled saved per change, crash recovery,
`.trk` double-click; missing: "Open the sample song" as a copy, "Move into a project", plain damaged / newer refusals
on screen, missing-media find, Ctrl+S message for named songs (check).

---

### 3.22 Settings, help and guides

**Goal.** "Make it play through my headphones without delay, find out how to do something, and see what's inside."

**Who / when.** Settings: first run and when the sound setup changes. Help: whenever stuck; guides most in the first
weeks.

**How it works.**
1. **Settings** (Ctrl+, or File › Settings…): a dialog built like the settings panel (essentials, folded groups,
   search). Changes apply and save at once; **Done** closes. Only what applies shows (exists). Groups:
   - **Sound device:** **Speakers** (list; "Windows' default" first), **Microphone** (list), **Take over the speakers**
     ("On: only RostrumSound uses them, for the shortest delay between a key and its sound; other programs go quiet
     while it plays") and, only when on, **Buffer** ("how much sound is prepared ahead: shorter answers faster, too
     short crackles; Automatic finds the shortest that plays cleanly"). A **Test** button plays a short tone through the
     chosen speakers (new).
   - **Recording delay** (new on screen): **Measure delay** — "Plays a few clicks and listens with the microphone to
     measure how late recordings arrive, so takes land on the beat. Use the speakers, not headphones, and keep quiet."
     Shows the result ("Measured 146 ms, today") (today a command-line step).
   - **New songs:** Sample rate, Loudness target, Peak limit (exist).
   - **Plug-ins** (new group): the folders searched (the usual ones listed, **Add folder…**), **Look for plug-ins
     now**, and the last scan's result: "Found 23 effects and 4 instruments. 2 couldn't load:" with each name and its
     reason in words (3.14).
   - **Files:** Projects folder; folded: AI models folder (with disk use and **Remove unused models**), Sound engine
     program (advanced).
2. **Help menu** (the top bar's **?**, F1 proposed): **Guides** (Your first song, Recording, Writing parts, Mixing to a
   target, Exporting, Settings, Scoring to picture, Cleaning a recording, Sounds library …) read **inside the app** in the
   kit's guide viewer (links between guides work, Back returns) · **Keyboard shortcuts** (from F1 › Keys): one page
   listing every key, built from the same list the menus use, searchable · **Connect an AI agent…** (3.23) · **About
   RostrumSound** (version, licence MIT, HireMyLens Media) with **Licences of what's inside** (the kit's notices
   dialog) · **Open the log folder** (for reporting a problem).
3. **Hover help everywhere:** every control and settings row has a hover line in plain words (the field's `help`; a
   kit request today).
4. **First run:** no wizard. The app opens a new untitled song; the empty arrangement shows one centred card until the
   first track exists: "Start with **Add a track** (L) · or **Open the sample song** to see one made · New here? Read
   **Your first song**." If no speakers can be opened, the card's first line says so in red with **Open Settings**.
   The card never comes back once a track exists (rule of individuality).

**Feedback.** Settings changes are confirmed in place ("Using Headphones (Realtek)"); a device change that needs the
player restarted says "Takes effect the next time you play". Measure delay shows progress ("Listening… 3 of 8 clicks")
and a plain failure ("Couldn't hear the clicks: turn the speakers up or move the microphone closer").

**Undo and adjust.** Settings are the person's machine choices, not song changes: they are not in the song's history
(and an agent can't change them, see Agent). Each can be changed back in place.

**Keys.** Ctrl+, (Settings), F1 (Help: guides and the key list).

**Agent.** Settings are deliberately **not** agent operations (speakers, microphone and folders belong to the person
at the machine). Agents read guides with `inspect_guide` and tools with `inspect_tools` (exist); plug-in scan with
`inspect_plugins` (exists); model install with `run_model_install` (exists, after the person's yes on screen when the
screen asks).

**Why this way (3E).** *Effective:* every sound-setup problem (no sound, delay, crackle, late takes, missing plug-ins)
is solved in one dialog. *Efficient:* guides and shortcuts inside the app, one key away. *Easy:* plain explanations
on every setting; a first-run card instead of a tour. **Rejected:** a first-run wizard (most people want to start;
the card is enough); "ASIO / WASAPI exclusive / buffer in samples" as labels (jargon: "Take over the speakers" and
milliseconds); guides only on a website (offline, and the agent and the person must read the same text).

**Studied.** Logic / GarageBand: audio device preferences with buffer size in samples; GarageBand's lesson-free start
with a project picker. Reaper: a deep preferences tree. Hindenburg: a short, plain preferences window. *We take*
Hindenburg's short plain settings and GarageBand's "make sound first". *We don't take* Reaper's tree.

**Later.** Choosing which output channels on a multi-output interface (needed with real studio interfaces, not yet
tried), MIDI device settings beyond the per-arm choice.

**Today.** Partial: Settings exists (speakers, microphone, take over, buffer, new songs, folders, models' disk use);
guides exist and the Help menu lists them (`Main.qml helpEntries`), About and licences exist; missing: Test tone,
Measure delay button, Plug-ins group, shortcut list, first-run card, hover help on rows (kit).

---

### 3.23 Working with an agent

**Goal.** "Let my AI agent build the cue while I fix bits of it, and see what it did."

**Who / when.** F, and inside every other job when the person asks an agent to do a step (score to markers, check
the mix, clean the takes).

**How it works.**
1. **Connect once:** Help › **Connect an AI agent…** (exists, kit's dialog): agents found on this computer come first,
   each with **Add to <agent>** (asks first) or **Remove**; every agent has "Do it by hand" with the exact text to
   copy, and what to restart.
2. **The agent works on the same song.** Its changes arrive as normal changes (no reload, the person's undo history
   survives). On the screen:
   - The **status line** shows the latest: "Claude: added 24 notes to Strings" (the agent's name from its connection).
   - Changed items **flash once** in an agent colour (the same for every agent change, distinct from selection), and
     new tracks slide in.
   - Nothing of the person's view moves: selection, playhead, zoom, open dock and the settings panel stay put. If the
     agent deletes what the person had selected, the selection drops it and the status says so.
   - History (3.20) shows the agent's turn as one folded row with **Keep** / **Undo all**.
3. **Handing the agent "the selection".** Select what you mean (notes, clips, tracks, a time range), then:
   - right-click › **Copy for an agent** (Ctrl+K too): puts a plain line on the clipboard to paste into the agent's
     chat: `RostrumSound song "Lull" (C:\Users\…\Lull): selected 8 notes on Strings (strings.n1500 … strings.n9000),
     bars 3–4.` Ids and plain words, so the agent knows exactly what "this" is.
   - or just tell the agent "the selection": the agent reads it with **`inspect_selection` (new)**, which returns the
     open window's selection (ids, type, time range) for that song.
4. **Both editing at once** (AGENTS rule 3). Every change is a small change by id, so the person's and the agent's
   changes don't clash unless they touch the same field:
   - The agent's change lands while the person drags something: the drag continues; if the agent's call touched the
     dragged item, the call is refused to the agent (`CONFLICT`, "a person is moving strings.n1500") and the person
     never notices.
   - The agent re-runs its script: what the person moved by hand **stays**; the agent's reply lists it as held back
     ("strings.n1500 at: script says bar 3, kept bar 3.5 (You, 'Move note')").
   - The person's Ctrl+Z never undoes the agent's work; the agent's undo never undoes the person's.
5. **The agent's ears.** Agents check sound with the look tools on the same render the person hears: loudness and its
   curve, levels per track, clashes, low end, width / mono, timing against markers and beats, notes and pitch, hum and
   steady tones, before / after a clean-up. The person can see the same pictures and facts in the Mixer's **Check**
   (3.18), so "the agent says the voice is buried in bars 9–16" can be checked by clicking **Play bars 9–16**.
   What the ears can't judge (does it sound real, musical, right for the picture) the agent reports as open for the
   person, with the file path (listening guide).
6. **When the agent fails.** A refused call changes nothing in the song (edits are all or nothing). The agent gets the
   one-line error; the person sees, in the status line for a few seconds in amber, "Claude's change was refused:
   strings.n99 doesn't exist" and in History an **Agent activity** fold (new) listing the agent's last 20 calls,
   refused ones included, with the reason. A failed render or job shows in the top bar's job chip in red with the
   reason, never as "done".

**Feedback.** Agent changes appear within the time the change takes to apply (well under a second for edits) and are
heard after the usual re-render. The flash lasts ~1.5 s. The status line is overwritten by the next change; History
keeps everything.

**Undo and adjust.** The person adjusts anything the agent made like their own (select → act). "Undo all" reverses a
whole agent turn in one step, refused with the reason if the person has since changed the same things (then "Undo this
one" per change).

**Keys.** Ctrl+K "Copy for an agent"; Ctrl+H (History, proposed).

**Agent.** Everything a person does maps to an operation through `edit_document` / `run_script` (exist); `inspect_history`
(exists); **`inspect_selection` (new, shared core: 2D needs the same)**; **`edit_undo` (new)**; the look tools (exist);
`inspect_guide` for "how to" (exists). Every change carries `who: agent:<name>` and the turn's `group` (exists).

**Why this way (3E).** *Effective:* the agent and the person really share one song, with nothing wiped and every change
reviewable. *Efficient:* "the selection" replaces describing notes in words; Undo all replaces many undos. *Easy:* no
agent mode: the screen behaves the same whoever made the change; the status line and the flash say what just happened.
**Rejected:** an AI chat panel inside Sound now (the person's own agent already has one; PLAN's "AI panel" can come
later through the kit for both apps); locking the song while the agent works (blocks the person; per-id changes make
it unnecessary); applying agent changes only after the person accepts (two songs at once, see 3.20).

**Studied.** Figma multiplayer: others' edits arrive live, your view and undo stay yours. Google Docs: suggestions
mode (rejected here, see 3.20). Descript's AI actions: results land as normal edits with undo. *We take* Figma's live,
per-person model and Descript's "agent edits are ordinary edits". *We don't take* suggestion mode.

**Later.** An AI panel in the kit (ask in place, "make variations" giving alternate takes, PLAN's kept list); the agent
seeing the person's playhead and loop range as context (`inspect_selection` can carry them from the start).

**Today.** Partial: Connect an AI agent exists; agents edit the same song live through MCP with who and group; script
re-runs keep the person's edits; the change count shows. Missing: flash of agent changes, folded agent turn in a
history list, Copy for an agent, `inspect_selection`, `edit_undo`, Agent activity.

---

## 4. End-to-end flows with click counts

**How counted** (as DESIGN.md §3): a click = one press (a double-click counts 1; a drag counts 1; typing a value
counts 1); keys counted separately; a **screen change** = a page switch, a popup or a dialog opening (a panel that
opens beside the work, like the Editor following the selection, is counted as a "panel" not a screen change). Today's
numbers are from `before\clicks.md`. "Today" covers only the part of the flow that today's table walked; the new
total also includes getting to a delivered file.

### Summary

| Flow | Today (same steps) | New (same steps) | New, empty song → delivered file | Screen changes today → new |
|---|---|---|---|---|
| A · Song: 2 tracks, 16 notes, 8 hits, repeat 4 bars, a section | ~57 clicks | **32 clicks + 3 keys** | 34 clicks + 3 keys | 2–4 → 0 (+ Deliver dialog) |
| B · Score: load picture, 3 markers, tempo so bar 5 lands | ~10 + **blocked** (no markers on screen) | **12 clicks + 7 keys** (6 + 1 if 2D made the markers) | 21 clicks + 10 keys | 3 popups → 1 (picture chooser) |
| C · Voice-over: record, cut a fluff, clean, even out, podcast | ~16 + **blocked** (no split / normalise) | **9 clicks + 6 keys** | same | 2 → 1 (Deliver) |
| C′ · Spoken lines (generated voice) | **blocked** | **3 clicks + 2 keys** | 5 clicks + 2 keys | — → 0 |
| D · SFX: a whoosh and an impact on two markers | **blocked** | **6 clicks + 1 key** | 8 clicks + 1 key | — → 0 |
| E · Mix: 3 faders, group 3 tracks, 2 effects, target, WAV + stems | ~18 clicks | **13 clicks + 3 keys** | same | 1 page + 3 pickers → 1 dialog |
| F · Agent + person | 1 (history) | **2 clicks + 1 key** to tweak, 0 to watch | — | 0 → 0 |
| Fix a mix an agent made | not walked (≈ 14, Mix page, render cut off) | **9 clicks + 2 keys** | same | → 1 (Deliver) |
| 15-second sting for a logo reveal | **blocked** (no designed sounds on screen) | — | **17 clicks + 2 keys** | — → 2 |

### A · Write a song (two tracks, a repeat, a section, delivered)

| # | Do | Clicks | Keys | Screen |
|---|---|---|---|---|
| 1 | Ctrl+N | | 1 | Empty song (W1) |
| 2 | Click **Add a track** | 1 | | Sounds panel opens (panel) |
| 3 | Double-click **Piano** (single click first to hear it is optional) | 1 | | Track "Piano" added and selected; Editor opens on its piano roll (panel) |
| 4 | Click 16 notes into the roll (click = a note of the grid length; drag = longer) | 16 | | Notes appear and sound as placed |
| 5 | Click **+ Track**, double-click **Drum kit** | 2 | | Drums track; Editor shows its drum grid |
| 6 | Click 8 hits | 8 | | |
| 7 | Drag on the ruler over bars 1–4 → Ctrl+D | 1 | 1 | Everything in bars 1–4 copied to bars 5–8 (one undo step) |
| 8 | Drag on the ruler over bars 1–8 → **Make a section** → type "verse" → Enter | 3 | 1 | Section label on the ruler |
| | *Same steps as today: 32 clicks + 3 keys (today ~57, 2–4 page/popup changes)* | | | |
| 9 | **Deliver** → **Deliver** (defaults: Streaming −14, WAV, whole song) | 2 | | Dialog; progress; "Done · Show file" |
| | **Total** | **34** (today's ~57 had no delivery) | **3** | 1 dialog |

### B · Score to picture

| # | Do | Clicks | Keys | Screen |
|---|---|---|---|---|
| 1 | **+ Add › Picture to work to…** → click the project item "Launch film" | 3 | | Picture chooser (1 change); Picture panel appears; 2D's markers on the ruler |
| 2 | Three hits not yet marked in 2D: click the ruler at the moment (or play and stop there) → M → type a name → Enter, ×3 | 6 | 6 | Marker flags appear, named |
| 3 | Click marker "cut" → **Land a bar here** → type 5 → Enter | 3 | 1 | Tempo changes so bar 5 starts on "cut" (one undo step) |
| | *Same steps as today: 12 clicks + 7 keys (today ~10 + blocked); if 2D already made the markers: 6 clicks + 1 key* | | | |
| 4 | L → double-click **Strings** | 1 | 1 | Track + Editor |
| 5 | Click 4 notes (they snap to the marker), drag across the velocity strip for the swell | 5 | | |
| 6 | Drag on the ruler around the marker → C → Space | 1 | 2 | Loop plays with the picture |
| 7 | **Deliver** → **Deliver** | 2 | | |
| | **Total** (with the 3 markers made here) | **21** (15 if 2D made them) | **10** (4) | 1 popup + 1 dialog |

### C · Voice-over

| # | Do | Clicks | Keys | Screen |
|---|---|---|---|---|
| 1 | Ctrl+N, L → double-click **Microphone** | 1 | 2 | Track "Voice" added and armed; ● Record and the input meter appear |
| 2 | R → speak → Space | | 2 | W4; the take lands, selected; Editor shows its waveform |
| 3 | Drag across the fluff in the Editor → Delete | 1 | 1 | That part is cut out, the gap closes (one undo step) |
| 4 | Ctrl+A in the lane (both pieces) → **Clean up** → **Clean** | 2 | 1 | Clean-up popover; progress on each clip, then the cleaned sound plays |
| 5 | **Even out level** | 1 | | Both pieces at the same loudness |
| 6 | **Deliver** → Target **Podcast −16** → File **MP3** → **Deliver** | 4 | | Dialog (1 change) |
| | **Total** | **9** (today ~16 + blocked) | **6** | 1 dialog (today 2) |

### C′ · Spoken lines (a generated voice)

| # | Do | Clicks | Keys |
|---|---|---|---|
| 1 | L → double-click **Voice: Maya** | 1 | 1 |
| 2 | In the Editor's "Type what she says" box: type the line → Enter (first time: the model download question, +1) | 1 | 1 |
| 3 | **Speak again** if you want another reading | 1 | |
| 4 | Deliver → Deliver | 2 | |
| | **Total** | **5** | **2** |

### D · Sound for motion (a whoosh and an impact on two 2D markers)

| # | Do | Clicks | Keys |
|---|---|---|---|
| 1 | Click marker "card in" on the ruler (playhead moves there) | 1 | |
| 2 | L → type "whoosh" → double-click **Whoosh** | 2 | 1 |
| 3 | Click marker "logo lands" → double-click **Impact** (panel still open at 1646; at 1280 it closed: +1 key) | 2 | |
| 4 | Click the whoosh → **Make another like it** until it fits (optional) | 1 | |
| | *Same steps as today: 6 clicks + 1 key (today blocked)* | | |
| 5 | Deliver → Deliver | 2 | |
| | **Total** | **8** | **1** |

Each sound is placed on an "Effects" track made the first time, and **tied to its marker** because the playhead was
on one: when 2D moves "logo lands", the impact moves with it. (Whether a whoosh *ends* rather than starts on its
marker is writer 3's "sound for motion" section.)

### E · Mix to delivery

| # | Do | Clicks | Keys | Screen |
|---|---|---|---|---|
| 1 | X | | 1 | Mixer opens (panel) |
| 2 | Drag 3 faders | 3 | | Loudness readout moves |
| 3 | Click Drums strip, Ctrl+click Bass, Ctrl+click Perc → Ctrl+G → Enter (name kept: "Drums + Bass + Perc") | 3 | 2 | A group strip appears after them, routed (today 10 clicks, 3 pickers) |
| 4 | On a strip: **+ effect** → **Squeeze**; on another: **+ effect** → **Space** | 4 | | |
| 5 | **Deliver** → Stems **Each group** → **Deliver** (target Streaming −14 is the default) | 3 | | Dialog |
| | **Total** | **13** (today ~18) | **3** | 1 dialog (today a page + 3 pickers) |

### F · Agent and person together

| # | Who | Do | Person's clicks / keys |
|---|---|---|---|
| 1 | Person | Connect an AI agent (once per machine) | — |
| 2 | Agent | Builds a 20 s cue to the markers; each step shows in the arrangement and the message line ("Agent: added 32 notes to Strings") | 0 (watching; nothing moves the person's view) |
| 3 | Person | Box-select the busy notes in bar 3 → Delete | 1 click + 1 key |
| 4 | Person | Tells the agent "tidy the ending"; the agent reads the selection (`inspect_selection`) or the range | 0 |
| 5 | Agent | Re-runs its part; the person's deletion stays (the re-run edits only what the agent made and the person didn't touch, AGENTS rule 3) | 0 |
| 6 | Person | Click "N changes" to see who did what | 1 |

### Fix a mix an agent made

The agent delivered a song; the voice is buried and the file is too loud.

| # | Do | Clicks | Keys | Screen |
|---|---|---|---|---|
| 1 | Ctrl+O → pick the song | 1 | 1 | The song; the readout says "Loudness −11.2 · target −14" (amber) |
| 2 | Click "N changes" → read what the agent did ("Agent: Music +4", "Agent: Squeeze on Master") | 1 | | History list (popover) |
| 3 | Click the loudness readout | 1 | | Mixer opens with the loudness curve: the loud stretch is visible |
| 4 | Drag Music's fader down | 1 | | |
| 5 | Click Music strip → right-click → **Duck under ▸ Voice** | 3 | | Music dips under the voice (writer 3, ducking) |
| 6 | Space to listen | | 1 | |
| 7 | **Deliver** → **Deliver** (the agent's last settings are kept: target −14 now passes) | 2 | | Dialog |
| | **Total** | **9** | **2** | 1 dialog |

### A 15-second sting for a logo reveal

The 2D project "Logo reveal" has markers "logo lands" (2.0 s) and "tagline" (9.0 s); the film is 15 s.

| # | Do | Clicks | Keys |
|---|---|---|---|
| 1 | Ctrl+N → **Bring in a picture** (empty-song button) → click "Logo reveal" | 2 | 1 |
| 2 | Settings panel (nothing selected = the song): Length → type 15 s | 1 | |
| 3 | Click marker "logo lands" → L → type "riser" → double-click **Riser** (ends on the marker, writer 3) | 3 | 1 |
| 4 | Double-click **Impact** | 1 | |
| 5 | Double-click **Warm pad** (new track at the playhead; Editor opens) → click 3 notes of a chord | 4 | |
| 6 | Box-select the chord → drag its right end to the song's end (snaps to the end) | 2 | |
| 7 | Click marker "tagline" → double-click **Soft chime** | 2 | |
| 8 | **Deliver** → **Deliver** ("Also give it to the project" is on: 2D's piece gets the sound) | 2 | |
| | **Total** | **17** | **2** |

Screen changes: the picture chooser and the Deliver dialog (2).

---

## 5. Feel

### Drags follow the hand

- **Everything drawn by the screen moves at screen rate** (every frame, ~60 per second): items, ends, fades, the
  selection box, fader knobs, automation points. The screen never waits for the engine while you drag.
- **Sound follows after release**: the engine re-renders the touched stretch after the drag ends (today debounced
  ~300 ms; the target is under 150 ms for a stretch that's on screen). While playing, a moved item is heard at its
  new place from the next block (we don't stop playback).
- **No jump on press**: the grab point is kept (you grab a note in its middle, it stays under the pointer there).
  A press that moves less than 4 px is a click, not a drag (no accidental moves).
- **Faders and knobs**: drag up/down; Shift = fine (10× slower); double-click = back to its default (0 dB, centre);
  the value shows beside the pointer while dragging. Scroll wheel over a fader moves it only while it has focus
  (scrolling the Mixer never changes a level by accident).
- **Long songs**: the arrangement draws only what's on screen; dragging in a 10-minute song with 40 tracks stays at
  screen rate (check after P25's block render).

### Snapping

- **What snaps**: starts and ends of notes, hits, clips, sounds, ranges, markers and section edges snap to — in this
  order of strength — **markers**, **the playhead**, **other items' edges** on any track, **section edges**, **the
  grid** (Grid ▾ in the header: bar, beat, 1/8, 1/16, 1/32, triplets; "Auto" follows the zoom).
- **A thin line shows what it snapped to**, with its name for a marker ("logo lands") or "grid" faint.
- **Ctrl while dragging = free** (2D's key for "no snapping"). **Snap ✓** in the header turns it off for everything.
- **Dropped on a marker = tied to it** (the flag shows; as in 2D). A tie is undone by dragging it off with Ctrl, or
  "Untie" in its More.
- Snapping is magnetic only within 8 px of the target at any zoom, so at high zoom you can still place freely
  between grid lines.

### Multi-select feel

- Moving several items: all move by the same amount; each snaps by its *grabbed* item's edge (the others follow).
- Dragging an end of several: each gets the same change; an item that would become shorter than 1/64 beat stops at
  that length (no flip).
- An action on many is one step and one message ("Quantised 128 notes").

### Keys and focus

- **Five areas take keys**: the arrangement, the Editor, the Mixer, the Sounds panel, the settings panel. The area you
  last clicked has focus; its header shows a thin accent line. F6 moves focus to the next area (proposed;
  Windows' own key for "next pane").
- **Arrows, Delete, Ctrl+A, Ctrl+C/V/D** act in the focused area on its selection (the same items may be selected in
  two areas; the focused one decides what Ctrl+A means).
- **Typing in a field** takes every key until Enter, Tab or Esc; Space types a space there, it doesn't play.
- **Global keys** work anywhere outside a text field: Space, Enter, R, C, K, E, X, L, M, Ctrl+K, Ctrl+Z, Ctrl+S, Ctrl+Shift+E.
- **Esc** goes back one level: closes a popover → clears a box/range → clears the selection → leaves the Sounds panel.

### Hover words

Every icon and every sound word has a hover sentence (after 600 ms, gone on move), plain, with its key:
"M — Mute: silence this track (M S)"; "Loudest peak — the highest point of the waveform. Under −1 is safe for every
platform."; "Squeeze — makes loud and quiet parts closer together (a compressor)."; "Group channel — several tracks
mixed together before the master, so one fader moves them all." The first time a sound word appears in a session it
has a dotted underline. Written once in the operation and field data (their `help`), never per panel.

### Empty states (what each says and offers)

| Where | Says | Offers |
|---|---|---|
| New song (arrangement) | "Start with a sound." | **Add a track** · "or drop a sound, recording or video here" · **Bring in a picture** |
| An empty instrument track (its lane) | "Double-click to open the Editor, or play your keyboard with Rec on." | — (the lane itself is the target) |
| An empty audio track (armed or not) | "Press R to record here, or drop a sound file." | — |
| Empty voice track | "Type what to say in the Editor." | **Open Editor** |
| Editor with nothing selected | "Select a track or something on it to edit it here." | the last edited track's name as a button |
| Editor on an empty instrument track | "Click to add a note. Drag for a longer one." (grid in the song's key) | — |
| Mixer with no tracks | "Your tracks' faders will be here." | **Add a track** |
| Settings panel, nothing selected | the song's settings and "Select a track, a note or a clip to change it here." | — |
| Sounds panel, search finds nothing | "No sound called 'xyz'. Try a shorter word, or add a folder of your sounds." | **Add a folder…** |
| History, no changes | "Changes you and agents make will be listed here." | — |

### Plain errors

- **One sentence: what failed, then what to do.** "The microphone isn't connected. Plug it in or pick another input."
  "This song uses the marker 'drop', which was deleted in 2D. Put it back in 2D or untie the 2 sounds on it."
- **Where:** on the thing that failed (a clip's red outline and its sentence; a Deliver row), and in the top bar's
  message line. Never a silent fallback (AGENTS rule 6): a delivery that can't pass says so and writes no file
  claiming success.
- **Red only for errors.** Amber means "not yet at the target"; green means "fine". Clipping on a meter is red because
  it is damage.
- An action that isn't possible is **absent**, not an error: if Join can't apply, it isn't offered.

### Progress for long jobs

- Clean-up, voice, stems, bounce (later), Deliver, model downloads are **jobs** (the one jobs queue).
- Each shows a progress line **on the item** it works on (a clip fills left to right) and a short line in the top
  bar's message ("Cleaning 2 clips · 40 %"); click it to cancel.
- You keep working while a job runs; the item it works on shows its old sound until the new one lands (one undo step
  when it lands).
- Over 10 s: it says how long is left. Finished: one line ("Cleaned 2 clips") and the sound plays the new version.
- Failed: the plain error above; the old sound stays.

### Names and labels that don't fit (S28 layout check)

- **A name that doesn't fit shortens with "…" and shows whole on hover**, everywhere a name is shown: the track
  header, a Mixer strip, a group header, a clip, the settings panel's title. One name label piece does this for every
  place (today a long track name is simply cut, with no hover, in the track header, the Mix strip and the instrument
  card). F2 renames; the whole name is always in the settings panel.
- **Ruler labels never start outside the ruler.** The first time label ("0 s", "2.4 s") is placed inside the left
  edge; a label that would be cut is moved in or left out, never drawn half (today the first label is cut on both
  rulers).
- The layout check (`main.py --check-layout`, four window sizes, long names included) is run on every screen state
  before a screen change is called done.

### Nothing greyed out

A control that can't be used now is not shown: Record without an armed track, Deliver without sound, Join for clips
that don't touch, the velocity strip without notes, Loop without a range. The data on each operation ("valid when",
"importance") builds the action bar, the menus, Ctrl+K and the settings panel; nothing is hand-hidden per panel.

---

## 6. The key map

"2D" = the same key with the same meaning in Rostrum2D (COMMON.md and 2D's DESIGN.md). "proposed" = not in the
reserved list; the lead decides.

| Group | Key | Does | 2D |
|---|---|---|---|
| **Play** | Space | Play / stop | same |
| | Shift+Space | Play from the selection's start (proposed) | — |
| | Home | Playhead to the start (Enter confirms what has focus) | — |
| | End | Playhead to the song's end (proposed) | — |
| | C | Loop on/off (makes the loop from the time range if one is selected) | — |
| | K | Click (metronome) on/off | — |
| | R | Record on the armed track | **clash in name only:** 2D's R = Rectangle tool (H28 if time). Different apps, no shared screen; keep both (R = record in Logic, Pro Tools, Reaper) |
| **Files and app** | Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S | New / open / save / save as | same |
| | Ctrl+Shift+E | Deliver… | proposed for 2D's Export (same meaning: make the final file) |
| | Ctrl+, | Settings | same |
| | Ctrl+K | Search or run anything | same |
| | Ctrl+F | Find a setting | same |
| | F1 | Help; Help lists every key (proposed) | proposed for 2D too |
| **Undo** | Ctrl+Z / Ctrl+Shift+Z (and Ctrl+Y) | Undo / redo | same |
| **Select** | Click / Ctrl+click / Shift+click / drag a box | Select / add-remove one / the run between / box | same as 2D's layer list |
| | Drag on the ruler (Shift: only selected tracks) | Time range | — |
| | Ctrl+A | Select all in the focused area | same |
| | Esc | Back one level / deselect | same |
| **Edit** | Ctrl+C / Ctrl+X / Ctrl+V | Copy / cut / paste at the playhead | same |
| | Ctrl+D | Duplicate right after | same |
| | Alt+drag | Drag a copy | same |
| | Delete (or Backspace) | Delete; on a range inside a clip, cut it out and close the gap | same |
| | F2 | Rename | same |
| | ← → | Nudge a grid step (Shift: a bar; Ctrl: fine) | same meaning (2D: 1 px, Shift 10 px) |
| | ↑ ↓ | Notes: half step (Shift: octave); clips/sounds: track above/below | same meaning (nudge) |
| | Ctrl+] / Ctrl+[ | Move selected tracks down / up | same ("order") |
| | Ctrl while dragging | No snapping | same |
| | Shift while dragging | Only in time | same meaning ("straight") |
| **Notes and hits** | Q | Quantise | — |
| | Ctrl+↑ / Ctrl+↓ | Transpose by a scale step in the key (proposed) | — |
| **Clips** | Ctrl+T | Split at the playhead | — |
| | Ctrl+J | Join | — |
| | Ctrl+B | Bounce the range to audio (proposed; later, §9) | — |
| **Groups** | Ctrl+G | Tracks: send to a new group · clips/sounds: layer as one sound | same meaning ("group") |
| | Ctrl+Shift+G | Ungroup / unlayer | same |
| **Tracks** | Shift+M / Shift+S | Mute / solo the selected tracks (proposed) | — |
| **Panels and view** | E | Editor | — |
| | X | Mixer | — |
| | L | Sounds panel | — |
| | A | Show automation of the selected track | — |
| | F6 | Focus the next area (proposed) | proposed for 2D |
| | Ctrl+= / Ctrl+− / Ctrl+0 | Zoom in / out / fit the song | same |
| | Z | Zoom to the selection | — |
| | Ctrl+wheel / Shift+wheel | Zoom at the pointer / scroll in time | same |
| **Markers** | M | Marker at the playhead (name asked inline) | proposed for 2D's "Add marker" (same meaning) |

**Clashes found**
1. **R** — Sound: record; 2D: Rectangle tool. Not in one app; keep, noted for the lead.
2. **Ctrl+↑/↓** — I use it for "transpose in key"; it must not also mean "fine nudge" (fine nudge is Ctrl+← → only,
   which has no vertical meaning). No clash inside Sound.
3. **Alt+arrows** — 2D: previous/next drawn frame. Sound leaves Alt+arrows **unused** on purpose, so a 2D habit never
   moves notes by surprise. (DESIGN.md §5 proposed Alt for fine nudge; changed to Ctrl for this reason.)
4. **Enter** — global "to start", but in a field or the Sounds panel it confirms / adds. Focus decides (§5). Home is
   the alias that always means "to start".
5. **X vs Ctrl+X**, **K vs Ctrl+K**, **A vs Ctrl+A**, **E vs Ctrl+Shift+E**: different keys, no clash; mentioned
   because a slipped Ctrl changes the meaning — each plain-letter key only opens or toggles something, never deletes,
   so a slip is harmless.
6. **DESIGN.md §5 used "Shift: free" for drags**; changed to **Ctrl = free** to match 2D. Shift = "only in time".

**Keys settled by the lead** (the table above, with these changes): Home = playhead to the start (Enter confirms or
does the obvious thing for what has focus) · Shift+M / Shift+S mute / solo the selected tracks · Alt+M /
Alt+Shift+M next / previous marker · Ctrl+↑ / Ctrl+↓ pitch the other way (notes: a scale step; clips: pitch only,
a half step) · V Select and B Draw in the Editor (2D's keys) · hold H to hear the original of a cleaned clip · T next
take · S swap a placed sound · P make a part (when parts arrive) · , and . step a picture frame · Ctrl+] / Ctrl+[
track order · R arms the selected track when none is armed, then records · F1 Help (lists every key) · Ctrl+H
History · Ctrl+B Bounce (later) · Shift+Delete delete and close the gap on that track. Alt+arrows stay unused.

---

## 7. Gap table against today

What exists now (2026-10-22, team/priyam after P26), what this spec adds, and what it needs. **Status:** exists ·
partial · missing · blocked. "Kit" = the shared GUI kit (Team Hem / Team Sam); "schema" = a new song-file field
(Team Sam); "engine" = the Rust sound engine.

| § | Feature | Today | Status | The spec adds | Needs |
|---|---|---|---|---|---|
| 2 | One workspace (arrangement, Editor / Mixer dock) | Three pages; the piano roll has the middle, the song is a strip | missing | Dock, E / X, no pages | screen |
| 2 | Mix page at 1280×720 / 1366×768 (S28 #1) | Render was hidden under Listen; **fixed for now in P26**: Listen gives way, Render pinned, the card scrolls | partial | Delivery moves to its dialog | screen |
| 2 | Long track names (S28 #2) | Cut with no hover in the track header, the Mix strip and the instrument card | missing | Names shorten with "…" and show whole on hover, everywhere a name is shown (one name label piece) | screen (kit hover label) |
| 2 | First time label on the rulers (S28 #3) | "2.4 s" cut at the left edge of both rulers | missing | Labels start inside the ruler; the first one never cut | screen (kit ruler if shared) |
| 3.0 | Selection and actions | Single selection; one-item drag; Ctrl+K for one item | partial | Multi-select, box, ranges, action bar, right-click, clipboard, nudge | kit selection list; screen |
| 3.1 | Songs, tracks, parts | New song; + Track with 8 kinds; rename / colour in the inspector; `bus.from_tracks` | partial | Sounds panel first; reorder, duplicate; groups that fold; parts | `part` (schema); `track.duplicate`, track order (new) |
| 3.2 | Instruments | Picker on cards / inspector; plug-ins load; voices on cards only | partial | Audition on your notes, swap without loss, saved sounds | `render_audition` (new); engine auditions |
| 3.3 | Notes and the piano roll | Click adds, one-note drag, quarter-beat snap | partial | Select / Draw tools, box, ends, velocity strip, grid menu, key shading, ties shown | kit selection; screen |
| 3.4 | Drums | Drum rows; click adds a hit; one synth kit | partial | Paint, accents, patterns ×N, swing, per-drum settings | `swing`, `drums` (schema); a free SFZ kit (decision) |
| 3.5 | Playing in | MIDI keyboard on arm; count-in, punch | partial | Play the selected track without arming; computer keyboard; overdub / replace; MIDI files on screen | live transport opens MIDI on select |
| 3.6 | Tempo, key, metre, sections | Tempo / key / sections in a popup and on the ruler | partial | Song in the settings panel; tempo fit to a marker; ramps; section ripple / duplicate | `ramp` (schema); `tempo.fit_bar`, `range.insert/remove`, `section.duplicate` (new) |
| 3.7 | Sounds panel and library | Library panel built but never shown; search in the engine | missing | One panel for every kind of sound, audition, aligned drops | engine auditions |
| 3.8 | Recording | Arm, meter, count-in, punch, hear input, a take as one clip | partial | Take stacks, choose / combine takes, input per track, several tracks, calibration button | `stack`, `input` (schema); `take.choose`, `take.flatten` (new) |
| 3.9 | Editing audio clips | Ops exist (split, join, crossfade, normalise, move, duplicate); screen moves one clip | partial | Edges, fades, stretch corner, level line, seam handle, drop files, slip, reverse, close gaps | `reverse`, clip length ties (schema); `clip.remove {close}`, `clip.close_gaps` (new) |
| 3.10 | Clean-up | Fields, job, cache, models, download question, "Make cleaned take" bar | partial / blocked | Several clips at once, made on release, Before / After (H), measurement line | the isolation model upload (NEEDS_DECISIONS 7); the installer's `cleanup` extra |
| 3.11 | Voice-over and spoken lines | Recording as 3.8; lines through ops and `render_voice`; cards on the Instruments page | partial | Type lines on the lane, made on finish, take arrows, level the voice, normalise by loudness | `clip.normalize {by: loudness}` (new) |
| 3.12 | Picture and markers | Picture corner; markers drawn (shared dashed); follow on rename; loud on delete | partial | Floating picture panel, M + name, Shared switch, problem chip, tempo fit, frame step | `marker.add {shared}`, `tempo.fit` (new); kit problem chip |
| 3.13 | Sound design for motion | Designed sounds in the file and engine; sounds from motion | partial | A screen for designed sounds; aligned drops; Swap; motion from the picture | `clip.swap`, `group` on sounds (schema) |
| 3.14 | Effects and plug-ins | Chains on tracks, groups, master; plug-in windows; clip effects only in the file | partial | Effects on any selection, reorder, missing-plug-in rule | `effect.move` (new) |
| 3.15 | Groups, sends, routing | Buses, sends, Output picker; "+ Group channel" (empty first) | partial | Ctrl+G from tracks, groups drawn as headers that fold, ungroup, share a reverb, loops refused at the operation | `bus.release`, `send.to_new_bus` (new) |
| 3.16 | Ducking | Ducks drawn; "+ Duck" per strip | partial | Duck the selected tracks under a voice or a group | duck under a group (engine) |
| 3.17 | Automation | Lanes for many settings; opened by "Auto" | partial | A key, ◇ in the settings panel, several points at once | kit ◇; `curve` (schema, later) |
| 3.18 | Mixing and loudness | Strips, faders, meters, loudness live, curve, Listen pictures (a page) | partial | Mixer in the dock, top-bar loudness, Check with Select / Play | screen |
| 3.19 | Export and delivery | Format, rate, trim, stems, versions, pass / miss after render — on the master strip | partial | Deliver dialog, range, groups-only stems, pass / miss before, cancel, bounce, "For the Editor" | `render_mix {from, to}`; `edit_bounce` (new); HANDOFFS stems (Team Sam) |
| 3.20 | Undo, history, versions | One history with who; per-person undo; change count | partial | History list with folded agent turns, Keep / Undo all, named versions | kit History panel; `version.save` (new) |
| 3.21 | Files | New, open, recent, save, untitled per change, recovery, Lull sample (P1 fixed) | mostly exists | Move into a project, find missing media | `edit_relink_media` (new) |
| 3.22 | Settings, help, guides | Settings, Help with guides, About | partial | Test tone, measure delay, plug-ins group, key list, first-run card, hover help on rows | kit hover help, key list |
| 3.23 | Working with an agent | Connect dialog; live edits with who; re-runs keep the person's edits | partial | Flash of agent changes, Copy for an agent, `inspect_selection`, `edit_undo`, Agent activity | shared core tools |

---

## 8. What the spec needs

**Operations that exist today and take a list of ids** (built in P26 or before): `note|hit|clip.move`,
`note|hit|clip.duplicate`, `note|hit.quantize`, `note|hit.humanize`, `note.transpose`, `clip.split`, `clip.join`,
`clip.crossfade`, `clip.normalize`, `clip.split_stems`, `bus.from_tracks`, every `.set` / `.remove`, `effect.add`
on tracks / clips / groups / master, `<kind>.add_many`, `marker.add` / `marker.set` / `marker.follow`,
`section.move`, `automation.set`, `duck.add`, `send.add`; jobs `render_mix`, `render_cleanup`, `render_voice`.

**New operations** (Sound's own, built by Team Priyam): `track.duplicate` · track order (`track.move`) ·
`sound.move` / `sound.duplicate` · `line.move` / `line.duplicate` · `section.duplicate` · `range.insert` /
`range.remove` (moved up from "later": sections ripple on them) · `clip.cut_range` · `clip.remove {close}` ·
`clip.close_gaps` / `line.close_gaps` · `clip.normalize {by: loudness}` · `clip.swap` · `take.choose` /
`take.flatten` · `tempo.fit_bar` · `marker.add {shared}` / `marker.unpin` · `effect.move` · `bus.release` ·
`send.to_new_bus` · `note.split_chord` · `voice.sample`. Jobs and tools: `render_audition` (a sound or instrument
heard on the selection without touching the song) · `render_mix {from, to, stems: "groups"}` · `edit_bounce` ·
`edit_picture_sound` · `edit_sounds_from_motion {item}` · `run_calibrate` · `edit_relink_media`.

**New song-file fields — one batched request to Team Sam** (each has an interim behaviour in its section, none blocks
the screen work): `part` on notes and hits · `stack` on clips (takes) · `swing` / `swingGrid` on tracks · per-drum
settings `drums` on tracks · `ramp` on tempo changes (and linear tempo segments in the engine contract) · `input` on
tracks · `reverse` on clips · `group` on designed sounds · length ties `{"to": "#marker"}` on clips and sounds ·
`curve` on automation points (later) · metre changes (later).

**Shared core and kit** (requests, exact wording in the sections): the selection as a list and `inspect_selection` ·
box and range selection in the timeline · item handles on timeline blocks (edges, corners, level line, seam) · the
action bar and right-click menu fed by the one action list (2D's from H28, reused, never a second copy) · an inline
value field in the action bar (names, semitones, a bar number, a target) · a tool state per editor (Select / Draw) ·
a "trying" state for a field (audition without a history entry, Esc puts back) · a banner for key-taking modes · a
colour swatch palette shared with 2D · a problem chip in the top bar · one marker look and marker row for both apps
· an audition service through Sound's engine · the History panel (folded agent turns, Keep / Undo all, highlight) ·
"Undid: / Redid:" wording · ◇ on automatable settings · hover help on every settings row · a job chip in the top bar ·
a key list page built from the command list · `edit_undo`, `version.save` / restore, an agent call log · drag
modifiers as a kit rule (Ctrl no snap, Alt copy, Shift constrain) · a name label that shortens with "…" and shows the
whole name on hover (S28 #2).

**Engine:** auditions through the engine, not Qt Multimedia (STATUS gap 2) · a swapped sound picked up without
restarting playback · live gain during a fader drag (heard before the re-render) · a duck that listens to a group ·
range renders (`from` / `to`; cheap now the mix renders in blocks) · plug-in crash containment (see §10).

---

## 9. Later

Deliberately not in this round, with one-line reasons. (Writers 1–3 list their own; the lead merges.)

| Later | Why it can wait |
|---|---|
| **Parts** (a named block of notes you grab as one; `part.make`) | Needs a schema field (Team Sam); every job works on note selections and time ranges now (DESIGN.md §1). Add if people miss blocks. |
| **Bounce to audio** and **Deliver this range** | Need the range render (`render_mix {from, to}`); the block render (P26 B) makes it cheap. Ctrl+B is reserved. |
| **Delete time / insert time across all tracks** (`range.remove`, `range.insert`) | Not needed for the eight jobs; Delete on a range inside one clip (job C) covers the common case. |
| **Voice edited by its words** (a transcript under recordings, Descript-style) | Needs ASR on recordings, analysed once and stored; next brief (DESIGN.md §7.3). The waveform with cut-and-close-gap carries job C. |
| **Short cuts for platforms** (a 30 s / 15 s version of a song, job H) | Needs range render plus a "cut-down" tool; job H's loudness versions work now in Deliver. |
| **Select similar** (same pitch / velocity / colour), saved selections | Ctrl+A, box and Shift-runs cover the jobs. |
| **Automation curve shapes** between points | Straight lines carry the jobs; shapes are a refinement. |
| **Tool modes** (pencil, scissors) | Rejected for now (§3.0); revisit only if people ask. |
| **Paste at original time** (Ctrl+Shift+V) | Paste at the playhead plus Ctrl+D covers the jobs. |
| **Touch / pen gestures**, a pinch to zoom | Windows laptop with a mouse first. |
| **Picture's own sound** (play the video's audio) | Job G needs it: import the video's sound as a clip is the first step; playing it live with the picture is later. |
| **5.1 / Atmos** in Deliver | PLAN: stereo first. |
| **Customisable keys** | One fixed key map shared with 2D first; a person can't break family habits by accident. |
| **A keys overlay** (hold a key to see all shortcuts) | Help › Keys lists them; the overlay is polish. |
| **Undo per author** ("undo only the agent's last change") | One history with who-did-what covers job F; per-author undo needs care with dependent edits. |

**Also later, from the feature sections:** swiping across takes to combine them (3.8: one-click take choice and cut
at the playhead come first) · points on a clip's level line (3.9) · AI-made sound effects (3.13, licence rule) ·
free online libraries as optional connectors with their licences shown (3.7c) · recording automation by moving a
fader while playing (3.17) · a plug-in in its own process so a crash can't touch the engine (3.14, see §10).

---

## 10. Open points, settled by the lead

| # | Point (from the parts) | Settled |
|---|---|---|
| 1 | **Clean-ups and speech made automatically** (on releasing the slider / finishing a line) or by a button | **Automatically**, once, kept and reused (rule 7). One job at a time, newest wins, progress on the item, Esc cancels. Voice isolation (about 2 GB of memory) asks once per session when memory is short. Today's "Make cleaned take" bar goes. |
| 2 | **Arming a track:** in the song file or screen state | **Screen state.** An agent's re-run must never disarm a person, and arming is not part of the song. |
| 3 | **A missing plug-in** | Play and Deliver **stop** at it, saying which plug-in and where, until it is switched off (one click). Preview ≡ export, fail loudly. |
| 4 | **A crashing plug-in** | Plug-ins run inside the engine today, so the honest text is: "The sound engine stopped and was restarted; nothing was lost" (P2's restart, logged). A separate plug-in process is later. |
| 5 | **Song-file fields** (`part`, `stack`, `swing`, `drums`, `ramp`, `input`, `reverse`, sound `group`, clip / sound ties, `curve`) | **One batched request to Team Sam** (§8). Each feature works in its interim form until then. |
| 6 | **`range.insert` / `range.remove`** | Moved from "later" to the next Sound operations brief: section ripple, duplicate and delete-with-music stand on them. |
| 7 | **Click in the piano roll** | A click selects or deselects; **Draw (B)** or a double-click adds a note. Changes today's behaviour; said in the release notes. |
| 8 | **The MIDI keyboard** | Plays the selected notes / drum track at once, without arming; arming is only for recording. |
| 9 | **Chord notes** (a note whose pitch is a list) | The screen writes separate notes. A list-pitch note (an agent's) is drawn as linked bars that move together, with "Split into notes" (`note.split_chord`). |
| 10 | **Stems for the Editor vs `shared\HANDOFFS.md`** | Deliver gets **"For the Editor"**: 32-bit float, full length, no trim, no loudness change, stems by group (groups named Dialogue / Music / Effects give the HANDOFFS split). Needs Team Sam's agreement on the shared contract. |
| 11 | **Loops in routing** | Refused by the operations themselves (`bus.from_tracks`, `track.set {output}`, `bus.set {output}`), naming the loop; the screen never offers one. |
| 12 | **Groups drawn as headers** | A view only: member tracks are drawn under their group, the song's track order is untouched. |
| 13 | **Ducking under a group** | Until the engine can listen to a group, the screen expands the group into its tracks and says so. |
| 14 | **Fader feel while playing** | Live gain during the drag is wanted (engine item, §8); until then the change is heard after the ~0.3 s re-render. |
| 15 | **A swapped sound while the range loops** | Promised only once the live transport can take a new render without restarting; until then Swap restarts the loop. |
| 16 | **A video's own sound** | Imported as a clip first (job G), through what Sound already ships for reading video; playing it live with the picture is later. |
| 17 | **Only one drum kit ships** (the synth kit) | **DECISION for Sam** (priority, not taste): ship a vetted free SFZ drum kit download sooner, so drums don't sound the same in every song. Recommended: yes. |
| 18 | **The voice model's size** in the download question | Read from the installed model when the text is written; no placeholder numbers on screen. |
| 19 | **Versions marked by renders** | The render's record notes the history point, so History shows "Delivered v003" (small, in `handoff.py`). |
| 20 | **Key clashes** | Settled in §0 and §6. R = Record in Sound and Rectangle in 2D: kept, the apps never share a screen. |

---

## Appendix A. The first design round (kept for its walks and counts)

*Written before this spec; that round's structure (its §4) became §0–§2 here. Pictures: `C:\Users\Sam\.rostrum\waves\results\sound-redesign\p26\before\`.*

### A.1 The six jobs, step by step (first round)

Each step: what the person is thinking · what they need on screen · what they don't need then.

#### A. Write a song from scratch (parts, instruments, notes)

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

#### B. Score a video to picture and its markers

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

#### C. Record a voice-over and clean it up

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

#### D. Design sound effects for motion

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

#### E. Mix to delivery loudness

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

#### F. An agent builds a cue while a person tweaks it

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

### A.2 Today's screen, walked and counted (first round)

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
