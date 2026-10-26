import QtQuick
import QtQuick.Controls as QQC
import "."
import "MenuPlace.js" as Place

// The kit's one popup: every menu, dropdown, flyout and small panel is built on it (Menu, ChoiceField, Popover, SidePopup,
// ToolFlyout, the Record panel …) and every dialog: a dialog with a scrim (`modal: true`: Preferences, Keys, About)
// blocks the window. Why: a plain QQC.Popup closes on Esc by itself, and while one with that Esc is open Qt stops EVERY
// window shortcut (Ctrl+Z, Space, Delete ... all dead until it closes); its Esc also only works while it has the keyboard.
// This one closes on a click outside, and on Esc through the window's one Esc (AppShell: OpenPopups.closeTop closes the
// popup opened last, wherever the keyboard is), so the window's other keys keep working. The keys it uses
// itself go in `ownKeys` (a menu's Up / Down / Enter): the window's shortcuts for those wait while it is open
// (OpenPopups.takes). `escaped()` comes before the close (an app can take a change back).
// A popup is sized and placed BEFORE it shows and never moves while it is visible (a menu that moved under a still pointer
// made a click land on another row): each kind calls `settle()` first and places itself once from its true size.
QQC.Popup {
    id: pop
    closePolicy: QQC.Popup.CloseOnPressOutside
    property var ownKeys: []
    property bool escCloses: true               // false: Esc means something else here for now (a paint stroke held)
    signal escaped()
    function settle() { Place.settle(contentItem) }     // lay the content out now: its size is the one it will have shown
    onOpened: OpenPopups.add(pop)
    onAboutToHide: OpenPopups.remove(pop)       // a popup fading out is no longer the one Esc closes: the next Esc goes past it
    onClosed: OpenPopups.remove(pop)
    Component.onDestruction: OpenPopups.remove(pop)
}
