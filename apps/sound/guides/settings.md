# Preferences

For a person using the RostrumSound app. Open with the menu (the app's mark at the top left), then **Preferences…**, or Ctrl+, (the window is titled **Preferences**). These are your machine's choices, kept the moment you make them (they are not part of any song or its history). Click **Done** to close.

Preferences show only what applies now, most important first. 
## Sound device

- **Speakers**: where you hear the song. Empty means whatever Windows uses by default.
- **Microphone**: what records a voice or instrument. Empty means Windows' default microphone. It is used when you record (see [recording.md](recording.md)).
- **Silence other programs (fastest)**: off by default. On: RostrumSound alone uses the speakers, for the shortest delay between a key and its sound, and other programs go quiet while it plays. Off: it shares the speakers with everything else. Hover it for the same words.
- **Buffer**: only shows when **Silence other programs (fastest)** is on. How much sound is prepared ahead. **Automatic** finds the shortest that plays cleanly and lengthens it if the computer falls behind. Fixed choices are 3, 5, 10, 20 and 40 ms. Shorter means a key sounds sooner, but a slow computer may crackle. A fixed buffer stays as set.

## New songs

These apply to songs you make from now on. A song keeps its own once made.

- **Sample rate**: **44.1 kHz (music CDs)**, **48 kHz (video)** (the default) or **96 kHz**. How finely the sound is stored.
- **Loudness target**: how loud a new song is made when you export with loudness matching. Default −14 LUFS, which suits streaming sites. −23 is broadcast TV. The range is −30 to −5.
- **Loudest peak allowed**: the loudest any moment may reach, so it doesn't distort after a video site re-encodes it. Default −1 dBTP, from −12 to 0.
- Every new song's master also starts with **Gentle limiting** on (**Most limiting** 2 dB): rather than squash its loudest moments harder, the master turns the whole song down, so it may come out a little under the loudness target. Change both on the master (click **Master** in the track list).

## Files

- **Projects folder**: where new songs are made (as "Untitled song", saved as you go). Empty means `Documents\Rostrum Sound` in your home folder.
- Click **More** under the list for the next two. **AI models folder**: where the voice and clean-up models are kept. Empty means `.rostrum\models` in your home folder.
- **Sound engine program**: the `rostrum-sound` program to use. Empty means it is found automatically, the one installed with the app. Leave it empty unless someone tells you otherwise.

## A few notes

- A change to Speakers or Microphone may need a moment, or the next time you play or arm a track.
- Some preferences can also be overridden by environment variables set on the computer; that is for experts.

## Your own keys

To use a different key for something, make the text file `.rostrum/keys/rostrumsound.toml` in your home folder and write one line per action: `"Undo" = "Ctrl+Shift+Z"`. An empty key (`"Add a marker at the playhead" = ""`) takes the key away. Write the action's name as the Keys list (**Ctrl+/**) shows it; a key you changed is marked "(your key)" there. If a line names an action that doesn't exist, or a key another action already has, the app says so when it starts and tells you which file to fix.
