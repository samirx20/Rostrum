import QtQuick
import "."
import "ColourMath.js" as M

// The whole fill picker: the fill type (none · solid · linear · radial · angular · picture · painted), for a gradient its
// bar and the reverse button, then the colour picker for the solid colour or the chosen stop. Every change is a new
// `paint` object out (`edited`, live; `chosen`, a pick that is a whole change at once), the one in is never touched.
// Picture and Painted are one thing with two sources (a picture filling the box): the source (a file; a painting among
// `sources`, tiles), then how it covers the box (Fill · Fit · Tile · Stretch), then the app's own rows for the rest (Scale,
// Offset …: `rows`, a model of the settings panel's rows, those marked `inside` this field drawn by the kit's
// InspectorRow with their key marks, each its own change through `rowsBridge`). Painted with no painting yet asks for a
// new one at once (`added`); with some, the tiles show first and a click on one uses it. A painted fill ends with Paint it
// (`paintAsked`: the app's brush paints the painting, through this layer) and how many layers use it.
//   paint: {type, color, stops: [{at, color, opacity}], angle, cx, cy, picture, painting, fit}
Column {
    id: pp
    property var paint: ({ type: "solid", color: "#ffffff" })
    property var types: ["none", "solid", "linear", "radial", "angular"]
    property int maxStops: 8
    property bool stopOpacity: true       // false: stops and a solid colour have no alpha strip
    property var project: []
    property var brand: []
    property string brandName: ""
    property var sources: []              // Painted: the paintings there are [{value, label, picture, note}]
    property var rows: null               // the rows drawn under Fit (a RowsModel), those `inside` == rowsHost
    property var rowsBridge: null
    property string rowsHost: ""
    signal edited(var paint)
    signal chosen(var paint)
    signal added()                        // Painted's New painting (the field ends its open change first)
    signal paintAsked()                   // Paint it (the field closes the picker and asks the app)
    property string paintIt: ""           // the app's Paint it action ("" = no Paint it)
    property string paintItNote: ""
    signal swatchAdd(string hex)          // the "+": the field ends its open change first, then saves (PaintField)

    readonly property string type: paint && paint.type ? paint.type : "solid"
    property bool browsing: false         // Painted picked while another fill is on: the tiles show, nothing changes yet
    readonly property string shown: browsing && type !== "painted" ? "painted" : type
    readonly property bool raster: shown === "painted" ? type === "painted" : type === "picture" && !!(paint && paint.picture)
    readonly property bool gradient: type === "linear" || type === "radial" || type === "angular"
    readonly property bool coloured: !browsing && (type === "solid" || gradient)     // the colour parts show
    readonly property var stops: paint && paint.stops ? paint.stops : []
    readonly property int sel: Math.max(0, Math.min(bar.selected, stops.length - 1))
    readonly property var stop: gradient && stops.length ? stops[sel] : null
    readonly property string base: paint && paint.color ? paint.color : "#ffffff"      // the colour a switch starts from
    readonly property var names: ({ none: "No fill", solid: "Solid colour", linear: "Linear gradient", radial: "Radial gradient",
                                    angular: "Angular gradient", picture: "Picture", painted: "Painted" })
    width: shown === "painted" || shown === "picture" ? 256 : 234; spacing: Theme.gap    // the rows' labels need a little more

    function change(fields) { edited(Object.assign({}, paint, fields)) }
    function stopsWith(i, fields) { return stops.map((s, k) => k === i ? Object.assign({}, s, fields) : Object.assign({}, s)) }
    function setType(t) {
        browsing = false
        if (t === type) return
        if (t === "picture" && !(paint && paint.picture)) { picture.choose(true); return }   // the picture first
        if (t === "painted") { if (sources.length) browsing = true; else added(); return }  // a painting first
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
        readonly property real cell: Math.min(28, (pp.width - spacing * (count + 1) - 1) / count)
        Repeater {
            model: pp.types
            delegate: IconButton {
                required property string modelData
                objectName: "fillType:" + modelData        // scripted clicks find it (2D click_steps.py)
                kind: "ghost"; down: modelData === pp.shown
                width: typeRow.cell; height: 28; tip: pp.names[modelData]
                onClicked: pp.setType(modelData)
                PaintIcon { anchors.centerIn: parent; kind: parent.modelData; ink: parent.ink }
            }
        }
        Rectangle { visible: pp.gradient && pp.coloured; width: 1; height: 16; anchors.verticalCenter: parent.verticalCenter; color: Theme.border }  // types | gradient's own buttons
        IconButton {   // only once the canvas handles set the gradient's own length: back to covering the whole shape
            id: wholeShape
            objectName: "wholeShape"; visible: pp.gradient && pp.coloured && !!pp.paint && pp.paint.span === "points"
            kind: "ghost"; width: typeRow.cell; height: 28; tip: "Cover the whole shape again"
            onClicked: pp.change({ span: "box" })
            PaintIcon { anchors.centerIn: parent; kind: "whole"; ink: parent.ink }
        }
        IconButton {
            objectName: "reverseStops"; visible: pp.gradient && pp.coloured; kind: "ghost"; width: typeRow.cell; height: 28; tip: "Reverse the stops"
            onClicked: pp.change({ stops: M.reversed(pp.stops) })
            PaintIcon { anchors.centerIn: parent; kind: "swap"; ink: parent.ink }
        }
    }

    GradientBar {
        id: bar
        visible: pp.gradient && pp.coloured
        width: parent.width
        stops: pp.stops; maxStops: pp.maxStops
        onEdited: (arr) => pp.change({ stops: arr })
    }

    ColorPicker {
        visible: pp.coloured
        hex: pp.gradient && pp.stop ? pp.stop.color : pp.base
        alpha: pp.gradient ? (pp.stop && pp.stop.opacity !== undefined ? pp.stop.opacity : 1)
                           : (pp.paint && pp.paint.opacity !== undefined ? pp.paint.opacity : 1)    // solid: the fill's own
        showAlpha: (pp.gradient || pp.type === "solid") && pp.stopOpacity
        extra: pp.gradient && pp.stop ? String(Math.round(pp.stop.at * 100)) : ""
        project: pp.project; brand: pp.brand; brandName: pp.brandName
        onChanged: (hx, a) => {
            if (pp.gradient) pp.change({ stops: pp.stopsWith(pp.sel, { color: hx, opacity: a }) })
            else pp.change(pp.paint && pp.paint.opacity !== undefined ? { color: hx, opacity: a } : { color: hx })
        }
        onExtraEdited: (t) => pp.moveStop(t)
        onSwatchAdd: (hx) => pp.swatchAdd(hx)
    }

    PicturePaint {
        id: picture
        visible: pp.shown === "picture"
        width: parent.width
        paint: pp.paint
        onChanged: (fields) => pp.chosen(Object.assign({}, pp.paint, fields))
    }
    PaintedPaint {
        visible: pp.shown === "painted"
        width: parent.width
        sources: pp.sources
        current: pp.type === "painted" && pp.paint.painting ? pp.paint.painting : ""
        onChosen: (id) => { pp.browsing = false; pp.chosen(Object.assign({}, pp.paint, { type: "painted", painting: id })) }
        onAdded: { pp.browsing = false; pp.added() }
    }
    Segmented {   // how the picture or painting covers the layer's box
        objectName: "paintFit"
        visible: pp.raster
        width: parent.width
        options: [{ value: "fill", label: "Fill" }, { value: "fit", label: "Fit" },
                  { value: "tile", label: "Tile" }, { value: "stretch", label: "Stretch" }]
        current: pp.paint && pp.paint.fit ? pp.paint.fit : "fill"
        onPicked: (v) => pp.chosen(Object.assign({}, pp.paint, { fit: v }))
    }
    Loader {      // the app's rows for the rest (Scale, Offset, …): made the first time they can show, off the click (a
        id: rowsPart  // click answers at once, the rows ease in over the next frames), then kept while the picker lives
        readonly property bool wanted: pp.raster && !!pp.rows && pp.visible
        property bool made: false
        onWantedChanged: if (wanted) made = true
        Component.onCompleted: if (wanted) made = true
        active: made
        visible: pp.raster
        asynchronous: true
        width: parent.width
        sourceComponent: Column {
            width: pp.width
            Repeater {    // InspectorRow by its file: it holds a fill field, which holds this picker (a type can't hold itself)
                model: pp.rows
                delegate: Loader {
                    required property var model
                    asynchronous: true
                    width: parent ? parent.width : 0
                    Component.onCompleted: if ((model.inside || "") === pp.rowsHost)      // the panel's other rows: nothing made
                        setSource(Qt.resolvedUrl("InspectorRow.qml"), { model: model, inside: pp.rowsHost, bridge: pp.rowsBridge, keyMarks: true })
                }
            }
        }
    }
    Item {        // Paint it: the brush on the painting, painting it in place on this layer (and every layer using it)
        objectName: "paintIt"
        visible: pp.raster && pp.type === "painted" && pp.paintIt !== ""
        width: parent.width; height: Theme.button + Theme.grid
        Button { id: paintItButton; anchors.bottom: parent.bottom; text: "Paint it"; hint: "B"; onClicked: pp.paintAsked() }
        Text { anchors { left: paintItButton.right; leftMargin: Theme.gap; right: parent.right; verticalCenter: paintItButton.verticalCenter }
               text: pp.paintItNote; elide: Text.ElideRight; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    }
    Text { visible: pp.shown === "none"; text: "No fill"; color: Theme.fg3; font.pixelSize: Theme.body; font.family: uiFont }
}
