import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The File button in the top bar and everything about the song as a file (screensound/session.py, `songs`):
// New song, Open, the recent songs, Save (an untitled song: asks for a name and a place) or Save As, Settings.
// A named song is saved after every change, so it has no Save; Ctrl+S on it just says so.
// The prompts: leaving an untitled song with changes (Save… / Don't keep / Cancel), and untitled songs a crash
// left behind (Open it / Throw away).
Button {
    id: file
    property var settingsPanel
    text: "File"
    down: menu.visible
    onClicked: menu.visible ? menu.close() : openMenu()
    function openMenu() { menu.open() }
    function saveNow() { note.show(songs.save()) }

    Menu {
        id: menu
        width: 260
        entries: [{ value: "new", label: "New song" }, { value: "open", label: "Open…" }]
                 .concat(songs.recent.slice(0, 6).map((r, i) => ({ value: "recent:" + i, label: "Open " + r.name })))
                 .concat([{ value: "saveas", label: songs.untitled ? "Save…" : "Save a copy as…" },
                          { value: "settings", label: "Settings…" }])
        onPicked: (v) => {
            if (v === "new") songs.newSong()
            else if (v === "open") openDialog.open()
            else if (v === "saveas") saveDialog.open()
            else if (v === "settings") file.settingsPanel.open()
            else if (v.indexOf("recent:") === 0) { const r = songs.recent[Number(v.slice(7))]; songs.openRecent(r.folder, r.item) }
        }
    }
    Text {
        id: note
        function show(t) { text = t; visible = t !== ""; hide.restart() }
        visible: false
        anchors { right: parent.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        Timer { id: hide; interval: 3500; onTriggered: note.visible = false }
    }
    Text {      // a refused open / save, in words, until the next thing works
        visible: songs.error !== ""
        anchors { right: parent.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
        width: 420; elide: Text.ElideRight; horizontalAlignment: Text.AlignRight
        text: songs.error; color: Theme.danger; font.family: uiFont; font.pixelSize: Theme.body
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
        readonly property var first: songs.recoverable.length ? songs.recoverable[0] : null
        heading: "RostrumSound closed unexpectedly"
        message: "An untitled song from then is kept with every change up to that moment"
                 + (songs.recoverable.length > 1 ? " (" + songs.recoverable.length + " songs)." : ".")
        Button { text: "Open it"; kind: "primary"; onClicked: { recover.close(); songs.recover(recover.first.folder) } }
        Button { text: "Throw it away"; danger: true; onClicked: { songs.discardRecovered(recover.first.folder)
                                                                    if (!songs.recoverable.length) recover.close() } }
        Button { text: "Later"; kind: "ghost"; onClicked: recover.close() }
    }
}
