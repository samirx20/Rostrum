import QtQuick
import QtQuick.Controls as QQC
import "."

// The kit's one popup: every menu, dropdown, flyout and small panel is built on it (Menu, ChoiceField, Popover, SidePopup,
// ToolFlyout, the Record panel …). Only a dialog with a scrim (`modal: true`: Preferences, Report a problem) blocks the window.
// Why: a plain QQC.Popup closes on Esc by itself, and while one with that Esc is open Qt stops EVERY window shortcut
// (Ctrl+Z, Space, Delete ... all dead until it closes). This one closes on a click outside, and on Esc through its own
// Shortcut (only the popup opened last: OpenPopups.top), so the window's other keys keep working. The keys it uses
// itself go in `ownKeys` (a menu's Up / Down / Enter): the window's shortcuts for those wait while it is open
// (OpenPopups.takes). `escaped()` comes before the close (an app can take a change back).
QQC.Popup {
    id: pop
    closePolicy: QQC.Popup.CloseOnPressOutside
    property var ownKeys: []
    property bool escCloses: true               // false: Esc means something else here for now (a paint stroke held)
    signal escaped()
    onOpened: OpenPopups.add(pop)
    onClosed: OpenPopups.remove(pop)
    Component.onDestruction: OpenPopups.remove(pop)
    Shortcut { sequence: "Escape"; enabled: pop.opened && pop.escCloses && OpenPopups.top === pop
               onActivated: { pop.escaped(); pop.close() } }
}
