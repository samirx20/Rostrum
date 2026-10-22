import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The Add button in the top bar: the layers that make sense on this page (adder.entries), most important first. A choice is one
// change through the same operations agents use; image and video ask for their file first.
Button {
    id: add
    property var adder: backend.adder
    property alias menuOpen: menu.visible
    text: "+ Add"; tip: "Add"; help: "Put a new layer on the canvas: a shape, text, a drawing, a camera."
    down: menu.visible
    onClicked: menu.visible ? menu.close() : menu.open()

    Menu {
        id: menu
        entries: add.adder.entries.map(e => ({ value: e.type, label: e.label }))
        onPicked: (type) => add.adder.add(type)
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
