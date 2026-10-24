import QtQuick
import QtQuick.Controls as QQC
import "."
import "ColourMath.js" as M

// A fill in the inspector: a swatch square (the colour, the gradient, a chequer for none) and beside it the hex code
// of a solid colour (typed in place: one change) or the fill's name ("Linear · 3 stops", "None"). A click on the
// square (or on the name) opens the PaintPicker beside it (to its left).
// One picker session = one undo: began() on the first change, live(paint) while it goes on, ended() when the picker closes.
// With `scrubbed` off, `edited(paint)` is sent once at the close instead (as ColorField does). While open it is
// PaintSession.field, so the canvas can show the gradient's handles (`stop`: the picked stop).
SwatchHex {
    id: f
    objectName: "paintField"
    property var paint: ({ type: "none" })
    property var types: ["none", "solid", "linear", "radial", "angular"]
    property int maxStops: 8
    property bool stopOpacity: true
    property bool scrubbed: false
    signal edited(var paint)
    signal began()
    signal live(var paint)
    signal ended()

    property var cur: paint               // what the swatch shows while the picker is open
    property bool changing: false
    readonly property int stop: pk.item ? pk.item.stopSel : -1
    onPaintChanged: cur = paint
    readonly property string kind: cur && cur.type ? cur.type : "none"
    readonly property int count: cur && cur.stops ? cur.stops.length : 0
    readonly property string name: ({ none: "None", solid: "Solid", picture: "Picture",
        linear: "Linear · " + count + " stops", radial: "Radial · " + count + " stops",
        angular: "Angular · " + count + " stops" })[kind] || "Solid"

    property string atRest: ""
    look: f.cur
    words: f.atRest !== "" ? f.atRest : f.kind === "solid" ? "" : f.name
    engaged: pk.item ? pk.item.visible : false
    onPick: f.open()
    onTyped: (hx) => f.edited(Object.assign({}, f.paint, { type: "solid", color: hx }))
    function open() { pk.active = true; pk.item.openBeside(f) }
    function settle() {           // the picker's open change ends: at the close, and before "+" saves a colour (a
        if (!f.changing) return   // document change of its own; the next edit in the picker starts a new undo step)
        f.changing = false
        if (f.scrubbed) f.ended(); else f.edited(f.cur)
    }
    function saveSwatch(hx) { f.settle(); if (typeof colourBank !== "undefined") colourBank.add(hx) }

    // The picker is made at the first opening only: a settings panel has a colour or a fill on most kinds' rows, and a
    // popup with its whole picker per field made each selection switch slower (~40 ms for a fill).
    Loader { id: pk; active: false; sourceComponent: pickerPopup }
    Component { id: pickerPopup
    SidePopup {
        id: picker
        readonly property alias stopSel: body.sel
        readonly property bool banked: typeof colourBank !== "undefined"
        closePolicy: PaintSession.hold && PaintSession.field === f ? QQC.Popup.CloseOnEscape
                                                                   : QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape
        onOpened: PaintSession.field = f
        onClosed: { f.settle(); if (PaintSession.field === f) PaintSession.field = null }
        PaintPicker {
            id: body
            paint: f.cur; types: f.types; maxStops: f.maxStops; stopOpacity: f.stopOpacity
            project: picker.banked ? colourBank.project : []
            brand: picker.banked ? colourBank.brand : []
            brandName: picker.banked ? colourBank.brandName : ""
            onEdited: (p) => {
                f.cur = p
                if (f.scrubbed) { if (!f.changing) f.began(); f.live(p) }
                f.changing = true
            }
            onSwatchAdd: (hx) => f.saveSwatch(hx)
        }
    }
    }
}
