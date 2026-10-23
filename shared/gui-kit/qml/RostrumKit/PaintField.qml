import QtQuick
import "."
import "ColourMath.js" as M

// A fill in the inspector: a small preview (the colour, the gradient, a chequer for none) and its name ("Solid",
// "Linear · 3 stops"); never the hex as text. A click opens the PaintPicker beside it (to its left).
// One picker session = one undo: began() on the first change, live(paint) while it goes on, ended() when the picker closes.
// With `scrubbed` off, `edited(paint)` is sent once at the close instead (as ColorField does).
FieldFrame {
    id: f
    property var paint: ({ type: "none" })
    property var types: ["none", "solid", "linear", "radial", "angular", "image"]
    property int maxStops: 8
    property bool stopOpacity: true
    property bool scrubbed: false
    signal edited(var paint)
    signal began()
    signal live(var paint)
    signal ended()
    signal chooseImage()

    property var cur: paint               // what the swatch shows while the picker is open
    property bool changing: false
    onPaintChanged: cur = paint
    readonly property string kind: cur && cur.type ? cur.type : "none"
    readonly property int count: cur && cur.stops ? cur.stops.length : 0
    readonly property string name: ({ none: "None", solid: "Solid", image: "Picture",
        linear: "Linear · " + count + " stops", radial: "Radial · " + count + " stops",
        angular: "Angular · " + count + " stops" })[kind] || "Solid"

    activeFocusOnTab: true
    engaged: picker.visible
    text: ""
    atRest: name
    leading: Item {
        width: 14; height: 14
        Checker { anchors.fill: parent; radius: 3; cell: 4; visible: f.kind !== "solid" }
        Canvas {
            anchors.fill: parent
            property var shown: f.cur
            onShownChanged: requestPaint()
            onPaint: {
                const g = getContext("2d"), t = f.kind, w = width
                g.reset()
                g.roundedRect(0, 0, w, w, 3, 3); g.clip()
                if (t === "solid" || t === "image") { g.fillStyle = M.rgba(f.cur.color || "#808080", 1); g.fillRect(0, 0, w, w) }
                else if (t === "none") { g.strokeStyle = "#c0392b"; g.lineWidth = 1.2; g.beginPath(); g.moveTo(1, w - 1); g.lineTo(w - 1, 1); g.stroke() }
                else {
                    const grad = t === "radial" ? g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w * 0.7)
                               : t === "angular" ? g.createConicalGradient(w / 2, w / 2, 0)
                               : g.createLinearGradient(0, 0, w, 0)
                    M.addStops(grad, M.sorted(f.cur.stops || []))
                    g.fillStyle = grad; g.fillRect(0, 0, w, w)
                }
            }
        }
        Rectangle { anchors.fill: parent; radius: 3; color: "transparent"; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18) }
    }
    function open() { picker.openBeside(f) }
    TapHandler { onTapped: f.open() }
    Keys.onReturnPressed: f.open()
    Keys.onSpacePressed: f.open()

    SidePopup {
        id: picker
        readonly property bool banked: typeof colourBank !== "undefined"
        onClosed: {
            if (!f.changing) return
            f.changing = false
            if (f.scrubbed) f.ended(); else f.edited(f.cur)
        }
        PaintPicker {
            paint: f.cur; types: f.types; maxStops: f.maxStops; stopOpacity: f.stopOpacity
            project: picker.banked ? colourBank.project : []
            brand: picker.banked ? colourBank.brand : []
            brandName: picker.banked ? colourBank.brandName : ""
            onEdited: (p) => {
                f.cur = p
                if (f.scrubbed) { if (!f.changing) f.began(); f.live(p) }
                f.changing = true
            }
            onChooseImage: f.chooseImage()
        }
    }
}
