import QtQuick
import "."

// A colour: a swatch square and its hex code beside it (SwatchHex). A click on the square opens the colour picker
// beside it (to its left): square, hue, hex, pipette, the project's and the brand's swatches; a hex typed in the box
// is one change (`edited`). `atRest` ("Mixed") shows in words in place of the hex. Project / brand swatches come from
// the app's optional `colourBank`.
// One picker session = one undo: with `scrubbed` set (the inspector does) the changes go out as began() / live(hex) ...
// ended(); otherwise `edited(hex)` is sent once, with the last colour, when the picker closes.
SwatchHex {
    id: f
    property string hex: "#ffffff"
    property string atRest: ""
    property bool scrubbed: false
    signal edited(string value)
    signal began()
    signal live(string hex)
    signal ended()

    property string shown: hex           // what the swatch shows while the picker is open
    property bool changing: false
    onHexChanged: shown = hex
    look: f.atRest !== "" ? ({ type: "mixed" }) : ({ type: "solid", color: f.shown })   // several colours: an empty swatch, not one of them
    words: f.atRest
    engaged: picker.visible
    onPick: f.open()
    onTyped: (hx) => f.edited(hx)
    function open() { picker.openBeside(f) }
    function settle() {           // the picker's open change ends: at the close, and before "+" saves a colour (a
        if (!f.changing) return   // document change of its own; the next edit in the picker starts a new undo step)
        f.changing = false
        if (f.scrubbed) f.ended(); else f.edited(f.shown)
    }
    function saveSwatch(hx) { f.settle(); if (picker.banked) colourBank.add(hx) }

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
