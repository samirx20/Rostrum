import QtQuick
import "."

// A colour: the swatch alone fills the field box; a click (or Enter / Space) opens the colour picker beside it (to its
// left): square, hue, hex, pipette, the project's and the brand's swatches. `atRest` ("Mixed") shows in words beside a
// small swatch. Project / brand swatches come from the app's optional `colourBank`.
// One picker session = one undo: with `scrubbed` set (the inspector does) the changes go out as began() / live(hex) ...
// ended(); otherwise `edited(hex)` is sent once, with the last colour, when the picker closes.
FieldFrame {
    id: f
    property string hex: "#ffffff"
    property bool scrubbed: false
    signal edited(string value)
    signal began()
    signal live(string hex)
    signal ended()

    property string shown: hex           // what the swatch shows while the picker is open
    property bool changing: false
    onHexChanged: shown = hex
    activeFocusOnTab: true
    engaged: picker.visible
    text: ""
    leading: Rectangle {
        width: f.atRest ? 14 : f.width - 2 * Theme.gap; height: 14; radius: 3
        color: f.shown; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18)
    }
    function open() { picker.openBeside(f) }
    function settle() {           // the picker's open change ends: at the close, and before "+" saves a colour (a
        if (!f.changing) return   // document change of its own; the next edit in the picker starts a new undo step)
        f.changing = false
        if (f.scrubbed) f.ended(); else f.edited(f.shown)
    }
    function saveSwatch(hx) { f.settle(); if (picker.banked) colourBank.add(hx) }
    TapHandler { onTapped: f.open() }
    Keys.onReturnPressed: f.open()
    Keys.onSpacePressed: f.open()

    SidePopup {
        id: picker
        readonly property bool banked: typeof colourBank !== "undefined"
        onClosed: f.settle()
        ColorPicker {
            hex: f.shown; showAlpha: false
            project: picker.banked ? colourBank.project : []
            brand: picker.banked ? colourBank.brand : []
            brandName: picker.banked ? colourBank.brandName : ""
            onChanged: (hx) => {
                if (hx === f.shown) return
                f.shown = hx
                if (f.scrubbed) { if (!f.changing) f.began(); f.live(hx) }
                f.changing = true
            }
            onSwatchAdd: (hx) => f.saveSwatch(hx)
        }
    }
}
