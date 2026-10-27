import QtQuick
import QtQuick.Dialogs
import RostrumKit

// Project a picture from <shot> (screen3d/project_qt.py): right-click › Project a picture from Hero 01… opens this short
// menu where the right-click menu was: each rendered 2D item of the project (linked: re-render it in 2D and the
// projection follows) and "A picture file…" (a file dialog). The choice is one change on the selected shapes.
Item {
    id: pp
    property point at: Qt.point(0, 0)
    function openAt(x, y) { at = Qt.point(x, y) }
    Connections {
        target: projector
        function onAsked(entries) {
            menu.entries = entries
            menu.openAt(pp.at.x, pp.at.y)
        }
    }
    ActionMenu {
        id: menu
        objectName: "projectMenu3d"
        onPicked: (v) => v === "file" ? dialog.open() : projector.project(v)
    }
    FileDialog {
        id: dialog
        objectName: "projectDialog"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Pictures (*.png *.jpg *.jpeg *.tif *.tiff *.exr *.webp)"]
        options: files.useNative ? 0 : FileDialog.DontUseNativeDialog
        onAccepted: projector.project(selectedFile.toString())
    }
}
