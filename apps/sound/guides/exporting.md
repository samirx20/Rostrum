# Exporting your song

For a person using the RostrumSound app: turn your song into sound files you can share, edit or send.

## Where

- **Export** in the top bar, **menu › Export…** (the app's mark at the top left), or **Ctrl+E**. It appears once the song makes a sound; before that, Ctrl+E says "Nothing to export yet: add a sound first".
- The sheet (titled **Make the file**; its button says **Export**) opens on the right, in the settings panel's place, so the song stays in sight. × or Ctrl+E
  closes it. It reads top to bottom like a bounce dialog: the **range** first (only when the song has a time range or sections), then **what for** (with **For the Editor** under it), the file type with **More** (its quality) under it, **+ Another version** (each extra version opens under it), **Stems**, **Cut the silence**, and the file's name (a box, the file type after it) with the folder under it, just above **Export**.
  The chosen target shows in the picker. The folder line shows exactly where the file will land, the new version folder included (`…\renders\song\v001`); a long path leaves its middle out, the whole of it on hover.
enders\song001`).
enders\song001`).
- **Ctrl+Shift+E** exports again with the last settings, without opening the sheet.

A solo or a mute that is on changes what the file holds, so the sheet says so first, in words ("Strings is soloed: the export holds only Strings", "Drums is muted: it is left out of the export"), with **Turn off solo** / **Turn off mute** under it: one click and the whole song is back. An agent does the same with `mix.hear_all`.

## 1. What for

What it is for is one picker at the top: open it and each choice shows its numbers under its name. **For the Editor** is a switch under it: on sets the file, quality, trimming, stems and markers for handing the song to a video editor, and it stays on while the choices still match; turn it off to put them back to the usual. Choosing **MIDI file** leaves only the file name and folder. The file's name sits just above the **Export** button: click the box and type the name you want (the file type stays after it); the line under it shows the exact folder the file lands in. The song keeps the sheet's choices as you leave them (file type, quality, trimming, stems, markers file; kept beside the song in `.rostrum/<song>.view-sound.json`, not in `renders`): pick stems, close the sheet without exporting, and they are still picked when you open it again, after a restart too, and cleaning the renders folder doesn't lose them. A song you never set the sheet for opens with the choices its last export was made with (each export keeps them in its `manifest.json` as `export_sheet`), so an agent's export with stems isn't followed by one without. Every choice on the sheet keeps its value when you change another (changing the target leaves Stems as you set it), and the sheet never moves under the pointer: the range picker's place at the top stays empty until the song has a section or a time range.

