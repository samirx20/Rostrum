# Files and settings

Starting, opening and copying projects. Your work is saved as you go: there is no Save button and nothing to lose.

## 1. Saving is automatic

1. Every change is on disk the moment you make it, so the top bar says nothing about saving. Only when saving is not happening does an amber dot sit after the project's name (red if saving failed); point at the name to read why. The window's title then starts with "● " too.
2. There is no "Save changes?" question when you close or open something else. Every change is in History (the clock at the top right, or **Ctrl+H**).
3. An agent working on the same project saves the same way. You see its changes in your window as they happen.

## 2. The file menu

Click the app's mark (the blue square with **▾**) at the top left.

- **New** (Ctrl+N): a new project, made at once in your projects folder.
- **Open…** (Ctrl+O): pick a project folder to open.
- **Open recent**: the projects you opened last.
- **Open sample** (only until you have a project of your own): your own copy of the sample project. The original never changes.
- **Duplicate…** (Ctrl+Shift+S): a separate copy of the whole project under a name you choose. Your window stays on the original and says so; click **Open the copy** to go to it.
- **Save a version** (Ctrl+S): gives the project as it is now a name, in History, so you can come back to it. The time is filled in as the name; type another if you like.
- **Show folder**: the project's folder on your computer.
- **Start screen…**: the start screen (see 4).
- **Add a song from RostrumSound…**: copies a song made in RostrumSound into this project, where it plays with the picture (see [timing-to-music.md](timing-to-music.md)).

The same actions are in the command box (**Ctrl+K**).

## 3. A project is a folder

1. Each project is a folder. It holds your work, your exports and your markers together.
2. New projects go in `Documents\Rostrum2D`, called "Untitled", "Untitled 2" and so on.
3. A new project you leave without changing anything is removed, so trying New leaves nothing behind.

## 4. Starting the app

1. The app opens the project you had open last.
2. With nothing to reopen, the start screen shows: **New**, **Open…**, **Open the sample** (the very first time only), your recent projects (with a picture of each), and three guides.
3. While the start screen shows, only its own keys work: **Ctrl+N** (New), **Ctrl+O** (Open…) and **Esc** (back to your project, when one is open). The project behind it hears nothing (Space doesn't play it, Ctrl+K doesn't open its command box).

## 5. If a project can't be opened

A damaged project, or one saved by a newer Rostrum2D, is not opened. A sentence in the top bar says why, in plain words ("This project file is damaged and can't be opened: proj.mtn"), and that nothing was changed.

## Your own keys

To use a different key for something, make the text file `.rostrum/keys/rostrum2d.toml` in your home folder and write one line per action: `"Undo" = "Ctrl+Shift+Z"`. An empty key (`"Add a marker at the playhead" = ""`) takes the key away. Write the action's name as the Keys list (**Ctrl+/**) shows it; a key you changed is marked "(your key)" there. If a line names an action that doesn't exist, or a key another action already has, the app says so when it starts and tells you which file to fix.

## For agents: open or make a project

The server starts on your own project, never the person's: the one you last opened from this working folder (a resumed
session gets it back), else a fresh scratch project made for you (in `~/.rostrum/projects/agent-scratch/`, with an empty
document `main`). The first reply says which. To work on the person's project, somewhere else, or to start a new piece:

- `run_open_project {"folder": "C:/Users/me/Videos/launch"}`: the folder is an absolute path. If it doesn't exist yet it
  is made (with any folders above it), with an empty document `main` in it; an existing project opens as it is.
- `item` names the document: `{"folder": "...", "item": "teaser"}` opens `teaser`, or starts it empty beside the others.
- `run_open_project {"what": "recent"}` lists the person's recent projects.
- A refused call (a path that isn't absolute, a file instead of a folder, a document name with spaces) makes nothing.

Next: [first-animation.md](first-animation.md), [exporting.md](exporting.md).
