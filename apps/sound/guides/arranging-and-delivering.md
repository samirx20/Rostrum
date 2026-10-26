# Groups, versions and delivery

Keep many tracks tidy, repeat a section and change the repeat, try another sound, hear what a clean-up did,
make spoken lines again, and hand the song on.

## 1. Groups of tracks

A group is one shared channel that several tracks play into. It gives you one row to mute, solo and fold away.

1. Select two or more tracks (Ctrl+click or Shift+click their names).
2. Press **Ctrl+G**, or use **Group** at the top of the settings panel. (In the Mixer, **+ Group** on the master's strip makes an
   empty group.)
3. The group has its own row. Click the arrow at its left to **fold** its tracks away; Alt+click the arrow folds all
   groups. **M** and **S** on the row mute or solo every track in the group.
4. To undo the grouping, select the group (or a track in it) and choose **Ungroup** (**Ctrl+Shift+G**).

## 2. Swap a sound

Try another sound in the same place, keeping the timing and the notes.

1. Select one sound clip (a recording or a sound file) and press **S**, or choose **Swap…** at the top of the settings panel. The Library opens on **My sounds**, which lists the folders you added with **Add a folder…**: add one first if it is empty, or pick another chip or search.
2. While a clip is selected, each result has a **Swap** button next to **Add**. Click it to put that sound where the old one was, with the same start, length and level. Arrow up and down try each result in the clip's place.
3. **Ctrl+Z** puts the old one back.

A track of notes has no clips to swap: change its sound with the **Sound ▾** picker in the track's settings panel.

## 3. Before / After (key H)

When a clip has a clean-up (see [recording.md](recording.md)), a **Before | After** switch shows in the Editor.

- Click **Before** or **After** to hear the clip without or with the clean-up. Playback keeps going and each flip is
  one undo step.
- Or hold **H** to hear the other side, and let go to come back.

The switch is absent while a clip has no clean-up.
The clip in the lane draws the sound it plays: the cleaned take while **Use cleaned take** is on (silent if the clean-up removed everything), the original otherwise.

## 4. Spoken lines: Speak again

On a voice track, each line is a row with its words and time. A small dot shows its state.

1. Click a line to select it. **Type a line** adds a new one; its speech is made at once ("Speaking…").
2. For another reading of the same words, select the line and press **T**, or choose **Speak again**. The new take is
   added; the earlier one is kept.
3. Step between takes with **◂** and **▸** beside the line (**Earlier take** / **Later take**).

You can select several lines and speak them all again at once.

## 5. Hand it on: For the Editor and ranges

Open **Export** (Ctrl+E). The sheet is explained in [exporting.md](exporting.md); two parts matter here.

- **For the Editor** is a switch under the target picker, not at the top of the sheet. It sets the choices for handing the song to a video
  editor in one go: WAV 48 kHz 32-bit float, no loudness change, the whole length, a stem for every track and group, and the
  markers written beside the files. Change any choice and the switch no longer shows as on. Group names are the
  stem names, so name your groups.
- **Range** (when the song has more than the whole song) lets you export a **time range** you dragged on the ruler,
  or a **section**, instead of the **Whole song**. See [exporting.md](exporting.md), section 5.

## 6. Make this the main mix

A project can hold several songs. One of them is the **main mix**, the one the rest of the project uses.

1. Open the song and select nothing, so the settings panel shows the song.
2. Click **Make this the main mix**. It says the song is now the main mix, and the button goes away.

The button only appears for a song in a project that is not yet its main mix.

## 7. Cues from 2D

When a 2D animation in the same project adds sounds at its markers, they arrive on a track called **Cues from 2D**.
Each clip there is tied to a named marker such as "logo lands". Select a clip and the settings panel says which marker
it is tied to. If the marker moves in 2D, the clip follows it. Move or swap such a clip as any other.

## 8. The Problems chip (what is wrong with the song)

When something about the song needs you, a **Problems** chip appears in the top bar with a count (it is gone when there is
nothing). Click it for the list; each line says what is wrong and what to do, and clicking a line selects that clip or track.
It lists, in one place:

