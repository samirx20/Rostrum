# Your first song

For a person using the RostrumSound app. This page takes you from an empty song to something you can hear and export.

## The screen in one look

- **Top bar:** **≡** (the menu), the song's name, **Search** (Ctrl+K), the **loudness chip** ("−14.2 LUFS · target −14"
  with a dot: green within 1 of the target, amber outside; click it to open the Mixer) and **Export** (both once the
  song makes a sound), and **?** (help).
- **Middle: the arrangement.** Every track is a row over time. Its header strip holds **+ Add**, then the transport, always
  there: ⏮ (to the start), ▶ (play / stop, the one blue button), the loop button, **Record** and the metronome; then
  the position ("3.2  0:04.80": bars.beats, then the time; click it and type **5.3** or **9.6 s** to jump there; a beat the bar does not have, like 5.9 in 4/4, is refused with the reason), and the song's tempo, beats and key as fields; **Grid ▾**, **Snap**, zoom − + and **Fit** sit at its right. The ruler counts **bars**: plain numbers, one per
  bar. For a seconds scale, right-click the ruler and choose **Show seconds** (the same entry hides it).
- **Under it: the dock.** **Editor** (E) shows the selected track up close; **Mixer** (X) shows the faders. ▾ folds
  it away.
- **Right: the settings panel.** It shows what is selected, or the song when nothing is. Times there read in
  **bars.beats**, like the ruler: At **5.3** is bar 5, beat 3 (**5.3.480** when it falls between beats; 960 ticks make
  a beat), and a Length counts from 0 (**0.2** is two beats, **2.0** two bars). Hover the label for the seconds. Type
  `5.3`, `5.3.240`, `5` (a bar), `9.6 s` or `0:09.6`; it is stored the way the item was written (beats stay beats,
  seconds stay seconds, a marker time stays on its marker). A pitch reads as a note name (G4); type G4 or a number.
- **Left: the Library** (Ctrl+L), where every track starts from a sound.

## 1. Start a new song

Open **≡**, then **New** (Ctrl+N). It is called "Untitled song" and lives in your projects folder.

Saving is automatic: every change is on disk as you make it. There is no Save button and nothing to lose. Ctrl+S
just tells you so; named versions come later with the History sheet. (The song's own file is brought fully up to date when
you close the window and every 20 changes; the change log beside it always has the latest, and opening the song plays it.)

## 2. Add a track

1. Click **Add a track** in the middle of the empty song, **+ Track** under the last track, or **+ Add › Track with a
   sound…**. You can also press **Ctrl+L**. The **Library** opens on the left.
2. Type to search ("warm", "bass", "voice"), or click a chip: **All**, **Instruments**, **Drums**, **Record**,
   **Voice**, **My sounds**.
3. **Double-click** a sound, or select it and press **Enter**. A new track with that sound appears, selected, and the
   **Editor** opens under the arrangement.
   - **Microphone** makes a track that is ready to record (see [recording.md](recording.md)).
   - With a track of the same kind already selected, the Library asks "Change Piano to Strings? The notes stay."
     Pick **Change** to swap that track's sound, or **New track** for a new one.
4. On a narrow window the Library floats over the arrangement and closes after each use. On a wide one it stays open
   beside it. Close it with × or Ctrl+L.

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
   **Draw** tool: then every click adds a note or a hit; **V** goes back to **Select**. **Note ▾** sets how long a new
   note is (a quarter at first; 1/8, 1/16, a bar … or one grid step).
   Drag a note to move it in time and pitch.
   - It snaps to the grid. **Grid ▾** in the arrangement's header strip sets the step (Auto follows the zoom; Bar,
     1/2, 1/4, 1/8, 1/16, 1/32, triplets; the current one is ticked); **Snap** switches snapping off and on. Hold **Ctrl** while dragging to drag
     without snapping once.
   - Hold **Alt** to drag a copy.
   - Hold **Shift** to move it only in time.
3. **Select several:** Ctrl+click adds or removes one, Shift+click takes everything between, and dragging across
   empty space draws a box. **Ctrl+A** selects all, **Esc** clears.
4. **The settings panel** on the right names the selection ("5 notes") and shows its actions first, as buttons, such
   as **Quantise** and **Transpose**, each always in the same place; **⋯** at the end of that row holds the less used
   ones (when only those fit, there is no row: use right-click or **Ctrl+K**). The bottom line, **Last changed by …**,
   sits on its own under a thin line; click it to open History. There is no bar floating over the arrangement: the
   actions live there. **Right-click** is a short menu: Cut, Copy, Paste, Duplicate, Delete, and for tracks Group,
   Move up / down, Lock and Rename. On empty lane space it offers Paste here, Add marker here and Select all on this
   track; on the ruler, Add marker here, Make a section from here and Show seconds. **Ctrl+K** finds every action by
   name.
