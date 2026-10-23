import QtQuick
import QtQuick.Dialogs
import "."

// The paint picker's Picture part: the picture (its file name; a click chooses another), how it sits in the layer's
// box (Fill · Fit · Tile · Stretch) and its scale. Every change is `changed(fields)`; the picker makes the new paint.
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

    Button {
        objectName: "picturePaint:file"
        width: parent.width
        text: pic.file ? decodeURIComponent(pic.file.split(/[\\/]/).pop()) : "Choose picture…"
        onClicked: pic.choose(false)
    }
    Segmented {
        objectName: "picturePaint:fit"
        width: parent.width
        visible: pic.file !== ""
        options: [{ value: "fill", label: "Fill" }, { value: "fit", label: "Fit" },
                  { value: "tile", label: "Tile" }, { value: "stretch", label: "Stretch" }]
        current: pic.paint && pic.paint.fit ? pic.paint.fit : "fill"
        onPicked: (v) => pic.changed({ fit: v })
    }
    Row {
        visible: pic.file !== ""
        width: parent.width; spacing: Theme.gap
        Text { id: scaleName; text: "Scale"; anchors.verticalCenter: parent.verticalCenter
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        NumberField {
            objectName: "picturePaint:scale"
            width: parent.width - scaleName.width - Theme.gap
            value: pic.paint && pic.paint.scale !== undefined ? pic.paint.scale : 1
            from: 0.01; to: 100; step: 0.01; display: "percent"; defaultValue: 1
            onEdited: (v) => pic.changed({ scale: v })
            onScrubbed: (v) => pic.changed({ scale: v })
        }
    }

    FileDialog {
        id: dialog
        title: "Choose a picture"
        nameFilters: ["Pictures (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"]
        onAccepted: pic.accept(selectedFile.toString())
    }
}
