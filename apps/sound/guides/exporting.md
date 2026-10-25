# Exporting your song

For a person using the RostrumSound app: turn your song into sound files you can share, edit or send.

## Where

- **Export** in the top bar, **≡ › Export…**, or **Ctrl+E**. It appears once the song makes a sound; before that, Ctrl+E says "Nothing to export yet: add a sound first".
- The sheet (titled **Make the file**; its button says **Export**) opens on the right, in the settings panel's place, so the song stays in sight. × or Ctrl+E
  closes it. It reads top to bottom like a bounce dialog: the **range** first (only when the song has a time range or sections), then **what for** (with **For the Editor** under it), the file type, **+ Another version**, **Stems**, **Cut the silence**, **More**, and the folder with its file name just above **Export**.
  The chosen target shows in the picker. The folder shows as its last two names ("song / v001"); the whole path is on hover.
- **Ctrl+Shift+E** exports again with the last settings, without opening the sheet.

## 1. What for

What it is for is one picker at the top: open it and each choice shows its numbers under its name. **For the Editor** is a switch under it: on sets the file, quality, trimming, stems and markers for handing the song to a video editor, and it stays on while the choices still match; turn it off to put them back to the usual. Choosing **MIDI file** leaves only the file name and folder. The file's whole name sits just above the **Export** button.

Pick where it is going. The list starts with **As the mix plays now** (it says "No loudness target": nothing is changed; it is there while the song's loudness matches no choice, and it goes once you pick one), then **Streaming**, **Apple Music**, **Broadcast**, **US TV**, **Podcast** and **MIDI file**. Each target choice sets the song's loudness and its loudest peak in one step (one undo), and the sheet says so under the picker ("Loudness set to −14 for Streaming") with an **Undo** beside it while that is still your newest step: the mix is never changed quietly. A song whose loudness matches no choice shows "As the mix plays now" there until you pick one.

The last choice, **MIDI file**, writes no sound: it saves the song's notes, drum hits, sustain pedal, expression and
pitch bend, tempo map, time signature, keys, markers and sections as a `.mid` for another music app. The sound
settings below (file type, quality, stems, versions, the silent end) don't apply to it, so they disappear; the whole
song is written. It lands in the project's `renders/<song>/midi/` folder (Browse also copies it where you choose),
and anything MIDI can't hold is listed when it is done. Agents make the same file with `render_midi`.

Under the choices a line checks the sound that plays now against that target. With a range chosen it reads that range alone (its loudness and loudest peak), because that is the file you get:
- "✓ Right for the target: loudness −14.2, loudest peak −1.3 dB" (green), or
- "Misses the target: 2.1 dB too quiet …" (amber).

When the master's numbers match none of the choices the picker reads "As the mix plays now" and the check line is not shown:
there is no target to meet or miss until you pick one.

The top bar's **Loudness** chip shows the same: the song's loudness, the target, and a green dot within 1 of it
(amber outside). Click the chip to open the Mixer, where the loudness curve is.

## 2. File

Each choice has a short note.

- **WAV 24-bit** (for video editors): the usual choice for handing sound to a video editor. Big files, no loss, room
  to change the volume later. This is what you get first.
- **WAV 16-bit** (CD quality, dithered): the CD standard. "Dithered" means a tiny bit of steady noise is added when
  rounding down, so quiet endings fade out smoothly.
- **WAV 32-bit float** (no rounding, for further mixing): nothing is rounded or cut off.
- **FLAC 24-bit** (lossless, about half the size): the same sound as the WAV, packed smaller. Some video editors
  don't open it.
- **MP3 320 kbps** (small, to listen on any device): the smallest, for sharing and listening. It loses a little sound.

There is no AAC option yet.

## 3. Quality

This is how finely the sound is stored (the sample rate). Click **More** to see it.
- **44.1 kHz** (music): music and CDs.
- **48 kHz** (video): the choice for video.
- **96 kHz** (high resolution): very fine, huge files. Not for MP3.

A new song starts with the rate set in Preferences. MP3 offers only 44.1 and 48 kHz.

## 4. Stems and the end

- **Stems** is a picker: **Only the mix** (the first choice) or **A stem per track and group**, which also gives a file for every track and every group, named after it. Added together they come to
  the mix. The master's compression and limiter are not in the stems.
- **Cut the silence at the end** (on at first): the file ends a quarter of a second after the last sound you can hear.
  The mix and stems are cut to the same length. Switch it off to keep the song's full length.

## 5. Range, and another version

- **Range** (appears when the song has more than the whole song): the **whole song**, the **time range** you have
  dragged on the ruler, or a **section**. Each end of a range drawn on the ruler goes to a grid line within a few pixels of it, else takes in the whole grid step it is in (Grid ▾ in the header strip); right-click the ruler and turn on the seconds scale to draw it
  in exact seconds. The row's name shows the two ends to the hundredth ("Time range · 0:02.00–0:06.00"), which is what
  is exported. The file is exactly that stretch (2 s to 6 s is 4.00 s long; any ring-out past the end is cut). Its loudness is the whole song's, matched
  by the master and then cut, so a quiet section stays quieter than a loud one, as it sounds in the song. The silent
  end is not cut for a range. Agents: `render_mix` with `from` and `to` (seconds, a beat or a marker).
- **+ Another version** adds a row with its own target, file type and quality (for example Streaming WAV and a
  Podcast MP3 from one click). Each row has its own line: how far up or down the sound that plays now will be turned
  to reach it, and whether the loudest peak stays under the limit (when Normalize is off the line also says plainly how far the mix is from the song's loudness target, in amber, never a green tick). **Export** makes every row, each in its own
  numbered folder. A version's target does not change the song's own target. Stems come with the first version only.
  Agents: one `render_mix` per version.

## 6. Export

1. Click **Export**. It says **Exporting…** and works in the background; you can keep working.
2. When done, the sheet says "Exported · Play · Show in folder" (once; the top bar says it too). Click **Show in folder** to open it. While it says "Exported", the folder line shows where that file really went; change a choice and the line shows where the next export will go.
3. If something went wrong, the sheet says so in red, in one sentence.

## What files appear

Each export goes into its own numbered folder in the song's folder, `renders\<song>\v001`, then `v002` and so on.
Nothing is overwritten.

- The mix: `<song>_mix` in the chosen format. The sheet shows this exact name and the next version folder before you
  export; **Browse** copies the mix into your folder under the same name.
- With stems: one file per track (named after it) and one per group. A track with nothing in it still gets its file, silent; the
  result line names it ("silent: Recording").
- A manifest saying which file is which, and what format and rate was used.
