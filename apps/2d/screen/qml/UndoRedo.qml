import QtQuick
import RostrumKit

// Undo and Redo in the top bar, each only while it has something to do (never greyed). Small, so the history text beside
// them keeps its room; the tip says what each would take back or bring back (keys: Ctrl+Z, Ctrl+Shift+Z).
Row {
    spacing: Theme.grid
    visible: backend.undoLabel !== "" || backend.redoLabel !== ""
    IconButton {
        visible: backend.undoLabel !== ""
        glyph: "↶"; kind: "ghost"; tip: "Undo: " + backend.undoLabel + "  (Ctrl Z)"; onClicked: backend.undo()
    }
    IconButton {
        visible: backend.redoLabel !== ""
        glyph: "↷"; kind: "ghost"; tip: "Redo: " + backend.redoLabel + "  (Ctrl Shift Z)"; onClicked: backend.redo()
    }
}
