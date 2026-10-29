# Timing to music

When your project has music, voice or sound made in RostrumSound, Rostrum2D plays it with the picture, shows it as a row in the timeline, and lets you put things on its beats and on its markers. The sound itself is always made in RostrumSound and played by RostrumSound's engine: 2D does not mix or change it, so what you hear here is the same mix you will export from Sound.

## 1. Hearing the project's sound

1. Open a project that has a RostrumSound song in it. Rostrum2D finds it by itself. A song you made in its own RostrumSound project comes in with the menu (the app's mark at the top left) › **Add a song from RostrumSound…**: pick the song's `.trk` file (in that project's `docs` folder). It is copied into this project with its history; the original stays where it was, and later changes there don't come over. A project that already has a song of that name says so and changes nothing.
2. Press **Space** (or the play button at the left of the timeline's header). The sound plays with the picture.
3. Drag the playhead in the ruler. You hear a short burst of the sound wherever you let it rest, so you can find a beat or a word by ear.
4. When the sound changes in RostrumSound (you or an agent edits the song, or a marker moves), 2D notices within a second and plays the new mix. While the new mix is being made, the Sound row says "Sound is rendering the mix…".

## 2. The Sound row

![The timeline with the Sound row and its waveform at the bottom](pictures/sound-row.png)

- The **Sound row** is the last row of the timeline, under every layer. Its name is the song's name, with a ♪ before it. On the right is the waveform: tall where the sound is loud, flat where it is quiet.
- It is there only when the project has sound.
- When the timeline is folded to its small height (the button at the right end of the ruler), the Sound row stays, under the selected layer.
- A voice line whose voice is not made yet in RostrumSound shows faded, with "not made yet" after its words. It is silent until RostrumSound makes it (its **Make voice**); the scene opens and plays as usual. An export that includes the sound stops and says which line is missing.
- If something is wrong, the row says so in red words instead of a waveform. For example, RostrumSound is not installed, the song can't be read, or your computer has no sound output. The same words show at the top of the window. The picture still plays.

## 3. Muting the sound

- Click the **speaker button** at the right end of the Sound row's name. It shows as pressed, with a cross in place of the sound waves, and the waveform fades. Click it again to hear the sound.
- Muting is only for this window. It does not change the song, and an export from RostrumSound still has all of its sound.

## 4. Picking which sound plays

1. Click an empty part of the canvas (outside every layer). The settings panel shows the scene's settings.
2. Click **+ Sound** under the scene's settings. The **Soundtrack** setting appears, showing **Main mix:** and the name of the project's main song.
3. Click the choice beside **Soundtrack** (it reads **Main mix:** and the song's name) to open its list. The first choice is **Main mix: <song>** (the project's main RostrumSound song, the one that plays unless you pick another); under it comes every RostrumSound song of the project, each by its name. Click one to play that song with this scene.

**+ Sound** and the Soundtrack setting are there only when the project has at least one RostrumSound song.

## 5. Showing the beats

![Show beats on: a faint line on every beat, a stronger line and a number on every bar](pictures/show-beats.png)

1. Click the song's name on the Sound row (or right-click the row). Its menu opens.
2. Click **Show beats**. A faint line appears on every beat, and a stronger line with the bar's number on every bar.
3. To hide them, open the menu again and click **Hide beats**.

**Show beats** is in the menu only when the song has a tempo. When you zoom out far, the beat lines leave and only the bar lines stay.

In a script (for agents): `beats()` gives the same beats as a list of seconds, to cut or key on (`b = beats(); title.set(start=b[16])`); it reads the song that plays with the scene and says so loudly when the project has no song yet. Before there is a song, `beats(bpm=120, start="#in", count=16)` gives a grid of beats from a marker (marker times that move with it). `marker("drop", 8)` in the script makes a shared marker the song can later be written to; `start="#drop"`, `end="#drop+2"` and keys on `"#drop+0.2"` tie layers to it.

## 6. Snapping to beats and markers

When you drag a layer's bar, its ends or a key in the timeline, it snaps to things nearby:

- markers first (the flags on the ruler), then the playhead, then the ends of other bars and other keys, then the beats of the music;
- a pink line down the timeline shows what it caught;
- hold **Ctrl** while you drag to turn snapping off, so it moves by whole frames.

A layer has a bar once it has keys (see [the-screen.md](the-screen.md)).

## 7. Tying a bar to a marker from the music

Markers made in RostrumSound (for example "drop") are shared with the whole project and show as flags on the ruler.

A song's own markers (made in its script with `marker()`, or in RostrumSound's window) count as markers here too: a layer's timing, a key, an expression, `look_frame` and the export find them by name, and `inspect_markers` lists them as the songs' own. On the ruler they are hollow grey flags with a ♪; hovering one names its song. They are read-only in 2D (no drag, rename or delete): change them in RostrumSound, and the flag follows within a second. One name is one marker: a project marker may have the same name as a song's marker only at the same time; at another time it is refused when you make it, and an export says so before it draws anything.

![The title's end tied to the "drop" marker: a small yellow mark at the tied end, and Ends at marker shows drop in the settings panel](pictures/tied-to-marker.png)

1. Drag the start or the end of a layer's bar towards the marker's line (every layer has a bar; the pointer turns into a two-way arrow over an end). A small label by the pointer names what it would snap to.
2. Let go when it snaps to the marker. A small yellow mark appears on that end: the end is now **tied** to the marker. The **Timing** group of the settings panel says so too: **Ends at marker** (or **Timed from marker**, for the start) shows the marker's name.
3. When the marker moves (someone changes the song in RostrumSound, or you drag the flag), the tied end moves with it. You don't have to do anything.

You can tie a whole bar the same way: drag its middle so that its start lands on the marker.

The same can be done without dragging: pick the layer, open **Timing** in the settings panel (click **+ Timing** if it is folded away) and pick the marker in **Timed from marker** (its start) or **Ends at marker** (its end).

## 8. Jumping from beat to beat

- **Shift+.** moves the playhead to the next beat; **Shift+,** to the one before.
- **.** and **,** (without Shift) still jump to the next or previous key, marker or drawing.

These keys work when the song has a tempo.

## 9. Changing the sound itself

Right-click the **Sound row** and choose **Open in RostrumSound**. RostrumSound opens on this project's song. Change the music, voice or markers there; 2D picks up the new sound by itself (see step 1.4).

## 10. For agents: layers timed from a marker

Cuts, entrances and beats that other apps also use (the music's drop, the 3D product landing) go on the project's
**shared markers** (`inspect_markers`, `edit_markers`), never copied as numbers. Give a layer or a whole group
**Timed from marker** (`marker="reveal"`): its *Starts at*, *Ends at* and keys, and everything inside it, count
from that marker. Move the marker in any app and the shot moves with it; Sound's music follows the same marker.

In a script, `marker("reveal", 3)` makes that shared marker (re-running moves it, removing the line removes it) and
gives `"#reveal"`, which adds like a number. A layer's `start="#reveal+0.5"` makes it Timed from marker with its other
numbers still meaning comp seconds as written; `end="#out"` is Ends at marker. `after(item, gap=)` is when its last
key lands, `stagger(items, every=, start=)` gives each item its start, `beats(bpm=120, start=)` a beat grid without a
song: no hand-counted `t0 + i * 0.5` (guide `the-film-as-one-script`).

```python
with group("reveal_shot", marker="reveal", end=4.0):     # visible from the marker for 4 s
    t = text("name", body="Lull", size=180)
    t.key("opacity", {0.0: 0, 0.4: 1})                     # 0.0 = the moment of the marker
```

- Inside a timed group, `start`, `end` and key times are **seconds from the marker**: `end=4.0` is 4 s after it, not
  at 4 s of the comp.
- A layer inside a timed group with its own `marker` counts from its own marker.
- **Ends at marker** (`endMarker="reveal"`) ends a layer on another marker: the phone shot is gone exactly when the
  reveal starts, wherever either marker moves.
- **Cuts:** the frame jumps on a key timed on a marker: `frame().cut(at="#reveal", to="rect", rect=(2240, 0, 1920, 1080))`
  (or `frame.cut` with `at: "#reveal"`), so the cut moves with the marker (see `frame-parallax-motion-blur`).
- **Lead-ins:** *Starts at* may be below 0, counted back from the marker (`start=-0.2` appears 0.2 s before it).
  A group's lead-in shows its children too: a child left at *Starts at* 0 starts with its group; a child with a
  start of its own counts it from the marker (`start=0.2` appears 0.2 s after it).
- **A key on its own marker:** a key's time may name a marker, as Sound's times do: `t.key("opacity", {0.0: 0,
  "#drop-0.1": 0.2, "#drop+0.2": 1})` (or `key.add` with `"t": "#drop+0.2"`). It lands at that moment of the
  project, whatever its layer counts from, so one layer can hit "drop" and "logo lands" both, and a key may sit
  before the layer's start (a pre-roll: the move is under way when the layer appears). Moving the marker moves the
  key; a marker that is gone stops the render naming the key. `look_motion` (`what: "curve"`), the curve editor and the settings panel
  show the marker ("drop +0.2 s"); dragging such a key keeps it on its marker with a new offset.
- Drawings' frames, effects', masks' and a rig's keys move with their layer.
- `look_motion`, `look_frame` and the export all read the times as they play (marker + time). `inspect_item`
  shows the times as written, from the marker.
- A marker the project doesn't have stops the render with a message, and `look_frame` with `what: "diagnose"` lists it.
- Move a marker with `edit_markers` and `marker.move`; its target may be the marker's name or its id:
  `{"op": "marker.move", "target": ["drop"], "args": {"at": 5.5}}`.

## 11. For agents: music and sound

Sound is made in **RostrumSound**, never in 2D: its own MCP server (`rostrum-sound`) on the **same project
folder**. Started together for one agent, the two servers open the same folder by themselves (the newest folder either
opened); after `run_open_project` in one, call it with the same folder in the other. Read its guides `start-here` and `scoring-motion` there. What it makes plays here
with the picture and goes under an mp4 export (`render_export` with `what: "video"`, `sound`, on by default when the project has sound).
Tie the two by **shared markers** ("drop", "logo lands"; `inspect_markers`), never copied times. From 2D:

- `inspect_sounds` lists what you can tie to a layer: a note or hit on the song's own instruments, the person's
  recordings, RostrumSound's library; `edit_sound_cue {layer, sound}` ties one to the layer's start (Sound mixes it).
- `render_export` `format: "motion"` hands your layers' motion to RostrumSound (`edit_sounds_from_motion` there
  suggests notes and hits for each landing).
- **No sound?** A render of a project with no RostrumSound item, or with `sound: false`, makes a silent mp4; it never fails for that. The Sound server is only needed to make or change the music, not to render it.
- In a script, `beats()` gives the beats of the scene's song in seconds, to cut or key on (`beats(bpm=120)` a grid with no song); a song's markers work as times (`"#drop"`), and `marker("drop", 8)` makes a shared one.

Next: [the-screen.md](the-screen.md), [exporting.md](exporting.md).
