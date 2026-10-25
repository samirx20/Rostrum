# Your first song

For a person using the RostrumSound app. This page takes you from an empty song to something you can hear and export.

## The screen in one look

- **Top bar:** **≡** (the menu), the song's name, **Search** (Ctrl+K: every action that fits now, every key on the Keys sheet, every setting of what is selected and every entry of the ≡ and Help menus; a word that starts a name finds that name first, and a word that only appears in a description never adds a track or group), the **loudness chip** (in words with a dot:
  "Ready for streaming" in green, "Quieter than streaming wants" or "Louder than streaming wants" in amber, or "… the
  target …" when the loudness target is not streaming's −14 LUFS ("Quieter than the target wants"); rest the pointer
  on it for the number, click it to open the Mixer, which shows the same with its curve) and **Export** (both once the
  song makes a sound), and **?** (help).
- **Middle: the arrangement.** Every track is a row over time. Its header strip holds **+ Add**, then the transport, always
  there: ⏮ (to the start), ▶ (play / stop, the one blue button), the loop button, **Record** and the metronome; then
  the position ("3.2  0:04.80": bars.beats, then the time; click it and type **5.3** or **9.6 s** to jump there; a beat the bar does not have, like 5.9 in 4/4, is refused with the reason), and the song's tempo, beats and key as fields; **Grid ▾**, **Snap**, zoom − + and **Fit** sit at its right. The ruler counts **bars**: plain numbers, one per
  bar. For a seconds scale, right-click the ruler and choose **Show seconds** (the same entry hides it).
- **Under it: the dock.** **Editor** (E) shows the selected track up close; **Mixer** (X) shows the faders. ▾ folds
  it away.
- **Right: the settings panel.** It shows what is selected, or the song when nothing is. Times there read in
  **bars.beats**, like the ruler: At **5.3** is bar 5, beat 3 (**5.3.2** when it falls a sixteenth into the beat: the
  sixteenths are 1 to 4), and a Length is in words (**1 beat**, **2 bars 1 beat**) or a note value (**1/8**, **dotted 1/4**)
  when it is one. Hover the label for the seconds. Type `5.3`, `5.3.2`, `5` (a bar), `1 bar 2 beats`, `1/8`, `9.6 s` or
  `0:09.6` (the old `5.3.480` in ticks and `0.2` for a length still work); it is stored the way the item was written (beats stay beats,
  seconds stay seconds, a marker time stays on its marker). A pitch reads as a note name (G4); type G4 or a number.
- **Left: the Library** (Ctrl+L), where every track starts from a sound.

## 1. Start a new song

Open **≡**, then **New** (Ctrl+N). It is called "Untitled song" and lives in your projects folder.

Saving is automatic: every change is on disk as you make it. There is no Save button and nothing to lose. Ctrl+S
(**≡ › Save a version**) saves a named version you can go back to from History. (The song's own file is brought fully up to date when
you close the window and every 20 changes; the change log beside it always has the latest, and opening the song plays it.)

## 2. Add a track

1. Click **Add a track** in the middle of the empty song, **+ Track** under the last track, or **+ Add › Track with a
   sound…**. You can also press **Ctrl+L**. The **Library** opens on the left.
2. Type to search ("warm", "bass", "voice"), or click a chip: **All**, **Instruments**, **Drums**, **Mic and files**,
   **Voice**, **My sounds**.
3. Click a row to hear it (on a track with notes selected, it plays those notes; a click only previews and never changes a track), then press that row's **Add** (or select it and press **Enter**). A new track with that
   sound appears, selected, the preview stops, the Library closes and the **Editor** opens under the arrangement.
   - **Microphone** makes a track that is ready to record (see [recording.md](recording.md)).
   - Click a voice and the footer says why there is nothing to hear: a voice is made from a line you type, so add it,
     type a line, then press Play. Voice rows have no preview.
   - **+ Add › From a file…** (Ctrl+I) brings in a sound file (a new track with the file at the playhead), a MIDI file
     or a video. A sound file is copied into the song's folder (`media`), so the song carries it when you copy or
     move the folder, and nothing is raised under **Problems**.
   - **Add** always makes a new track; clicking a row never changes one. To give an existing track another sound, use the **Sound ▾** picker in its settings panel: it lists every sound the track's content can use (a notes track: the recorded instruments first, then the synth presets, the synth, the modelled instruments and, last, the classic synthesized voices; an empty track: any sound, a voice or a kit too; a drum track: the three kits, Rock, Studio and Classic). The notes stay, and the track's name follows the new sound unless you renamed it. An agent does the same with `track.set {sound: "builtIn:warmPad"}` (also `"builtIn:piano"`, `"synth"`, `"model:guitar"`, `"kit:studio"`, `"voice:ryan"`). A plain instrument is a recorded one and plays like a person would by default (the track's **Feel** group: **Played like a person** off plays every note exactly as written; **Swing** makes
   every second 8th or 16th come late without moving the notes; see `writing-parts`). If its sample pack is not installed yet, playing says which one and how to install it (Library: `inspect_library (kind: packs)` and `run_model_install` for agents).
