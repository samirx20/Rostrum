import QtQuick
import QtQuick.Dialogs
import RostrumKit

// What the file actions ask before they act (screen2d/files.py does the work): "save changes?" before New, Open or
// closing with unsaved changes; a name for Save as; the open dialog; and, on open, whether to restore a recovery copy.
// The shortcuts live here too. act(key) is the one way in: the File menu, Ctrl+K (files.wanted) and the shortcuts.
Item {
    id: flow
    property var window
    property var next: null              // what to do once the question is answered
    property string asking: ""           // which question is open: save | name | recovery

    function act(key) {
        if (key === "file:new") whenSaved(() => files.newProject(""))
        else if (key === "file:open") whenSaved(() => openDialog.open())
        else if (key.startsWith("file:recent:")) whenSaved(() => files.openRecent(parseInt(key.split(":")[2])))
        else if (key === "file:saveas") askName()
        else if (key === "file:save" && files.unsaved) save(null)
    }
    function save(then) {               // a document with no project folder yet asks its name first
        if (files.hasFolder) { if (files.save() && then) then() }
        else askName()
    }
    function whenSaved(then) {
        if (!files.unsaved) return then()
        next = then; asking = "save"
        dlg.ask("Save changes to " + files.name + "?", "Your changes will be lost if you don't save them.",
                [{ value: "cancel", label: "Cancel" }, { value: "discard", label: "Don't save", danger: true },
                 { value: "save", label: "Save" }])
    }
    function askName() {
        asking = "name"
        dlg.ask(files.hasFolder ? "Save as a new project" : "Save project",
                "A new project folder is made in " + files.projectsFolder + ".",
                [{ value: "cancel", label: "Cancel" }, { value: "save", label: "Save" }], files.suggestedName)
    }
    function askRecovery() {
        asking = "recovery"
        dlg.ask("Restore unsaved changes?", "Rostrum2D closed without saving " + files.name
                + ". Restore the changes made " + files.recoveryAt + "?",
                [{ value: "discard", label: "Discard", danger: true }, { value: "restore", label: "Restore" }])
    }
    function closing(close) {           // the window's close button
        if (window.leaving || !files.unsaved) return
        close.accepted = false
        whenSaved(() => { window.leaving = true; window.close() })
    }

    Component.onCompleted: if (files.recoveryAt !== "") Qt.callLater(askRecovery)
    Connections { target: files; function onWanted(key) { flow.act(key) } }

    Shortcut { sequence: "Ctrl+N"; onActivated: flow.act("file:new") }
    Shortcut { sequence: "Ctrl+O"; onActivated: flow.act("file:open") }
    Shortcut { sequence: "Ctrl+S"; onActivated: flow.act("file:save") }
    Shortcut { sequence: "Ctrl+Shift+S"; onActivated: flow.act("file:saveas") }

    AskDialog {
        id: dlg
        objectName: "fileQuestion"
        onAnswered: (value, name) => {
            const then = flow.next
            flow.next = null
            if (flow.asking === "save") {
                if (value === "save") flow.save(then)
                else if (value === "discard") { files.discard(); then() }
            } else if (flow.asking === "name") {
                if (value === "save") files.saveAs(name)
            } else if (flow.asking === "recovery") {
                if (value === "restore") files.restore()
                else files.discard()
            }
        }
    }
    FileDialog {
        id: openDialog
        title: "Open a Rostrum2D project"
        currentFolder: "file:///" + files.projectsFolder.replace(/\\/g, "/")
        nameFilters: ["Rostrum2D documents (*.mtn)"]
        onAccepted: files.openPath(selectedFile.toString())
    }
}
