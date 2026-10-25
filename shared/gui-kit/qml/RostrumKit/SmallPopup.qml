import QtQuick
import QtQuick.Controls as QQC
import "."

// A small popup (a few choices, a few settings) that leaves the window's keys alone. A plain QQC.Popup closes on Esc by
// itself, and while it is open Qt stops EVERY window shortcut (Ctrl+Z, Space, Delete ... all dead until it closes).
// So this one closes on a click outside, and on Esc through its own Shortcut (the KeyMap's Esc waits while one is open,
// OpenPopups): the window's other keys keep working.
QQC.Popup {
    id: pop
    closePolicy: QQC.Popup.CloseOnPressOutside
    property bool counted: false
    onOpened: { counted = true; OpenPopups.count++ }
    onClosed: if (counted) { counted = false; OpenPopups.count-- }
    Component.onDestruction: if (counted) OpenPopups.count--
    Shortcut { sequence: "Escape"; enabled: pop.opened; onActivated: pop.close() }
}
