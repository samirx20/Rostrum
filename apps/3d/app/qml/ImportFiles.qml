import QtQuick
import QtQuick.Dialogs

// The rail's Import group (Rail3D.qml; importing.py): a format's entry opens the system's file dialog showing only
// that format's files; the file picked lands at once on the surface in the middle of the view, selected, the tool
// Select again. Asset library opens the asset sheet.
Item {
    id: files
    objectName: "importFiles"
    property bool useNative: true     // false: Qt's own dialog inside the window (a check's window behind the person's work)
    function open(name) {
        if (name === "library") return backend.importer.openLibrary()
        dialog.nameFilters = backend.importer.nameFilters(name)
        dialog.title = "Import " + backend.importer.label(name)
        dialog.open()
    }
    FileDialog {
        id: dialog
        objectName: "importDialog"
        fileMode: FileDialog.OpenFile
        options: files.useNative ? 0 : FileDialog.DontUseNativeDialog
        onAccepted: backend.importer.importAtCentre(selectedFile.toString())
    }
}
