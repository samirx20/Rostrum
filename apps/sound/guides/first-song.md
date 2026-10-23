# Your first song

For a person using the RostrumSound app. This page takes you from an empty song to something you can hear and export.

## The screen in one look

- **Top bar:** **≡** (the menu), the song's name, what just happened and how many changes, the **Loudness** chip and
  **Export** (once the song makes a sound), **Search** (Ctrl+K) and **?** (help).
- **Middle: the arrangement.** Every track is a row over time. Its header strip holds **+ Add**, ⏮ ▶, the position,
  and the tempo · beats · key; zoom − + **Fit** sit at its right.
- **Under it: the dock.** **Editor** (E) shows the selected track up close; **Mixer** (X) shows the faders. ▾ folds
  it away.
- **Right: the settings panel.** It shows what is selected, or the song when nothing is.
- **Left: the Library** (Ctrl+L), where every track starts from a sound.

## 1. Start a new song

Open **≡**, then **New song** (Ctrl+N). It is called "Untitled song" and lives in your projects folder.

Saving is automatic: every change is on disk as you make it. There is no Save button and nothing to lose. Ctrl+S
just tells you so; named versions come later with the History sheet.

## 2. Add a track

1. Click **Add a track** in the middle of the empty song, **+ Track** under the last track, or **+ Add › Track with a
   sound…**. You can also press **Ctrl+L**. The **Library** opens on the left.
2. Type to search ("warm", "bass", "voice"), or click a chip: **Instruments**, **Drums**, **Record**, **Voice**,
   **My sounds**.
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

1. With the track selected, the **Editor** shows its notes on a keyboard (drums: a row per drum; recordings: their
   waveform).
2. **Double-click** empty space to add a note (on a drum grid: a hit on that drum's row). Or press **B** for the
   **Draw** tool (top right of the Editor): then every click adds a note or a hit; **V** goes back to **Select**.
   Drag a note to move it in time and pitch.
   - It snaps to the grid. **Grid ▾** in the arrangement's header strip sets the step (Auto follows the zoom; Bar,
     Beat, 1/8, 1/16, 1/32, triplets); **Snap** switches snapping off and on. Hold **Ctrl** while dragging to drag
     without snapping once.
   - Hold **Alt** to drag a copy.
   - Hold **Shift** to move it only in time.
3. **Select several:** Ctrl+click adds or removes one, Shift+click takes everything between, and dragging across
   empty space draws a box. **Ctrl+A** selects all, **Esc** clears.
4. **The settings panel** on the right names the selection ("5 notes") and shows its actions first, as buttons, such
   as **Quantise** and **Transpose**; **More** holds the rest. **Right-click** is a short menu: Cut, Copy, Paste,
   Duplicate, Delete, and for tracks Group, Move up / down, Lock and Rename. **Ctrl+K** finds every action by name.
5. **Keys on the selection:**
   - Copy, cut and paste: **Ctrl+C**, **Ctrl+X**, **Ctrl+V**. Duplicate: **Ctrl+D**. Delete: **Delete**.
   - **A time range:** drag on the ruler's thin top band. The settings panel offers **Make a section** and **Select
     inside**; Ctrl+D duplicates it. With both a time range and selected notes, Ctrl+D acts on **the one you made last**:
     drag a range after clicking notes and Ctrl+D repeats the whole stretch; click notes after drawing a range and it
     copies just those notes. **Shift+Delete** cuts the range out of the clips under it and closes the gap.
   - Arrows nudge in time; ↑ / ↓ move notes a half step (Shift: an octave).
   - **Q** quantises. **Ctrl+T** splits a clip at the playhead and **Ctrl+J** joins clips.
   - **Ctrl+G** puts the selected tracks into a group.
   - **Shift+M** mutes the selected tracks and **Shift+S** solos them.
   - **M** puts a marker at the playhead.
6. Zoom with **Ctrl + wheel** and scroll in time with **Shift + wheel**. **Fit** (Ctrl+0) shows the whole song.
7. A mistake? **Ctrl+Z** undoes it (**Ctrl+Shift+Z** redoes). Every drag is one step.

## 5. Play it

- **Space** plays and stops. **Home** (or ⏮) goes to the start.
- Click the ruler to move the playhead there.
- **M** / **S** on a track's row mute it or play it alone.
- After an edit the sound is prepared again in a moment, so playback follows what you changed.

## 6. Tempo, beats and key

- With nothing selected, the settings panel shows the song: **Key**, **Tempo**, **Length** ("until the last sound"
  unless you set one) and **Beats per bar**.
- Click the tempo · beats · key in the header strip for a small box to add a tempo change or a key change at the
  playhead.

## 7. Get it out

**Export** in the top bar (Ctrl+E) opens the Export sheet on the right. See [exporting.md](exporting.md).

## Finding your song again

- **≡ › Open…** opens a song, and the recent songs are in the same menu.
- **≡ › Duplicate…** (Ctrl+Shift+S) makes a separate copy to experiment with; this window stays on the original.
- **≡ › Show folder** opens the song's folder.