4. The Library closes after each use. Close it any time with ×, Ctrl+L or Esc (while a preview plays, the first Esc stops it).

## 3. Shape the sound

Select the track (click its name). The settings panel shows only the settings that apply to its instrument. A
plucked string, for example, shows Position and Damping. Change the instrument there at any time; the notes stay.
The **Colour** row shows the colour the track is drawn in.

## 4. Write notes

1. With the track selected, the **Editor** shows its notes beside a piano keyboard, framed so every note is in view
   (drums: a row per drum; recordings: their waveform). Each octave's C is labelled (C4 is middle C); **click a key
   to hear it** on the track's own instrument, or drag down the keys to play each one. The track's name, **Select** /
   **Draw** and **Note ▾** sit on the dock's top line, beside the Editor / Mixer tabs.
2. **Double-click** empty space to add a note (on a drum grid: a hit on that drum's row). Or press **B** for the
   **Draw** tool: then every click adds a note or a hit; **V** goes back to **Select**. A new note or hit goes in the
   grid cell under the pointer: a click anywhere after a grid line, up to the next one, starts it on that line.
   **Note ▾** sets how long a new note is. Its menu, headed "Note length", lists One grid step, Bar, 1/2, 1/4, 1/8, 1/16 and 1/32, with a tick on
   the current one (1/4, a quarter, at first). With **Draw**, drag on after the click to set its
   length: the note ends on the grid line nearest the pointer (drag two beats, it is two beats long). The click and the drag are one step ("Draw note"), one **Ctrl+Z** takes it away. A new note is selected,
   so the settings panel shows it. Clicks in the roll never move the playhead (the ruler does), and the roll never
   scrolls by itself after an edit: only you move the view. A click on the ruler puts the playhead on the nearest
   grid line, marker or section edge (with a picture: the nearest frame on the seconds line). Hold **Ctrl** to put it
   exactly where you click.
   Drag a note to move it in time and pitch, or its right end to make it longer or shorter (the pointer shows ↔ over
   the note's last few pixels; every selected note changes by the same amount), or its left end to move where it starts
   (its end stays put). Neither end makes a note shorter than one grid step (Ctrl: no snapping, then down to 20 ms). A click just past a note's end is
   empty space, so with **Draw** you can write notes on one key back to back.
   - It snaps to the nearest grid line. **Grid ▾** in the arrangement's header strip sets the step: **Auto**, ticked
     at first, follows the zoom (the button reads the step it is on: "Grid Auto · 1/8"), never a step narrower than 8 pixels on screen (beats or bars when zoomed out, finer as
     you zoom in); or Bar, 1/2, 1/4, 1/8, 1/16, 1/32, triplets (the current one is ticked); **Snap** switches snapping off and on. Hold **Ctrl** while dragging to drag
     without snapping once.
   - Hold **Alt** to drag a copy.
   - Hold **Shift** to move it only in time.
3. **Select several:** Ctrl+click adds or removes one, Shift+click takes everything between, and dragging across
   empty space draws a box (in the arrangement it takes what it touches on every track it crosses). **Ctrl+A** selects all, **Esc** clears.
   A key on a mixed selection acts on the part it can: after Ctrl+A, **Q** quantises the notes and drum hits, ↑ / ↓
   and Ctrl+↑ / Ctrl+↓ move the notes, and the step in History names them ("Quantise · 178 notes and 202 drum hits").
4. **The settings panel** on the right names the selection ("5 notes") and shows its actions first, as buttons, such
   as **Quantise** and **Transpose**, each always in the same place. A button with a small **▾** beside it (Quantise ▾,
   Humanise ▾) runs at once with the amounts you used last; its **▾** opens a small box of amounts. While it is open
   every change plays straight away on the notes; **Enter** or a click away keeps it as one undo step, **Esc** puts
   everything back. **Humanise** loosens the selected notes a little (writes it into them): its **▾** sets how much,
   timing in milliseconds, velocity and length, and **Another take** gives a new result with the same amounts.
   **Quantise ▾** has **Swing** too: the off-beat grid lines move late and the notes snap to them (to swing a whole
   track without moving its notes, use the track's **Feel**). **Transpose ▾ › By…** moves the selected notes any number
   of half steps; with **Along the key** on, by steps of the song's key (a third, a fifth), so they stay in the key. The less used ones sit behind **› More** under the
   fields (a clip has **⋯** at the end of its button row instead); when only those fit, there is no row: use right-click or **Ctrl+K**. There is no bar floating over the arrangement: the
   actions live there. **Right-click** is a short menu: Cut, Copy, Paste, Duplicate, Repeat… (on notes, hits and clips), Delete, and for tracks Group,
   Move up / down, Lock and Rename; on an audio clip also Split here, Fade in to here, Fade out from here and Swap…. On empty lane space it offers Add track…, Paste here, Add marker here and Select all on this
   track; on empty space in the Editor, Add note here (a hit on a drum row), Paste here, Select all on this track and Select every C4 (that key); on notes and hits it adds Quantise, Humanise and Transpose ▸; on a marker's flag, Rename, Delete, Put a sound here and Start a bar here…; on a lane's point, Delete point; on either ruler, Add marker here, Make a section from here (it starts on the grid line nearest the pointer, as a range drawn on the ruler does) and Show seconds. **Ctrl+K** finds every action by
   name, every key on the Keys list (Ctrl+/; "nudge" finds the arrow keys): export, undo, Preferences, snapping, zoom, History, the Library, the playhead and markers, Guides, tempo and the grid;
   a setting of what is selected by its name ("velocity", "volume": Enter jumps to its field in the settings panel) and the selected track's lanes
   ("automation", "sustain": Show the Volume lane, Playing lane: Sustain). An action that can't run right now says why instead ("paste" before a copy:
   "Nothing to paste yet: copy something first"). The same keys
   work from the keyboard: **End** moves the playhead to the end of the song, **Alt+M** / **Alt+Shift+M** to the next / previous marker, **Ctrl+↑ / Ctrl+↓** move
   selected notes one step along the song's key (the message line says so if the song has no key yet).
5. **Keys on the selection:**
   - Copy, cut and paste: **Ctrl+C**, **Ctrl+X**, **Ctrl+V**. What you copy stays until you copy something else, in every song you open, so you can paste it into another song (a clip's sound is copied into that song's own media folder). Duplicate: **Ctrl+D**. **Repeat…** (**Ctrl+R**) copies the selection or the time range several times in one go: choose how many, or *Until* the end of the section or the next marker. Delete: **Delete** (on a group: the group goes, its tracks stay and play where the group played to; one Undo brings it back).
   - In the Editor, drag a drum hit **up or down** to move it to another drum row (Shift: time only); dragging sideways still moves it in time.
   - **A time range:** drag on the ruler's thin top band. Each end goes to the grid line nearest the pointer. The settings panel offers **Make a section**, **Select
     inside** and **Repeat…**; Ctrl+D duplicates it. With both a time range and selected notes, Ctrl+D acts on **the one you made last**:
     drag a range after clicking notes and Ctrl+D repeats the whole stretch; click notes after drawing a range and it
     copies just those notes. **Shift+Delete** (**Cut out and close the gap**) cuts the range out of the clips under it and closes the gap.
   - Arrows nudge in time; ↑ / ↓ move notes a half step (Shift: an octave). The selection moves as one block: when
     ← would take its earliest note before the start of the song, it stops at the start, and once there the message
     line says "Already at the start of the song".
   - **Q** quantises. **Ctrl+T** splits a clip at the playhead and **Ctrl+J** joins clips.
   - **Ctrl+G** puts the selected tracks into a group. **Ctrl+]** and **Ctrl+[** move the selected tracks up and
     down the list.
   - **Shift+M** mutes the selected tracks and **Shift+S** solos them.
   - **M** puts a marker at the playhead, its name box open: type a name and press Enter, or Esc to keep "Marker 2" (Ctrl+Z takes the marker away). With a marker already at the playhead, M selects that one and says so instead of adding a second. Paste here and Add marker here land on the grid line under the pointer while Snap is on.
6. Zoom with **Ctrl + wheel** and scroll in time with **Shift + wheel**. **Fit** (Ctrl+0) shows the whole song. An
   edit that makes the song longer or shorter never moves the view: the bars stay where they are under the pointer
   (after a delete, empty room shows past the end), and **Fit** is lit only while the whole song is in view.
7. A mistake? **Ctrl+Z** undoes it (**Ctrl+Shift+Z** redoes). Every drag is one step.

## 5. Play it

- **Space** plays and stops. **Home** (or ⏮) goes to the start.
- The **metronome icon** beside play turns the click on and off (**Shift+K**); it is lit while on. It is only for you while you work; it is never in an export.
- The **loop button** (**Shift+L**) is always there. It loops the time range on the ruler; with no range drawn it
  makes one first: the selection's span, else the bar at the playhead and the next three. The loop shows as a solid
  blue band on the ruler's top strip, with the track lanes under it (only the lanes, not the empty space below) shaded and edged to match; drag either edge to change it, double-click the band to clear it (that also
  ends the loop).
- Click the ruler to move the playhead there. A click on empty space in the arrangement clears the selection and
  makes that track the Editor's, but never moves the playhead; only the ruler (and Play) does.
- Each track's header shows a small picture of what it holds (keyboard: notes, drum, waveform: sound files,
  microphone: voice) and its name (double-click it to rename; hover it to see a long name in full), then four
  buttons that never move, whether the track is selected or not: **R** gets it ready to record (absent on a voice
  track, which is typed, not recorded), **M** mutes it, **S** plays it alone, **A** opens its automation lane. The lane's head names what it draws ("Volume ▾"): open it to draw another lane of that track (pan, a send, an effect's setting). A volume lane reads in dB like the Mixer ("+2.1 dB", "−∞ dB" at silence); the song keeps the level as gain.
  Selecting a track only tints its row. Under them a thin bar shows how loud the track was in the last render (green,
  amber near 0 dB, red over). When rows are short the header is one line. To lock a track (nobody can change it,
  agents included) right-click it and choose Lock, or press Ctrl+Shift+L; a locked track shows a small padlock by
  its name. A track's volume is set in its settings panel or the Mixer, not on the header.
  **Drag a header** up or down to move the track: a line shows where it will land, above or below the row under the pointer. Dropped on a group's header, the track joins that group; dropped between tracks it takes the group of the track it lands beside, or leaves its own group when that one has none. The selected tracks go together; one Undo undoes the drop. A **group's header** works like a track's: double-click its name or press **F2** to rename it in place, right-click for its menu (Rename, Ungroup …).
