import QtQuick
import QtQuick.Dialogs
import "."

// The paint picker's Picture part: the picture (its file name; a click chooses another). How it sits in the layer's box
// is the picker's (Fit and the app's rows, shared with Painted). A pick is `changed(fields)`; the picker makes the new paint.
// `choose()` opens the file dialog (the picker calls it when Picture is picked with no picture yet; a cancel leaves
// the fill as it was). The file goes out as the dialog's file:// url; the app turns it into a path.
Column {
    id: pic
    objectName: "picturePaint"
    property var paint: ({})
    signal changed(var fields)
    readonly property string file: paint && paint.picture ? String(paint.picture) : ""
    spacing: Theme.gap

    property bool switching: false        // the dialog was opened by picking Picture: a pick also sets the type
    function choose(switching) { pic.switching = !!switching; dialog.open() }
    function accept(url) {                // the dialog's pick (a scripted step hands one in: 2D click_steps `picturefile`)
        if (dialog.visible) dialog.close()
        pic.changed(Object.assign({ picture: String(url) }, pic.switching ? { type: "picture" } : {}))
        pic.switching = false
    }

    Item {                                // the file's name (shown here only) and a button that chooses another
        width: parent.width; height: Theme.field
        Text {
            visible: pic.file !== ""
            anchors.left: parent.left; anchors.right: fileButton.left; anchors.rightMargin: Theme.gap
            anchors.verticalCenter: parent.verticalCenter
            text: pic.file ? decodeURIComponent(pic.file.split(/[\\/]/).pop()) : ""
            elide: Text.ElideMiddle; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        }
        Button {
            id: fileButton
            objectName: "picturePaint:file"
            anchors.right: parent.right
            width: pic.file ? implicitWidth : parent.width
            text: pic.file ? "Change…" : "Choose picture…"
            onClicked: pic.choose(false)
        }
    }
    FileDialog {
        id: dialog
        title: "Choose a picture"
        nameFilters: ["Pictures (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"]
        onAccepted: pic.accept(selectedFile.toString())
    }
}
