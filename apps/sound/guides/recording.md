# Recording

For a person using the RostrumSound app: record your voice or an instrument onto a track.

## 1. Choose the microphone

1. The menu (the app's mark at the top left), then **Preferences…** (or Ctrl+,).
2. Under **Sound device**, set **Microphone**. Empty means Windows' default microphone.
3. Click **Done**. Preferences are kept at once.

## 2. Put on headphones

Use headphones. If the song plays from speakers, the microphone hears it and it ends up in your take.
If you must use speakers, leave **Hear input** off (see below).

## 3. Arm a track

1. Pick the track you want to record on. The quickest: open the **Library** (Ctrl+L), click the **Mic and files** chip and
   press **Add** on **Microphone**. The new track comes armed, ready to record.
2. Click **R** on the track's header. It turns red when armed. Click it again to disarm. Hovering over it explains it.
3. **Record** is always in the arrangement's header strip, after ⏮ ▶ and loop, and it never moves. Once a track is
   armed its dot is red; while recording the dot pulses and the word becomes **Stop** with the seconds. You can also skip arming: with no track armed,
   **Record** (or R) arms the selected track, else the first one that takes sound, and records; if there is none it
   says so in the message line.

## 4. Check the level

The thin bar along the bottom of the **Record** button shows how loud the microphone is while a track is armed. Green is fine, yellow is getting loud, red means too loud: move back or turn the input down in Windows. Speak or play as you will in the take, and watch it.

## 5. Choose how the take is made (optional)

Click the **▾** beside **Record** (or right-click **Record**); a track need not be armed. The panel shows only what can be used now:

- **Count-in**: clicks before you start. Turn it on and **Bars** appears (1 to 8).
- **Punch in**: record only over a range. Turn it on and the range appears as red edges on the ruler: it starts at the playhead and runs two bars. Drag across the ruler to draw it, or drag either red edge. The take stops by itself after the range. If the playhead is already past the start, playback starts one bar before it.
- **Hear input** (only when the microphone is open): you hear yourself in the output. **Volume** sets how much. Off by default.
- A line says whether the microphone's delay was measured.

## 6. Record

1. Move the playhead where you want to begin.
2. Click **Record** or press **R**. The song plays from the playhead. With count-in on you see "Count-in" and the number first, then **Stop** with the seconds, the dot pulsing.
3. While it records, the take grows in the armed track's lane from where it started to the playhead, marked
   "Recording…", with the microphone's level drawn along it: you see at once that the right track is taking sound.
4. Click **Stop** (or press **R** again) to finish. The growing take becomes its clip a moment later.

## 7. Where the take goes

- It becomes one clip on the armed track, at the moment you started. Undo removes it in one step.
- The sound file is saved in your song's folder, in `media`, named after the track's name and the take number (a track called Recording gives `Recording-take-1.wav`). A sound file you bring in with **+ Add › From a file…** is copied there too. The song remembers the file by its place inside the folder, so you can copy or move the whole song folder and the takes still play. If a take's file is deleted, play and export stop and name the clip, the track and the file.

## 8. Optional: a cleaner take

If a take has hiss, hum or room echo:

1. Click the clip. For a take recorded here, the panel's **Cleanup** group is the one place for the controls; for any other clip it appears after **Clean up…** in Ctrl K (which jumps to it). It has **Play one stem**, **Dialogue only**, **Less noise** and **Less echo**. The two sliders run from 0 % to 100 %; start low, because too much sounds watery.
2. The cleaned take is made as soon as you let go of a slider or switch a step on. The clip shows its progress, and the song keeps playing the original until the take is ready. Click **Cancel** under the panel to stop it; nothing half-made is kept.
3. When it is made, the **Use cleaned take** switch is on (turn it off to hear the original again), and a line under the panel says what the clean-up did, for example "Background noise −6 dB · voice level −6 dB". If it is amber and says "The voice got quieter too: try less.", lower the slider.
4. **Dialogue only** and some other steps need a model. The first time, a box under the panel says so, with its size and licence. Click **Download** to continue or **Not now**; you see progress, with **Cancel**, and it is checked when done ("Downloaded and checked."). The take is made right after. If the download fails, use **Try again** or **Close**.
5. **Make cleaned take** is a button that appears under the panel only when a clip has cleanup set but no take yet, for example after a download was cancelled or a take failed. Click it to make the take.
6. The model is downloaded only once. Where it is kept is under **More** › **AI models folder** in Preferences.

## If something is wrong

- No level bar: the microphone did not open. Check **Microphone** in Preferences.
- Level bar stuck red with nothing playing: the microphone's input level in Windows is too high.
- Take a little late against the music: the microphone's delay was not measured. The Take panel says so.