- **Missing file**: a clip's sound file is not where the song says (the line names the clip and the file).
- **File outside the song**: a clip's file lives outside the song's folder, so it will not travel if you copy or move the
  song. Record or import it again to keep a copy inside.
- **Cleaned take not made**: a clip is set to a cleaned take that is not made yet; until it is, the original plays.
  Select the clip and press Make cleaned take. While it is being made it is work in progress, not a problem: the Clean up
  bar shows it and the chip does not count it.
- **Held past the end**: notes or clips still held at the song's Length. They are let go there (cut off, or ringing out
  with Ring out on); shorten them or make the song longer if they should be heard whole.
- **No longer made**: a designed sound an older song still holds (see *scoring-motion*).
- **Notes it can't play** (red): the newest render was refused because a track has a note outside its sound's range
  (Violins play G3–D6, so an octave too many up stops the mix). The line names the track, the note and the range; click
  it to select the track, then move those notes back (Down an octave) or pick another sound. Any other refusal of the
  render is listed the same way as **Can't make the sound**. Until it is fixed the last good sound plays, and the
  loudness chip says "Can't play: fix the notes" instead of the old mix's loudness.
- **Clipping** (red): the newest mix goes over full scale.

Agents get the same list, except clipping, from the `inspect_diagnose` tool (each problem: kind, item, message, fix), plus **out-of-range**: a track with notes its recorded sound can't play, named with the sound's range (the render would refuse the whole song). `run_script` says the same in its reply.

## 9. Duplicate a section, then vary it

A second verse or a "B" that answers "A": copy the section with everything in it, then change the copy.

1. **Copy it.** On the screen, click the section's band on the ruler and choose **Duplicate section** at the top of
   the settings panel (or press **Ctrl+D**). The copy's section is then selected on its own, so Ctrl+D again copies it
   once more. An agent calls `edit_document` with
   `{"op": "section.duplicate", "target": ["section.A"]}`. Every note, drum hit and clip that **starts** inside the
   section is copied to right after it (a hit Humanise or Feel nudged up to a 1/32 note before the section's line
   counts as inside; one that close to its end belongs to the next section), and the copy is a new section named like the first with the next free
   number (`A-2`, id `section.A-2`; a copy of `A-2` is `A-3`). Nothing after the section moves, so the bars right
   after it must be free: when they already hold notes, hits, clips or another section, the copy is refused and
   says what is there (move what follows later first with `section.move`). Set the song's length (`doc.set`) if it
   should now run longer. One undo step.
2. **List the copy's ids.** A copied note, hit or clip gets a new id made from its track and where it now starts, in
   milliseconds: `<track>.n<ms>` for a note (`melody.n22222` starts at 22.222 s), `<track>.<drum><ms>` for a hit
   (`drums.kick22222`), so you cannot guess them before the copy exists. Ask for them afterwards:
   - `inspect_item {"id": "section.A-2"}` gives the copy's `at` and `end`;
   - `inspect_notes {"track": "melody", "section": "A-2"}` lists that section's notes in one line each (id, time, pitch, length, velocity);
   - `inspect_item {"id": "melody", "detail": "full"}` lists every note on that track with its id and values (`at`,
     `pitch`, `dur`); keep the ones that start between the copy's `at` and `end`.
   - `look_arrangement` shows both sections side by side, to check the copy landed where you meant.
3. **Vary it.** Change the copy with ordinary operations on those ids, in one `edit_document` call (all or nothing,
   one step): `note.set` (`pitch`, `vel`, `dur`; a chord takes a list of pitches), `note.transpose`, `note.remove`, `note.thin` (every Nth, or the soft ones),
   `hit.add` / `hit.remove` for a busier or sparser groove, `track.set` to change a sound only for the whole track.
   On the screen, **Select inside** on the copy's section selects everything in it to move or change at once.

Writing the song with `run_script` instead? A script can also just write the second section itself (a loop over the
first one's notes with changes); `section.duplicate` is for a section you or a person already have in the document.
