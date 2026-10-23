# Groups, versions and delivery

Keep many tracks tidy, try another sound, hear what a clean-up did, make
spoken lines again, and hand the song on.

## 1. Groups of tracks

A group is one shared channel that several tracks play into. It gives you one row to mute, solo and fold away.

1. Select two or more tracks (Ctrl+click or Shift+click their names).
2. Press **Ctrl+G**, or use **Group** at the top of the settings panel. (In the Mixer, **+ Group** makes an empty
   group.)
3. The group has its own row. Click the arrow at its left to **fold** its tracks away; Alt+click the arrow folds all
   groups. **M** and **S** on the row mute or solo every track in the group.
4. To undo the grouping, select the group (or a track in it) and choose **Ungroup** (**Ctrl+Shift+G**).

## 2. Swap a sound

Try another sound in the same place, keeping the timing and the notes.

1. Select one clip and press **S**, or choose **Swap…** at the top of the settings panel. The Library opens.
2. Each result has a **Swap** button next to **Place**. Click it to put that sound where the old one was.
3. **Ctrl+Z** puts the old one back.

## 3. Before / After (key H)

When a clip has a clean-up (see [recording.md](recording.md)), a **Before | After** switch shows in the Editor.

- Click **Before** or **After** to hear the clip without or with the clean-up. Playback keeps going and each flip is
  one undo step.
- Or hold **H** to hear the other side, and let go to come back.

The switch is absent while a clip has no clean-up.

## 4. Spoken lines: Speak again

On a voice track, each line is a row with its words and time. A small dot shows its state.

1. Click a line to select it. **Type a line** adds a new one; its speech is made at once ("Speaking…").
2. For another reading of the same words, select the line and press **T**, or choose **Speak again**. The new take is
   added; the earlier one is kept.
3. Step between takes with **◂** and **▸** beside the line (**Earlier take** / **Later take**).

You can select several lines and speak them all again at once.

## 5. Hand it on: For the Editor and ranges

Open **Export** (Ctrl+E). The sheet is explained in [exporting.md](exporting.md); two parts matter here.

- **For the Editor** is one button at the top of the sheet. It sets the choices for handing the song to a video
  editor in one go: WAV 48 kHz 32-bit float, no loudness change, the whole length, a stem for every group, and the
  markers written beside the files. Change any choice and the button no longer shows as chosen. Group names are the
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
