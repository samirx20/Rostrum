# Exporting your song

For a person using the RostrumSound app: turn your song into sound files you can share, edit or send.

## Where

1. Click **Mix**.
2. The export is at the bottom of the **Master** strip: a format picker, a sample-rate picker, **Trim silence at the end** and **Render mix and stems**.
3. The song must be saved as a folder first (**File**, **Save…**).

## 1. Pick a format

The picker shows each choice with a short note.

- **WAV 24-bit** (for video editors): the usual choice for handing sound to a video editor. Big files, no loss, room to change the volume later. This is what you get first.
- **WAV 16-bit** (CD quality, dithered): the CD standard. "Dithered" means a tiny bit of steady noise is added when rounding down, so quiet endings fade out smoothly and don't crackle.
- **WAV 32-bit float** (no rounding, for further mixing): nothing is rounded or cut off. Use it if someone will keep mixing the file.
- **FLAC 24-bit** (lossless, about half the size): the same sound as the WAV, packed smaller. Nothing is lost. Many programs open it, but some video editors don't.
- **MP3 320 kbps** (small, to listen on any device): the smallest, for sharing and listening. It loses a little sound. Don't use it to hand to another editor.

There is no AAC option yet.

## 2. Pick a sample rate

- **44.1 kHz** (music): music and CDs.
- **48 kHz** (video): the choice for video.
- **96 kHz** (high resolution): very fine, huge files. Not for MP3.

A new song starts with the rate you chose in Settings (**Sample rate**). It is rendered at the rate you pick here. MP3 offers only 44.1 and 48 kHz.

## 3. Trim silence at the end

On by default. Leaves the file ending a quarter of a second after the last sound you can hear, so a long empty end isn't exported. The mix and all stems are cut to the same length, so they line up. Switch it off to keep the song's full length.

## 4. Render

1. Click **Render mix and stems**. It says **Rendering…** and works in the background; you can keep looking around.
2. When done, the line below says what was made. If something went wrong it says so in red, beginning with "Error".
3. Click **Show folder** to open it.

## What files appear

Each render goes in its own new numbered folder, `renders\<song>\v001`, then `v002` and so on. Nothing is overwritten.

- The mix: `<song>_mix` in the chosen format.
- **Stems**: one file for every track, named after the track (a track called Piano gives `Piano`). Two tracks with the same name get a number after them. Every bus gives `<name>.bus`.
- A manifest saying which file is which, and what format and rate was used.

Stems are made so that, added together, they come to the mix. Compression and the limiter on the master strip are not applied in stems, so a stem can be a bit quieter or louder than in the mix.

## Loudness

On the same strip, **Deliver to** (streaming, Apple Music, broadcast TV, podcast) sets the loudness target and peak ceiling. Settings has the defaults for new songs. Render after you change them.