5. **Keys on the selection:**
   - Copy, cut and paste: **Ctrl+C**, **Ctrl+X**, **Ctrl+V**. Duplicate: **Ctrl+D**. Delete: **Delete**.
   - **A time range:** drag on the ruler's thin top band. The settings panel offers **Make a section** and **Select
     inside**; Ctrl+D duplicates it. With both a time range and selected notes, Ctrl+D acts on **the one you made last**:
     drag a range after clicking notes and Ctrl+D repeats the whole stretch; click notes after drawing a range and it
     copies just those notes. **Shift+Delete** cuts the range out of the clips under it and closes the gap.
   - Arrows nudge in time; ↑ / ↓ move notes a half step (Shift: an octave).
   - **Q** quantises. **Ctrl+T** splits a clip at the playhead and **Ctrl+J** joins clips.
   - **Ctrl+G** puts the selected tracks into a group. **Ctrl+]** and **Ctrl+[** move the selected tracks up and
     down the list.
   - **Shift+M** mutes the selected tracks and **Shift+S** solos them.
   - **M** puts a marker at the playhead.
6. Zoom with **Ctrl + wheel** and scroll in time with **Shift + wheel**. **Fit** (Ctrl+0) shows the whole song.
7. A mistake? **Ctrl+Z** undoes it (**Ctrl+Shift+Z** redoes). Every drag is one step.

## 5. Play it

- **Space** plays and stops. **Home** (or ⏮) goes to the start.
- The **metronome icon** beside play turns the click on and off (**Shift+K**); it is lit while on. It is only for you while you work; it is never in an export.
- The **loop button** (**Shift+L**) is always there. It loops the time range on the ruler; with no range drawn it
  makes one first: the selection's span, else the bar at the playhead and the next three. The loop shows as a solid
  blue band on the ruler's top strip; drag either edge to change it, double-click the band to clear it (that also
  ends the loop).
- Click the ruler to move the playhead there.
- Each track's header shows a small picture of what it holds (keyboard: notes, drum, waveform: sound files,
  microphone: voice), its name and its volume, then its buttons: **R** gets it ready to record, **M** mutes it, **S**
  plays it alone, **A** opens its automation lane, the padlock locks it. Under them a thin bar shows how loud the
  track was in the last render (green, amber near 0 dB, red over). When rows are short the header is one line;
  if it is narrow too, A and the padlock show only when on or under the mouse (R, M and S always stay).
- After an edit the sound is prepared again in a moment, so playback follows what you changed.

## 6. Tempo, beats and key

A typed tempo outside 20–400 bpm is refused ("Tempo is 20–400 bpm"), never changed to the nearest.

- The song's **tempo**, **beats per bar** (4/4, 3/4 …) and **key** are the three fields in the arrangement's header
  strip, and they show what plays at the playhead. Type the tempo or drag it; pick the beats and the key from their
  lists. Nothing has to be selected first.
- With nothing selected, the settings panel shows the song's timeline as lists: **Tempo**, **Time signature**, **Key**,
  **Sections** and **Markers**, then **Song** (its **Length**, "until the last sound" unless you set one, and **More**).
  **Bar 1** under Tempo and Time signature is the song's own start: type or drag the tempo, pick the time signature
  there. Every change after it is a row ("Bar 5 · drop", its value at the right): click a row and the playhead jumps
  there and the change is selected, so the panel shows its settings (Delete removes it). A time signature change
  has its own picker in its row: pick 6/8 there and it changes in one step (one Ctrl+Z takes it back).
- Under each list, **+ Tempo change**, **+ Time signature change**, **+ Key change**, **+ Section** and **+ Marker**
  add one at the playhead. A new change starts at what already plays there and is selected, so you change it at once
  (pick 6 and 8 for a 6/8 bar). A **+** is there only where it makes sense: not at the very start (that is the song's
  own tempo and time signature) and not where one already sits.
- A new section is named for its next musical role (intro, verse, chorus …); rename it in the settings panel.
- Changes sit on the ruler as small flags: "♩ 132" for a tempo, "3/4" for a time signature, "D minor" for a key.
  Drag a flag to move it (one undo step). Click one and the settings panel shows it. A tempo flag has **Bpm**, **At**
  and **Glide to next**: turn that on and the tempo speeds up or slows down evenly to the next change instead of
  jumping; its flag then reads "♩ 100 ↗" (or ↘ when slowing). Time signature changes start a new bar at that place;
  the ruler's bar numbers follow them. Add one with **+ Time signature change** in the song's panel (or an agent's
  `meter.add`); the header's time signature sets the one playing at the playhead (the song's own before the first
  change).

## 7. Get it out

**Export** in the top bar (Ctrl+E) opens the Export sheet on the right. See [exporting.md](exporting.md).

## Finding your song again

- **≡ › Open…** opens a song, and the recent songs are in the same menu.
- **≡ › Duplicate…** (Ctrl+Shift+S) makes a separate copy to experiment with; this window stays on the original.
- **≡ › Show folder** opens the song's folder.
