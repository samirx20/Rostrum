import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The ≡ menu (INTERACTION.md §1.19; it was "File"): everything about the song as a file (screensound/session.py,
// `songs`). Saving is automatic, so there is no Save: New, Open…, the sample, the recent songs, Duplicate… (a separate
// copy; this window stays on the original), Save a version (Ctrl+S; named versions come with the History sheet),
// Show folder, Preferences…, Quit. The prompts: a refused open in words, and untitled songs a crash left behind.
Button {
    id: file
    property var settingsPanel
    text: "≡"
    down: menu.visible
    onClicked: menu.visible ? menu.close() : openMenu()
    HoverTip { text: "Menu: new, open, duplicate, preferences"; hovered: file.hovered && !menu.visible }
    function openMenu() { const p = file.mapToItem(null, 0, file.height + 2); menu.openAt(p.x, p.y) }
    function saveNow() { backend.say(songs.saveVersion()) }
    function newNow() { songs.newSong() }
    function openNow() { openDialog.open() }
    function duplicateNow() { duplicateDialog.open() }

    ActionMenu {    // the kit's menu with keys (INTERACTION.md Part 5, piece 3)
        id: menu
        entries: [{ value: "new", label: "New song", keys: "Ctrl+N", group: "open" }, { value: "open", label: "Open…", keys: "Ctrl+O", group: "open" },
                  { value: "sample", label: "Open sample (Lull)", group: "open" }]
                 .concat(songs.recent.slice(0, 6).map((r, i) => ({ value: "recent:" + i, label: "Open " + r.name, group: "recent" })))
                 .concat([{ value: "duplicate", label: "Duplicate…", keys: "Ctrl+Shift+S", group: "file" },
                          { value: "version", label: "Save a version", keys: "Ctrl+S", group: "file" },
                          { value: "folder", label: "Show folder", group: "file" },
                          { value: "settings", label: "Preferences…", keys: "Ctrl+,", group: "app" },
                          { value: "quit", label: "Quit", keys: "Ctrl+Q", group: "app" }])
        onPicked: (v) => {
            if (v === "new") songs.newSong()
            else if (v === "open") openDialog.open()
            else if (v === "sample") songs.openSample()
            else if (v === "duplicate") duplicateDialog.open()
            else if (v === "version") file.saveNow()
            else if (v === "folder") songs.showFolder()
            else if (v === "settings") file.settingsPanel.open()
            else if (v === "quit") Qt.quit()
            else if (v.indexOf("recent:") === 0) { const r = songs.recent[Number(v.slice(7))]; songs.openRecent(r.folder, r.item) }
        }
    }
    // A refused open or duplicate, in words: in the top bar's message line (a line starting "Error" shows red).
    Connections {
        target: songs
        property string said: ""
        function onChanged() { if (songs.error !== "" && songs.error !== said) backend.say("Error: " + songs.error); said = songs.error }
    }

    FolderDialog {
        id: openDialog
        title: "Open a song: choose its folder"
        currentFolder: songs.projectsFolder
        onAccepted: songs.openPath(selectedFolder.toString())
    }
    FileDialog {
        id: duplicateDialog
        title: "Duplicate the song: name the copy and choose where"
        fileMode: FileDialog.SaveFile
        currentFolder: songs.projectsFolder
        nameFilters: ["A song folder (*)"]
        onAccepted: { const t = songs.duplicate(selectedFile.toString()); if (t) backend.say(t) }
    }
    Connections {
        target: songs
        function onRecoverOffered() { recover.open() }
        function onRefused() { refused.open() }
    }

    Prompt {    // a refused open / save, in words: the sentence, then its details
        id: refused
        heading: songs.error.split(" Details: ")[0]
        message: songs.error.indexOf(" Details: ") < 0 ? "" : songs.error.split(" Details: ")[1]
        Button { text: "OK"; kind: "primary"; onClicked: refused.close() }
    }

    Prompt {
        id: recover
        heading: songs.recoverable.length > 1 ? "RostrumSound closed unexpectedly: " + songs.recoverable.length + " songs were kept"
                                              : "RostrumSound closed unexpectedly"
        message: "Untitled songs from then are kept with every change up to that moment. Open the one you want, or throw it away."
        content: [Repeater {
            model: songs.recoverable
            delegate: Rectangle {
                required property var modelData
                width: recover.availableWidth; height: Theme.button + 4
                radius: Theme.radiusCtl; color: Theme.app
                Text { x: Theme.gap + 2; anchors.verticalCenter: parent.verticalCenter; text: "Untitled song, " + parent.modelData.when
                       color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                Row {
                    anchors { right: parent.right; rightMargin: 2; verticalCenter: parent.verticalCenter }
                    spacing: 2
                    Button { text: "Open"; kind: "primary"; height: Theme.button - 4
                             onClicked: { recover.close(); songs.recover(parent.parent.modelData.folder) } }
                    Button { text: "Throw away"; kind: "ghost"; danger: true; height: Theme.button - 4
                             onClicked: { songs.discardRecovered(parent.parent.modelData.folder)
                                          if (!songs.recoverable.length) recover.close() } }
                }
            }
        }]
        Button { text: "Later"; kind: "ghost"; onClicked: recover.close() }
    }
}
