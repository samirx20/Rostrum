import QtQuick
import "."
import "Files.js" as Files

// The paint picker's Painted part: the paintings there are, as tiles (the picture, its name under it), the one in use
// outlined, then "New painting". A tile click is `chosen(id)`, New is `added()`; the picker
// makes the change. The app hands the paintings in (PaintField options.sources).
//   sources: [{value: id, label: name, picture: path}]
Column {
    id: pp
    objectName: "paintedPaint"
    property var sources: []
    property string current: ""
    signal chosen(string id)
    signal added()
    spacing: Theme.grid
    readonly property int across: 3
    readonly property real tile: Math.floor((width - (across - 1) * Theme.gap) / across)
    // The tiles change in place (a painting's new picture, a new name): a tile is never made again under the pointer,
    // so a click that lands while the app reads its rows again still counts.
    ListModel { id: tiles }
    onSourcesChanged: sync()
    Component.onCompleted: sync()
    function sync() {
        const ids = pp.sources.map(t => t.value)
        let same = ids.length === tiles.count
        for (let i = 0; same && i < ids.length; i++) same = tiles.get(i).value === ids[i]
        if (!same) tiles.clear()
        pp.sources.forEach((t, i) => {
            const row = { value: t.value, label: t.label || "", picture: t.picture || "" }
            if (same) tiles.set(i, row); else tiles.append(row)
        })
    }

    Text { text: "Paintings in this scene"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    Flow {
        width: parent.width; spacing: Theme.gap
        Repeater {
            model: tiles
            delegate: Column {
                id: one
                required property string value
                required property string label
                required property string picture
                readonly property bool on: value === pp.current
                objectName: "painting:" + value          // scripted clicks find it (2D click_steps.py)
                width: pp.tile; spacing: 2
                Item {
                    width: pp.tile; height: pp.tile
                    Checker { anchors.fill: parent; anchors.margins: 1; radius: Theme.radiusCtl; cell: 5 }
                    Image {
                        anchors.fill: parent; anchors.margins: 1
                        source: Files.url(one.picture)
                        sourceSize: Qt.size(2 * pp.tile, 2 * pp.tile); fillMode: Image.PreserveAspectCrop
                        asynchronous: true; cache: true; smooth: true      // content-named files: a change is a new name
                    }
                    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: "transparent"
                                border.width: one.on ? 2 : 1
                                border.color: one.on ? Theme.accent : tileHover.containsMouse ? Qt.rgba(1, 1, 1, 0.4) : Qt.rgba(1, 1, 1, 0.14) }
                    MouseArea { id: tileHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: pp.chosen(one.value) }     // a MouseArea: a TapHandler in the picker missed real clicks
                }
                Text { width: parent.width; text: one.label; elide: Text.ElideRight
                       color: one.on ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
            }
        }
        Column {      // + New painting: a new painting the size of the layer, laid on it (one change)
            objectName: "painting:new"
            width: pp.tile; spacing: 2
            Item {
                width: pp.tile; height: pp.tile
                Canvas {
                    anchors.fill: parent
                    property bool hot: newHover.containsMouse
                    onHotChanged: requestPaint()
                    onPaint: {
                        const g = getContext("2d"), w = width, h = height
                        g.reset(); g.setLineDash([3, 3]); g.lineWidth = 1
                        g.strokeStyle = hot ? Theme.fg2 : Theme.fg4
                        g.beginPath(); g.roundedRect(0.5, 0.5, w - 1, h - 1, Theme.radiusCtl, Theme.radiusCtl); g.stroke()
                    }
                }
                Text { anchors.centerIn: parent; text: "+"; color: newHover.containsMouse ? Theme.fg : Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.heading }
                MouseArea { id: newHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: pp.added() }
            }
            Text { width: parent.width; text: "New painting"; elide: Text.ElideRight
                   color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
}
