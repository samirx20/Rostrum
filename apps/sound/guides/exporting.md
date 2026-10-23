# Exporting your song

For a person using the RostrumSound app: turn your song into sound files you can share, edit or send.

## Where

- **Export** in the top bar, or **Ctrl+E**. It appears once the song makes a sound.
- The **Export sheet** opens on the right, in the settings panel's place, so the song stays in sight. × or Ctrl+E
  closes it.
- **Ctrl+Shift+E** exports again with the last settings, without opening the sheet.

## 1. What for

Pick where it is going: **Streaming**, **Apple Music**, **EBU R128**, **ATSC A/85** or
**Podcast**. Each choice sets the song's loudness and its loudest peak in one step (one undo).

The last choice, **MIDI file**, writes no sound: it saves the song's notes, drum hits, sustain pedal, expression and
pitch bend, tempo map, time signature, keys, markers and sections as a `.mid` for another music app. The sound
settings below (file type, quality, stems, versions, the silent end) don't apply to it, so they disappear; the whole
song is written. It lands in the project's `renders/<song>/midi/` folder (Browse also copies it where you choose),
and anything MIDI can't hold is listed when it is done. Agents make the same file with `render_midi`.

Under the choices a line checks the sound that plays now against that target:
- "✓ Pass: loudness −14.2 LUFS, loudest peak −1.3 dBTP" (green), or
- "Miss: 2.1 LU too quiet …" (amber).

The top bar's **Loudness** chip shows the same: the song's loudness, the target, and a green dot within 1 of it
(amber outside). Click the chip to open the Mixer.

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

This is how finely the sound is stored (the sample rate).
- **44.1 kHz** (music): music and CDs.
- **48 kHz** (video): the choice for video.
- **96 kHz** (high resolution): very fine, huge files. Not for MP3.

A new song starts with the rate set in Preferences. MP3 offers only 44.1 and 48 kHz.

## 4. Stems and the end

- **Stems** (off at first): also a file for every track and every group, named after it. Added together they come to
  the mix. The master's compression and limiter are not in the stems.
- **Cut the silence at the end** (on at first): the file ends a quarter of a second after the last sound you can hear.
  The mix and stems are cut to the same length. Switch it off to keep the song's full length.

## 5. Range, and another version

- **Range** (appears when the song has more than the whole song): the **whole song**, the **time range** you have
  dragged on the ruler, or a **section**. The file is exactly that stretch. Its loudness is the whole song's, matched
  by the master and then cut, so a quiet section stays quieter than a loud one, as it sounds in the song. The silent
  end is not cut for a range. Agents: `render_mix` with `from` and `to` (seconds, a beat or a marker).
- **+ Another version** adds a row with its own target, file type and quality (for example Streaming WAV and a
  Podcast MP3 from one click). Each row has its own line: how far up or down the sound that plays now will be turned
  to reach it, and whether the loudest peak stays under the limit. **Export** makes every row, each in its own
  numbered folder. A version's target does not change the song's own target. Stems come with the first version only.
  Agents: one `render_mix` per version.

## 6. Export

1. Click **Export**. It says **Exporting…** and works in the background; you can keep working.
2. When done, the sheet says "Exported · Version 3 · …". Click **Show in folder** to open it.
3. If something went wrong, the sheet says so in red, in one sentence.

## What files appear

Each export goes into its own numbered folder in the song's folder, `renders\<song>\v001`, then `v002` and so on.
Nothing is overwritten.

- The mix: `<song>_mix` in the chosen format.
- With stems: one file per track (named after it) and one per group.
- A manifest saying which file is which, and what format and rate was used.