- After an edit the sound is prepared again in a moment, so playback follows what you changed.

## 6. Tempo, beats and key

A typed tempo outside 20–400 bpm is refused ("Tempo is 20–400 bpm"), never changed to the nearest.

- The song's **tempo**, **beats per bar** (4/4, 3/4 …) and **key** are the three fields in the arrangement's header
  strip, and they show what plays at the playhead. Type the tempo or drag it (while you drag, the ruler follows at
  once and the notes when you pause or let go); pick the beats and the key from their lists. Nothing has to be
  selected first.
- With nothing selected, the settings panel is titled **Song** and lists only the song's changes, never the first
  tempo, time signature and key (those are edited in the top bar's fields above, once): **Tempo**, **Time signature**
  and **Key** (each shown once it has a change), **Sections** and **Markers**, then the song's **Length** (a picker: **Until the
  last sound**, the default, or a number of bars: playback and the playhead stop where the sound ends, with its tail; the ruler keeps
  room to write in) and **More**. With a number of bars, **Ring out** (right under **Length**, on at first) lets what still
  rings at the end (a held chord's release, a cymbal, an echo) die away before the song stops (agents: `doc.set` `ringOut`).
  Switch it off to stop at the length; then **Soft end** appears below it (on at first) and fades the last tenth of a second so the stop has no
  click; switch that off too for a dead stop (`endFade`). Every change is a row ("Bar 5 · drop", its value at the right): click a row and the
  playhead jumps there and the change is selected, so the panel shows its settings (Delete removes it). A time
  signature change has its own picker in its row: pick 6/8 there and it changes in one step (one Ctrl+Z takes it back).
- Under each list, **+ Tempo change**, **+ Time signature change**, **+ Key change** (once the song has a key), **+ Section** and **+ Marker**
  add one at the playhead. A new change starts at what already plays there and is selected, so you change it at once
  (pick 6 and 8 for a 6/8 bar). A **+** is there only where it makes sense: not at the very start (that is the song's
  own tempo and time signature) and not where one already sits.
- A new section is named for its next musical role (intro, verse, chorus …); rename it in the settings panel.
- Changes sit on the ruler as small flags: "♩ 132" for a tempo, "3/4" for a time signature, "D minor" for a key.
  Drag a flag to move it (one undo step). Click one and the settings panel shows it. A tempo flag has **Bpm**, **At**
  and **Glide to next**: turn that on and the tempo speeds up or slows down evenly to the next change instead of
  jumping; its flag then reads "♩ 100 ↗" (or ↘ when slowing). Time signature changes start a new bar at that place;
  the ruler's bar numbers follow them. Add one with **+ Time signature change** in the song's panel: it lands on the bar
  line nearest the playhead (an agent's `meter.add` off a bar line is refused, naming the bars on either side); the header's time signature sets the one playing at the playhead (the song's own before the first
  change).

## 7. Get it out

**Export** in the top bar (Ctrl+E) opens the Export sheet on the right. See [exporting.md](exporting.md).

## Finding your song again

- **≡ › Open…** opens a song, and the recent songs are in the same menu.
- **≡ › Duplicate…** (Ctrl+Shift+S) makes a separate copy to experiment with; this window stays on the original.
- **≡ › Show folder** opens the song's folder.
