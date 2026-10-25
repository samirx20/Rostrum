import QtQuick
import QtQuick.Controls as QQC
import "."
import "ColourMath.js" as M

// A fill in the inspector: a swatch square (the colour, the gradient, a chequer for none, a picture or painting's own
// picture) and beside it the hex code of a solid colour (typed in place: one change) or the fill's name ("Linear · 3
// stops", "None", a painting's name). A click on the square (or on the name) opens the PaintPicker beside it (to its left).
// One whole change in the picker = one undo: began() on its first step, live(paint) while it goes on, ended() when it is
// done (a colour drag let go, a hex or swatch taken: PaintPicker.done; a painting, a fit, a picture file at once) or the
// picker closes. Painted's New
// painting is the app's: `asked(add)` after the open change ends (a new painting is a change of its own); so is Paint it
// (`asked(paintIt)`: the picker closes and the app's brush paints the painting).
// Painted, the paintings to pick (`sources`) and the rows drawn under Fit (`rows`, `rowsBridge`, `rowsHost`) come from
// the app; InspectorRow hands in its row's.
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
    signal asked(string action)
    property var sources: []
    property string add: ""               // the app's action for Painted's New painting ("" = no Painted)
    property string paintIt: ""           // the app's action for Paint it ("" = none)
    property string paintItNote: ""       // the words beside it ("used by 3 layers")
    property var rows: null
    property var rowsBridge: null
    property string rowsHost: ""

    property var cur: paint               // what the swatch shows while the picker is open
    property bool changing: false
    readonly property int stop: pk.item ? pk.item.stopSel : -1
    onPaintChanged: cur = paint
    readonly property string kind: cur && cur.type ? cur.type : "none"
    readonly property int count: cur && cur.stops ? cur.stops.length : 0
    readonly property string name: ({ none: "None", solid: "Solid", picture: "Picture",
        painted: cur && cur.name ? cur.name : "Painted",
        linear: "Linear · " + count + " stops", radial: "Radial · " + count + " stops",
        angular: "Angular · " + count + " stops" })[kind] || kind      // a kind it doesn't know reads as itself, never "Solid"

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
    function take(p) {
        f.cur = p
        if (f.scrubbed) { if (!f.changing) f.began(); f.live(p) }
        f.changing = true
    }

    // The picker is made at the first opening only: a settings panel has a colour or a fill on most kinds' rows, and a
    // popup with its whole picker per field made each selection switch slower (~40 ms for a fill).
    Loader { id: pk; active: false; sourceComponent: pickerPopup }
    Component { id: pickerPopup
    SidePopup {
        id: picker
        readonly property alias stopSel: body.sel
        readonly property bool banked: typeof colourBank !== "undefined"
        closePolicy: PaintSession.hold && PaintSession.field === f ? QQC.Popup.NoAutoClose : QQC.Popup.CloseOnPressOutside   // Esc: SmallPopup's
        onOpened: PaintSession.field = f
        onClosed: { f.settle(); body.browsing = false; if (PaintSession.field === f) PaintSession.field = null }
        PaintPicker {
            id: body
            paint: f.cur; maxStops: f.maxStops; stopOpacity: f.stopOpacity
            project: picker.banked ? colourBank.project : []
            brand: picker.banked ? colourBank.brand : []
            brandName: picker.banked ? colourBank.brandName : ""
            sources: f.sources; rows: f.rows; rowsBridge: f.rowsBridge; rowsHost: f.rowsHost
            paintIt: f.paintIt; paintItNote: f.paintItNote
            types: f.add === "" ? f.types.filter(t => t !== "painted") : f.types
            onEdited: (p) => f.take(p)
            onChosen: (p) => { f.take(p); f.settle() }
            onDone: f.settle()
            onAdded: { f.settle(); f.asked(f.add) }
            onPaintAsked: { picker.close(); f.asked(f.paintIt) }
            onSwatchAdd: (hx) => f.saveSwatch(hx)
        }
    }
    }
}
