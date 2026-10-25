import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import "."

// The ≡ button and menu, the same in every app (INTERACTION.md 1.19 item 2, kit piece 13): New, Open…, Open recent ▸,
// Open sample, Duplicate…, Save a version, Show folder, Start screen…, then the app's own rows (`extra`). Two more
// rows appear only when they apply: "Find missing files…" (asks for a folder, links every file found in it again as one
// change) while something is missing, and "Open the last version that works" after a refused damaged file. Saving is
// automatic, so there is no Save. Its keys come from the key map (files.keys: Ctrl+N, Ctrl+O, Ctrl+Shift+S, Ctrl+S).
// Reads the app's `files` (rostrum_gui/project_files.py). In the top bar: AppShell { menu: FilesMenu { … } }
//     extra: [{ value: "settings", label: "Preferences…", keys: "Ctrl+,", group: "app" }]; onPicked: (v) => …
IconButton {
    id: root
    property var source: typeof files !== "undefined" ? files : null
    property var extra: []                   // the app's own rows, after the kit's
    property bool keysOn: true               // off while a dialog of the app's own has the keys
    readonly property bool menuOpen: menu.visible
    signal picked(string value)              // one of `extra`'s values
    icon: "menu"; kind: "ghost"; tip: "Menu"; help: "New, open, duplicate, versions and the start screen"
    down: menu.visible
    onClicked: menu.visible ? menu.close() : openMenu()

    function openMenu() {
        spot.open(source.menu().concat(extra))     // under ≡, its left edge on the window's gap; beside the tool rail, not over it
    }
    function closeMenu() { menu.close() }
    function ask(v) {           // the file actions that need the window: a dialog, or History's name field
        if (v === "open") openDialog.open()
        else if (v === "find") findDialog.open()
        else if (v === "duplicate") {
            duplicateDialog.selectedFile = source.projectsUrl + "/" + encodeURIComponent(source.name + " copy")
            duplicateDialog.open()
        } else if (v === "version") {
            const w = root.Window.window
            if (w && w.nameVersion) w.nameVersion(source.versionName())     // the name field at the top of History
            else source.saveVersion("")
        }
    }

    MenuSpot { id: spot; anchor: root; menu: menu; x0: Theme.gap }
    ActionMenu {
        id: menu
        onPicked: (v) => { if (root.extra.some(e => e.value === v)) root.picked(v); else root.source.pickLater(v) }      // later: New / Open swap the whole screen, and this menu goes with it (never inside its own handler)
    }
    Connections {
        target: root.source
        function onWanted(v) { root.ask(v) }
        function onCopied(name) { if (!root.source.startShown) notice.open() }   // the start screen says it itself
        function onChanged() { if (root.source.startShown) notice.close() }      // ...and takes it over when it opens
    }
    Instantiator {      // the file keys, from the key map
        model: root.source ? [["new", root.source.keys.new], ["open", root.source.keys.open],
                              ["duplicate", root.source.keys.duplicate], ["version", root.source.keys.version]] : []
        delegate: Shortcut {
            required property var modelData
            sequence: modelData[1]
            context: Qt.WindowShortcut
            enabled: root.keysOn && (root.source.hasProject || modelData[0] === "new" || modelData[0] === "open")
            onActivated: root.source.pickLater(modelData[0])      // later: New swaps the screen this key belongs to
        }
    }

    FolderDialog {
        id: openDialog
        title: "Open a " + (root.source ? root.source.noun : "project") + ": choose its folder"
        currentFolder: root.source ? root.source.projectsUrl : ""
        onAccepted: root.source.openPath(selectedFolder.toString())
    }
    FolderDialog {
        id: findDialog
        title: "Find missing files: choose the folder they are in"
        currentFolder: root.source ? root.source.projectsUrl : ""
        onAccepted: root.source.findMissing(selectedFolder.toString())
    }
    FileDialog {
        id: duplicateDialog
        title: "Duplicate: name the copy and choose where"
        fileMode: FileDialog.SaveFile
        currentFolder: root.source ? root.source.projectsUrl : ""
        onAccepted: root.source.duplicate(selectedFile.toString())
    }

    SmallPopup {     // after Duplicate: the window stays on the original; the copy is one click away
        id: notice
        parent: root
        y: root.height + Theme.grid
        padding: Theme.gap
        background: MenuBackground { }
        onOpened: noticeTimer.restart()
        Timer { id: noticeTimer; interval: 10000; onTriggered: notice.close() }
        contentItem: Row {
            spacing: Theme.gap
            Text { anchors.verticalCenter: parent.verticalCenter; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   text: "Copy made. This window stays on the original." }   // the message line names the copy
            Button { text: "Open the copy"; kind: "primary"; onClicked: { notice.close(); root.source.pickLater("copy") } }
        }
    }
}
