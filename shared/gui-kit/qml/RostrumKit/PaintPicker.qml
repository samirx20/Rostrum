import QtQuick
import "."
import "ColourMath.js" as M

// The whole fill picker: the fill type (none · solid · linear · radial · angular · picture), for a gradient its bar and
// the reverse button, then the colour picker for the solid colour or the chosen stop. Every change is a new `paint`
// object out (`edited`), the one in is never touched.
//   paint: {type, color, stops: [{at, color, opacity}], angle, cx, cy, picture, fit, scale}
Column {
    id: pp
    property var paint: ({ type: "solid", color: "#ffffff" })
    property var types: ["none", "solid", "linear", "radial", "angular"]
    property int maxStops: 8
    property bool stopOpacity: true       // false: stops have no alpha strip
    property var project: []
    property var brand: []
    property string brandName: ""
    signal edited(var paint)
    signal swatchAdd(string hex)          // the "+": the field ends its open change first, then saves (PaintField)

    readonly property string type: paint && paint.type ? paint.type : "solid"
    readonly property bool gradient: type === "linear" || type === "radial" || type === "angular"
    readonly property var stops: paint && paint.stops ? paint.stops : []
    readonly property int sel: Math.max(0, Math.min(bar.selected, stops.length - 1))
    readonly property var stop: gradient && stops.length ? stops[sel] : null
    readonly property string base: paint && paint.color ? paint.color : "#ffffff"      // the colour a switch starts from
    readonly property var names: ({ none: "No fill", solid: "Solid colour", linear: "Linear gradient", radial: "Radial gradient",
                                    angular: "Angular gradient", picture: "Picture" })
    width: 234; spacing: Theme.gap

    function change(fields) { edited(Object.assign({}, paint, fields)) }
    function stopsWith(i, fields) { return stops.map((s, k) => k === i ? Object.assign({}, s, fields) : Object.assign({}, s)) }
    function setType(t) {
        if (t === type) return
        if (t === "picture" && !(paint && paint.picture)) { picture.choose(true); return }   // the picture first
        const f = { type: t }
        const cur = gradient && stop ? stop.color : base
        if (t === "solid" || t === "picture" || t === "none") f.color = cur
        else {
            if (!stops.length) f.stops = [{ at: 0, color: cur, opacity: 1 }, { at: 1, color: M.shade(cur), opacity: 1 }]
            if (paint.angle === undefined) f.angle = 90
            if (t === "radial" || t === "angular") { if (paint.cx === undefined) f.cx = 0.5; if (paint.cy === undefined) f.cy = 0.5 }
            if (!gradient) bar.selected = 0
        }
        change(f)
    }
    function moveStop(text) {          // typed place of the chosen stop, in %
        const at = M.clamp01(parseFloat(text) / 100)
        const arr = stopsWith(sel, { at: at })
        const item = arr[sel], out = M.sorted(arr)
        bar.selected = out.indexOf(item)
        change({ stops: out })
    }

    Row {   // the type, then (a gradient) whole shape and reverse: the buttons narrow a little when all are there
        id: typeRow
        width: parent.width; spacing: 2
        readonly property int count: pp.types.length + 1 + (wholeShape.visible ? 1 : 0)
        readonly property real cell: Math.min(28, (pp.width - spacing * count) / count)
        Repeater {
            model: pp.types
            delegate: IconButton {
                required property string modelData
                objectName: "fillType:" + modelData        // scripted clicks find it (2D click_steps.py)
                kind: "ghost"; down: modelData === pp.type
                width: typeRow.cell; height: 28; tip: pp.names[modelData]
                onClicked: pp.setType(modelData)
                PaintIcon { anchors.centerIn: parent; kind: parent.modelData; ink: parent.ink }
            }
        }
        Item { width: Math.max(0, pp.width - typeRow.cell * typeRow.count - typeRow.spacing * typeRow.count); height: 1 }
        IconButton {   // only once the canvas handles set the gradient's own length: back to covering the whole shape
            id: wholeShape
            objectName: "wholeShape"; visible: pp.gradient && !!pp.paint && pp.paint.span === "points"
            kind: "ghost"; width: typeRow.cell; height: 28; tip: "Cover the whole shape again"
            onClicked: pp.change({ span: "box" })
            PaintIcon { anchors.centerIn: parent; kind: "whole"; ink: parent.ink }
        }
        IconButton {
            objectName: "reverseStops"; visible: pp.gradient; kind: "ghost"; width: typeRow.cell; height: 28; tip: "Reverse the stops"
            onClicked: pp.change({ stops: M.reversed(pp.stops) })
            PaintIcon { anchors.centerIn: parent; kind: "swap"; ink: parent.ink }
        }
    }

    GradientBar {
        id: bar
        visible: pp.gradient
        width: parent.width
        stops: pp.stops; maxStops: pp.maxStops
        onEdited: (arr) => pp.change({ stops: arr })
    }

    ColorPicker {
        visible: pp.type === "solid" || pp.gradient
        hex: pp.gradient && pp.stop ? pp.stop.color : pp.base
        alpha: pp.gradient && pp.stop && pp.stop.opacity !== undefined ? pp.stop.opacity : 1
        showAlpha: pp.gradient && pp.stopOpacity
        extra: pp.gradient && pp.stop ? String(Math.round(pp.stop.at * 100)) : ""
        project: pp.project; brand: pp.brand; brandName: pp.brandName
        onChanged: (hx, a) => {
            if (pp.gradient) pp.change({ stops: pp.stopsWith(pp.sel, { color: hx, opacity: a }) })
            else pp.change({ color: hx })
        }
        onExtraEdited: (t) => pp.moveStop(t)
        onSwatchAdd: (hx) => pp.swatchAdd(hx)
    }

    PicturePaint {
        id: picture
        visible: pp.type === "picture"
        width: parent.width
        paint: pp.paint
        onChanged: (fields) => pp.change(fields)
    }
    Text { visible: pp.type === "none"; text: "No fill"; color: Theme.fg3; font.pixelSize: Theme.body; font.family: uiFont }
}
