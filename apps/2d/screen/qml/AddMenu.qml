import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The "+" at the foot of the tool strip: what is not a tool. Import… (files and designs: the Import panel), Camera, a 3D render (only
// with Rostrum3D, adder.entries) and the Library drawer. The drawing tools (shape, text, path, drawing) are tools, not here. A choice
// is one change through the same operations agents use (`add` still takes every type); image and video ask for their file first.
Button {
    id: add
    property var adder: backend.adder
    property alias menuOpen: menu.visible
    readonly property var rest: add.adder.entries.filter(e => e.type === "camera" || e.type === "render3d")
    kind: "ghost"; width: 92
    text: "+"; tip: "Add"; help: "Import a file, add a camera or a 3D render, open the Library."
    down: menu.visible
    onClicked: menu.visible ? menu.close() : menu.open()

    Menu {
        id: menu
        entries: [{ value: "import", label: "Import…" }].concat(add.rest.map(e => ({ value: e.type, label: e.label })))
                 .concat([{ value: "library", label: "Library" }])
        onPicked: (v) => {
            if (v === "import") Window.window.setImportOpen(true)
            else if (v === "library") backend.library.setOpen(!backend.library.open)
            else add.adder.add(v)
        }
    }
    FileDialog {
        id: dialog
        property string type: ""
        title: "Choose " + type
        nameFilters: type === "video" ? ["Video (*.mp4 *.mov *.webm *.mkv *.m4v *.avi)"]
                                      : ["Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"]
        onAccepted: add.adder.addFile(type, selectedFile.toString())
    }
    Connections {
        target: add.adder
        function onFileWanted(type) { dialog.type = type; dialog.open() }
    }
}
