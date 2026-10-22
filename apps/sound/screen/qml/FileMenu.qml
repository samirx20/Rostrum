import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The File button in the top bar and everything about the song as a file (screensound/session.py, `songs`):
// New song, Open, the recent songs, Save (an untitled song: asks for a name and a place) or Save As, Settings.
// A named song is saved after every change, so it has no Save; Ctrl+S on it just says so.
// The prompts: leaving an untitled song with changes (Save… / Don't keep / Cancel), and untitled songs a crash
// left behind (Open it / Throw away), and a song that was refused (damaged, another app's, a newer version's).
Button {
    id: file
    property var settingsPanel
    text: "File"
    down: menu.visible
    onClicked: menu.visible ? menu.close() : openMenu()
    function openMenu() { menu.open() }
    function saveNow() { const t = songs.save(); if (t) backend.say(t) }

    function newNow() { songs.newSong() }
    function openNow() { openDialog.open() }
    function saveAsNow() { saveDialog.open() }

    HintMenu {
        id: menu
        entries: [{ value: "new", label: "New song", hint: "Ctrl N" }, { value: "open", label: "Open…", hint: "Ctrl O" },
                  { value: "sample", label: "Open sample (Lull)" }]
                 .concat(songs.recent.slice(0, 6).map((r, i) => ({ value: "recent:" + i, label: "Open " + r.name })))
                 .concat(songs.untitled ? [{ value: "saveas", label: "Save…", hint: "Ctrl S" }]
                                         : [{ value: "save", label: "Save", hint: "Ctrl S" },
                                            { value: "saveas", label: "Save a copy as…", hint: "Ctrl Shift S" }])
                 .concat([{ value: "settings", label: "Settings…", hint: "Ctrl ," }])
        onPicked: (v) => {
            if (v === "new") songs.newSong()
            else if (v === "open") openDialog.open()
            else if (v === "save") file.saveNow()
            else if (v === "sample") songs.openSample()
            else if (v === "saveas") saveDialog.open()
            else if (v === "settings") file.settingsPanel.open()
            else if (v.indexOf("recent:") === 0) { const r = songs.recent[Number(v.slice(7))]; songs.openRecent(r.folder, r.item) }
        }
    }
    // What a save said, and a refused open / save in words: in the top bar's status line, like every other
    // "what just happened" (a line starting "Error" shows red).
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
        id: saveDialog
        title: songs.untitled ? "Save the song: name it and choose where" : "Save a copy of the song as"
        fileMode: FileDialog.SaveFile
        currentFolder: songs.projectsFolder
        nameFilters: ["A song folder (*)"]
        onAccepted: songs.saveAs(selectedFile.toString())
        onRejected: if (keep.visible === false) songs.answer("cancel")
    }
    Connections {
        target: songs
        function onWantSaveAs() { saveDialog.open() }
        function onAskKeep() { keep.open() }
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
        id: keep
        heading: "Keep this song?"
        message: "This song has no name yet. Save it to keep it, or leave it and it is thrown away."
        Button { text: "Save…"; kind: "primary"; onClicked: { keep.close(); songs.answer("save") } }
        Button { text: "Don't keep"; danger: true; onClicked: { keep.close(); songs.answer("discard") } }
        Button { text: "Cancel"; kind: "ghost"; onClicked: { keep.close(); songs.answer("cancel") } }
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
