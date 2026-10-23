# Recording

For a person using the RostrumSound app: record your voice or an instrument onto a track.

## 1. Choose the microphone

1. **≡**, then **Preferences…** (or Ctrl+,).
2. Under **Sound device**, set **Microphone**. Empty means Windows' default microphone.
3. Click **Done**. Preferences are kept at once.

## 2. Put on headphones

Use headphones. If the song plays from speakers, the microphone hears it and it ends up in your take.
If you must use speakers, leave **Hear input** off (see below).

## 3. Arm a track

1. Pick the track you want to record on. The quickest: open the **Library** (Ctrl+L), click the **Record** chip and
   double-click **Microphone**. The new track comes armed, ready to record.
2. Click **R** on the track's header. It turns red when armed. Click it again to disarm. Hovering over it explains it.
3. Once a track is armed, a group of controls appears in the arrangement's header strip, after ⏮ ▶: **Record**,
   **Take**, a small level bar and (with a keyboard) **Record keys**. With nothing armed it is not shown.

## 4. Check the level

The small bar next to **Take** shows how loud the microphone is. Green is fine, yellow is getting loud, red means too loud: move back or turn the input down in Windows. Speak or play as you will in the take, and watch it.

## 5. Choose how the take is made (optional)

Click **Take**. The panel shows only what can be used now:

- **Count-in**: clicks before you start. Turn it on and **Bars** appears (1 to 8).
- **Punch in**: record only over a range. Turn it on and the range appears as red edges on the ruler, starting two bars from the playhead. Drag across the ruler to draw it, or drag either red edge. The take stops by itself after the range. If the playhead is already past the start, playback starts one bar before it.
- **Hear input** (only when the microphone is open): you hear yourself in the output. **Volume** sets how much. Off by default.
- A line says whether the microphone's delay was measured.

## 6. Record

1. Move the playhead where you want to begin.
2. Click **Record** or press **R**. The song plays from the playhead. With count-in on you see "Count-in" and the number first, then **REC** with the seconds.
3. Click **Stop** (or press **R** again) to finish.

## 7. Where the take goes

- It becomes one clip on the armed track, at the moment you started. Undo removes it in one step.
- The sound file is saved in your song's folder, in `media`, named after the track's name and the take number (a track called Recording gives `Recording-take-1.wav`). Keep this in mind if you move the song: move its whole folder.

## 8. Optional: a cleaner take

If a take has hiss, hum or room echo:

1. Click the clip, then **Clean up…** at the top of the settings panel. It opens the panel's **Cleanup** group and offers three presets: **Dialogue only**, **Less noise** and **Less echo**. A click turns that step on (or off) for every picked clip and starts its cleaned take. The group itself has: **Less noise** and **Less echo** (0 to 1; start low, too much sounds watery), **Dialogue only**, **Play one stem**.
2. Once cleanup is set, a box appears under the settings panel: "This clip has cleanup set, but its cleaned take is not made yet." Meanwhile the song keeps playing and the clip plays its original.
3. Click **Make cleaned take**. The first time, a model may be missing. The box then asks first, giving its size and licence. Click **Download** to continue or **Not now**. You see progress, with **Cancel**; it is checked when done ("Downloaded and checked."). If it fails, use **Try again** or **Close**.
4. When it is made, the song plays again and the clip uses the cleaned take (the **Use cleaned take** switch turns it on and off).
5. The model is downloaded only once. Where it is kept is under **AI models folder** in Preferences.

## If something is wrong

- No level bar: the microphone did not open. Check **Microphone** in Preferences.
- Level bar stuck red with nothing playing: the microphone's input level in Windows is too high.
- Take a little late against the music: the microphone's delay was not measured. The Take panel says so.
