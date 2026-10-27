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
// Motion (Theme, principle 10): it fades in over Theme.popupIn while drifting Theme.popupShift px from its anchor's side
// (`shiftY` > 0: from above, as under a button; < 0 from below; `shiftX` sideways), drawn by a shift of its picture only,
// so its x / y (and any binding on them) are never touched. Reduce motion: it is simply there. `quickClose`: the close
// is instant (a menu's pick runs on its close: it must not wait for a fade).
// Its opener's area (principle 8): `openerArea` is the window's focus area when it opened (AppShell.focusArea); a press
// inside it keeps that area (ack.PopupPresses), so Ctrl+A and Delete after a click in it act where the person was.
QQC.Popup {
    id: pop
    closePolicy: QQC.Popup.CloseOnPressOutside
    property var ownKeys: []
    property bool escCloses: true               // false: Esc means something else here for now (a paint stroke held)
    property real shiftX: 0
    property real shiftY: Theme.popupShift
    property bool quickClose: false
    property string openerArea: ""
    signal escaped()
    function settle() { Place.settle(contentItem) }     // lay the content out now: its size is the one it will have shown
    Translate { id: drift }
    onAboutToShow: {
        const w = pop.parent && pop.parent.Window ? pop.parent.Window.window : null
        openerArea = w && typeof w.focusArea === "string" ? w.focusArea : ""
        const host = pop.contentItem ? pop.contentItem.parent : null       // the popup's own item (content + background)
        if (host && host.transform.length === 0) host.transform = [drift]
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.popupIn; easing.type: Easing.OutCubic }
            NumberAnimation { target: drift; property: "y"; from: -pop.shiftY; to: 0
                              duration: Theme.popupIn; easing.type: Easing.OutCubic }
            NumberAnimation { target: drift; property: "x"; from: -pop.shiftX; to: 0
                              duration: Theme.popupIn; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: pop.quickClose ? 0 : Theme.popupIn } }
    onOpened: OpenPopups.add(pop)
    onAboutToHide: OpenPopups.remove(pop)       // a popup fading out is no longer the one Esc closes: the next Esc goes past it
    onClosed: { OpenPopups.remove(pop); drift.x = 0; drift.y = 0 }
    Component.onDestruction: OpenPopups.remove(pop)
}
