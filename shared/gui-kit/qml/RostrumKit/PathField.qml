import QtQuick
import QtQuick.Dialogs
import "."

// A file or folder path: the text field (type or paste a path; Enter commits) and a "…" (Browse) button that opens
// the system's own file or folder dialog, starting where the current path is. A choice sends one edited(path)
// with a plain local path (C:\Music\x.sfz, /Users/me/x.sfz), never a file:// address.
Item {
    id: f
    property string value: ""
    property bool folder: false           // true: pick a folder; false: pick a file
    property var nameFilters: []          // for a file: ["SFZ instruments (*.sfz)"]; empty = any file
    signal edited(string value)
    signal typingStarted()                // the typed path's caret went in / left (FieldFrame)
    signal typingEnded()
    implicitWidth: 220
    implicitHeight: Theme.field

    function toPath(url) {                // file:///C:/a%20b/x -> C:\a b\x (Windows), file:///Users/x -> /Users/x
        let p = decodeURIComponent(String(url).replace(/^file:\/\//, ""))
        if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1).replace(/\//g, "\\")
        return p
    }
    function toUrl(path) {                // a path's folder (a file's own folder) as a file:// address
        if (!path) return ""
        let p = path.replace(/\\/g, "/")
        if (!f.folder) p = p.slice(0, Math.max(0, p.lastIndexOf("/")))
        return p ? "file:///" + p.replace(/^\//, "") : ""
    }

    TextField {
        id: text
        anchors { left: parent.left; right: browse.left; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        value: f.value
        placeholder: "Default"            // empty means the setting's default (its help says which)
        elide: Text.ElideMiddle           // the whole path, cut in the middle when too long; hover shows all of it
        onEdited: (v) => f.edited(v)
        onTypingStarted: f.typingStarted()
        onTypingEnded: f.typingEnded()
    }
    IconButton {  // small, so the name keeps the room in a narrow inspector; its tip says what it does
        id: browse
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        width: Theme.field; height: Theme.field
        glyph: "…"
        tip: f.folder ? "Browse for a folder" : "Browse for a file"
        onClicked: f.folder ? folderDialog.open() : fileDialog.open()
    }
    FileDialog {
        id: fileDialog
        title: "Choose a file"
        currentFolder: f.toUrl(f.value)
        nameFilters: f.nameFilters.length ? f.nameFilters.concat(["All files (*)"]) : ["All files (*)"]
        onAccepted: f.edited(f.toPath(selectedFile))
    }
    FolderDialog {
        id: folderDialog
        title: "Choose a folder"
        currentFolder: f.toUrl(f.value)
        onAccepted: f.edited(f.toPath(selectedFolder))
    }
}