Pick where it is going. The list starts with **As the mix plays now** (it says "No loudness target": nothing is changed; it is there while the song's loudness matches no choice, and it goes once you pick one), then **Streaming: Spotify, YouTube, Tidal**, **Apple Music**, **Broadcast**, **US TV**, **Podcast** and **MIDI file**. Each target choice sets the song's loudness and its loudest peak in one step (one undo), and the sheet says so under the picker ("Loudness set to −14 for Streaming") with an **Undo** beside it while that is still your newest step: the mix is never changed quietly. A song whose loudness matches no choice shows "As the mix plays now" there until you pick one.

The last choice, **MIDI file**, writes no sound: it saves the song's notes, drum hits, sustain pedal, expression and
pitch bend, tempo map, time signature, keys, markers and sections as a `.mid` for another music app. The sound
settings below (file type, quality, stems, versions, the silent end) don't apply to it, so they disappear; the whole
song is written. It lands in the project's `renders/<song>/midi/` folder (Browse also copies it where you choose),
and anything MIDI can't hold is listed when it is done. Agents make the same file with `render_mix` (`what: "midi"`).

Under the choices a line checks the sound that plays now against that target. With a range chosen it reads that range alone (its loudness and loudest peak), because that is the file you get:
- "✓ Right for the target: loudness −14.2, loudest peak −1.3 dB" (green), or
- "Misses the target: 2.1 dB too quiet." and, under it, what to do ("Turn the mix up."), in amber.

**When the target can't be reached as the master is set.** Gentle limiting lets the master's limiter pull the loudest
moments down by at most **Most limiting** (2 dB in a new song); a mix with tall peaks then lands under the target. The
sheet says so before you save, in amber, with what the file will measure and what reaching the target takes:
"Will land at −16.4 LUFS: reaching −14 needs 4.4 dB of limiting (Most limiting allows 2). Over ~3 dB of limiting starts
to flatten acoustic drums and piano." Under it, one click:
- **Push to −14** (chosen by default): Export first measures the mix exactly as it will write it (your newest edit
  included; the sheet's number is only the last playback's estimate, and deep limiting needs more than it says), raises
  Most limiting as far as reaching the target takes, then writes the file once. The top bar says what it did ("Exported
  song_mix.wav · Most limiting raised to 9.4 dB to reach −14 LUFS"); it is one undo step ("Push loudness to target",
  Ctrl+Z puts the limit back; the file stays). The loudest peak still stays under the ceiling.
- **Keep it dynamic**: Export writes the mix at the level it reaches, and the sheet says that instead of "Loudness set to
  −14": "Kept dynamic: the file will measure −16.4 LUFS, 2.4 dB under Streaming's −14". Streaming services play a
  quieter file as it is, so the dynamics stay.

**When it would take a lot of limiting** (over ~3 dB, the loudest parts start to sound flat), the sheet also offers
**Tame the peaks first**: one click finds the gentlest compressor that takes the sharpest attacks off the peakiest track
(measured by rendering the song a few times in the background; the top bar says what it is doing), adds it first in
that track's chain with its makeup set so the track sits where it did, and says how much limiting is left ("Peaks tamed
on Piano … The master now needs 3.8 dB of limiting (was 9.8)"). It is one undo step ("Tame the peaks"); the compressor
stays in the track's chain to see and change. Then Push to −14 needs far less. When no gentle compressor gets under
~3 dB, it tries once more half way to what the push alone needs and takes that; when taming would save less than 1 dB,
or the peaks come from too many tracks at once, it changes nothing and says why under the button (with the tracks'
names), until the song changes. *Why not lift the quiet parts instead?*
The loudness measure leaves out passages more than 10 LU quieter than the loud ones, so raising a soft intro does not
lower the limiting a loud climax needs; it only makes the intro less soft (an agent can still ask for it: `edit_loudness`
`lift_quiet`, which says what it would change before anything is changed).

A song that would need more than the master's 12 dB says so and is written at the level it reaches; turn the peakiest
track down (or tame it) first. After any export the result line says what the file measured: "measured −14.2 LUFS,
loudest peak −1.3 dBTP, 4.3 dB of limiting".

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

- **Stems** is a picker: **Only the mix** (the first choice) or **A stem per track and group**, which also gives a file for every track and every group, named after it. Every stem goes through the master just as the mix
  did: its volume, fades, compression, loudness and limiter, the very same turn-down at the same moment for every stem. So
  the stems of the tracks in no group, plus the group stems, added together come to the mix, and a stem never clips where
  the mix doesn't. The master's own effects and reverb can't be split between stems: when the song has them, the result
  line says "The stems do not add up to the mix exactly" and names them. If any file still came out cut flat at full
  scale, the result line says which ("Clipped: Piano (120 samples cut flat)"): export as WAV 32-bit float, or turn that
  track down. While it works, the sheet says what it is doing ("Rendering the mix and its stems", then "Writing
  song_mix.wav and 4 stems as WAV 24-bit"). The song is rendered once; the stems come from that one render.
- **Cut the silence at the end** (on at first): the file ends a quarter of a second after the last sound you can hear.
  The mix and stems are cut to the same length. Switch it off to keep the song's full length.

## 5. Range, and another version

- **Range** (appears when the song has more than the whole song): the **whole song**, the **time range** you have
  dragged on the ruler, or a **section**. Each end of a range drawn on the ruler goes to a bar or beat line when you let go within a few pixels of it, otherwise to the grid line nearest the pointer (Grid ▾ in the header strip sets the step); right-click the ruler and turn on the seconds scale to draw it
  in exact seconds. The row's name shows the two ends to the hundredth ("Time range · 0:02.00–0:06.00"), which is what
  is exported. The file is exactly that stretch (2 s to 6 s is 4.00 s long; any ring-out past the end is cut). Its loudness is the whole song's, matched
  by the master and then cut, so a quiet section stays quieter than a loud one, as it sounds in the song. The silent
  end is not cut for a range. Agents: `render_mix` with `from` and `to` (seconds, a beat or a marker).
- **+ Another version** adds a row under it (**Another version**; with two or more, **Another version 1**, **2**, …) with its own target, file type and quality (for example Streaming WAV and a
  Podcast MP3 from one click). Each row has its own line: how far up or down the sound that plays now will be turned
  to reach it, and whether the loudest peak stays under the limit (when Normalize is off the line also says plainly how far the mix is from the song's loudness target, in amber, never a green tick; with the master's **Gentle limiting** on, a version whose peaks would need more limiting than **Most limiting** says it comes out that much quieter than its target instead, in amber). **Export** makes every row, each in its own
  numbered folder. A version's target does not change the song's own target. Stems come with the first version only.
  Agents: one `render_mix` per version.

## 6. Export

1. Click **Export**. It says **Exporting…** and works in the background; you can keep working.
2. When done, the sheet says "Exported · Play · Show in folder" (once). The top bar's chip says "Exported song.wav ▾" until your next change: click it for **Play** and **Show in folder**. Click **Show in folder** to open it. While it says "Exported", the folder line shows where that file really went; change a choice and the line shows where the next export will go.
3. If something went wrong, the sheet says so in red, in one sentence.

## What files appear

Each export goes into its own numbered folder in the song's folder, `renders\<song>\v001`, then `v002` and so on.
Nothing is overwritten.

- The mix: `<song>_mix` in the chosen format unless you name it (the name box; agents give `name` on `render_mix`, and on `render_midi` for the MIDI file). Characters a file name can't hold are replaced, and
  emptying the box goes back to `<song>_mix`. Agents get the same file from `render_mix`: `renders/<song>/vNNN/<song>_mix.wav`, absolute path in the reply's `file`; with `folder` (an absolute path) the mix is also copied there under the same `name`, and its stems into "<name> stems" beside it (`copied` in the reply). A song that has a Length is delivered exactly that long by `render_mix` (trim never cuts below it; a ring-out past it is faded out inside it; `ring_past_length: true` lets the file run on as the sheet does). The sheet shows this exact name and the next version folder before you
  export; **Browse**, or a folder typed in the folder box (Enter; made if it isn't there, Esc puts the old one back), copies the mix into that folder under the same name.
- With stems: one file per track (named after it) and one per group. A track with nothing in it still gets its file, silent; the
  result line names it ("silent: Recording").
- A manifest saying which file is which, and what format and rate was used.

## Credits for recorded instruments

A song that used an instrument licensed CC-BY (the Salamander piano, the Wurlitzer and Rhodes electric pianos, the rock drum kit) must
carry its credit. The render's reply says the credit lines, and the export's manifest holds them (`credits`): put them in
the video's description or end titles. CC0 instruments need none.
