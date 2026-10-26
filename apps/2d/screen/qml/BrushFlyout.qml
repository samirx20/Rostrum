import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The Brush group's flyout = the brush panel (painting design §2.1, mockup paint-04): beside the rail at the Brush
// icon. The top row: the five paint tools (backend.paintTool; each one's key in its hover tip). Below: the brushes as real strokes painted by the kit's
// engine (image://brushes/<id>, screen2d/brush_presets.py), three across, by group. A click on a brush makes it the
// brush (the Brush tool goes on) and closes the panel; a click anywhere else closes it without changing
// anything, and Esc leaves the Brush (the panel goes with it). Too tall for the window: the brushes scroll, the tools stay. Last, My brushes (saved brushes, from the
// project and the person's own library, each once; a small "project" / "library" on the stroke's corner of one kept in just one
// place; "+ Save this brush" is the last tile; right-click one: Rename, Duplicate, Also keep in / Remove from a place, Delete — the
// entries that apply, from painter.myBrushes). Hovering a brush shows its stroke larger, at the tile.
SmallPopup {
    id: fly
    objectName: "brushFlyout"
    parent: QQC.Overlay.overlay
    padding: 8
    escCloses: false                               // not on Esc: Esc is Main.qml's, one step back from the Brush to Select, closing the panel with it
    focus: true
    background: MenuBackground { radius: Theme.radiusPanel }
    readonly property int tileW: 112
    readonly property int tileH: 27
    readonly property var tools: [
        { id: "brush", name: "Brush", key: "B" }, { id: "eraser", name: "Eraser", key: "E" }, { id: "fill", name: "Fill", key: "G" },
        { id: "pick", name: "Pick", key: "I" }, { id: "select", name: "Select", key: "S" }]
    property real room: 10000          // the brushes' most height: the window's, less the tools row
    property real at: 8                // the Brush icon's top: the panel starts there, moved up as far as it must fit
    // a binding, not set once in show(): the list's height settles only after the positioners lay it out
    property real floor: 10000         // the lowest it may reach (above the timeline's names column)
    MenuSpot { id: spot }
    y: Math.max(8, Math.min(at, Math.min(floor, parent ? parent.height : 0) - implicitHeight))
    // The panel opens beside the rail, over the left of the picture, so the settings panel (the Brush row, Size, Colour) stays in
    // view while a brush is chosen; a press anywhere outside it closes it and starts the stroke in that same press
    // (a click outside = CloseOnPressOutside, and the press goes on to the canvas).
    function settingsZone(item) {     // the visible settings panel's rectangle in the window, or null
        if (!item || !item.visible) return null
        if (item.popupsBeside === true && item.width > 0) { const q = item.mapToItem(parent, 0, 0); return { x: q.x, y: q.y, w: item.width, h: item.height } }
        for (const c of item.children) { const z = settingsZone(c); if (z) return z }
        return null
    }
    function show(button) {
        const p = button.mapToItem(parent, button.width, 0)
        const w = 3 * tileW + 2 * 8 + 2 * padding
        const z = settingsZone(button.Window.window.contentItem)
        spot.anchor = button
        x = p.x + 8                                              // beside the rail: the settings panel stays in view (brush, size, colour)
        const top = z ? z.y : p.y - padding
        floor = spot.floorBelow(x, w, top)     // above the timeline's names, not over them
        if (z) floor = Math.min(floor, z.y + z.h)     // and within the settings panel: the brushes scroll for the rest
        room = floor - Math.max(8, top) - 2 * padding - 48 - 1 - 2 * 6
        at = top
        open()
    }
    property var hoverTile: null       // the brush the pointer rests on: its stroke shows larger (bigPreview)
    onAboutToShow: painter.refreshBrushes()    // an agent may have saved one meanwhile
    function pickBrush(id) { painter.setPreset(id); backend.paintTool.use("brush"); close() }

    component BrushTile: Rectangle {
        id: tile
        required property var modelData
        required property int index
        property bool mine: false                     // a saved brush: right-click shows its menu
        property bool renaming: false
        readonly property bool on: painter.brushNow.preset === modelData.id
        readonly property bool hovered: tileTap.containsMouse
        objectName: mine ? "mybrush_" + index : "brush_" + modelData.id     // My brushes by place: their ids are content
        width: fly.tileW; height: fly.tileH + 22; radius: Theme.radiusCtl
        color: tileTap.pressed ? Theme.active : hovered ? Theme.hover : "transparent"
        border.color: tile.on ? Theme.accent : "transparent"
        onHoveredChanged: fly.hoverTile = hovered ? tile : (fly.hoverTile === tile ? null : fly.hoverTile)
        Image {
            x: 3; y: 3; width: parent.width - 6; height: fly.tileH
            source: "image://brushes/" + tile.modelData.id
            asynchronous: false; fillMode: Image.PreserveAspectCrop; smooth: true; mipmap: true   // painted ahead: a lookup (screen_images.py)
        }
        Text {
            id: tileName
            visible: !tile.renaming
            x: 5; anchors { bottom: parent.bottom; bottomMargin: 4 }
            width: parent.width - 10; elide: Text.ElideRight
            text: tile.modelData.name; color: tile.on || tile.hovered ? Theme.fg : Theme.fg2
            font.family: uiFont; font.pixelSize: Theme.body
        }
        Rectangle { // where a saved brush is kept, only when it is in just one of the two places: on the stroke's corner
            id: markText
            visible: tile.mine && !!tile.modelData.mark
            anchors { right: parent.right; top: parent.top; margins: 3 }
            width: markLabel.implicitWidth + 8; height: markLabel.implicitHeight + 2; radius: 3; color: Theme.raised
            Text { id: markLabel; anchors.centerIn: parent; text: tile.mine ? tile.modelData.mark : ""; color: Theme.fg2
                   font.family: uiFont; font.pixelSize: Theme.label - 2 }
        }
        HoverTip { hovered: tile.hovered && !tile.renaming && (tileName.truncated || markText.visible)
                   text: markText.visible ? tile.modelData.name + " · " + tile.modelData.markTip : tile.modelData.name }
        NameBox {     // rename in place (the kit's box): Enter keeps it, Esc or a click elsewhere leaves the name as it was
            id: nameEdit
            objectName: "brushName_" + tile.index
            visible: tile.renaming
            current: tile.modelData.name
            anchors { left: tileName.left; right: tileName.right; verticalCenter: tileName.verticalCenter }
            font.pixelSize: Theme.label
            onDone: (t) => { tile.renaming = false; if (t.trim() && t !== tile.modelData.name) painter.renameBrush(tile.modelData.id, t.trim()) }
            onCancelled: tile.renaming = false
        }
        MouseArea {
            id: tileTap; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            enabled: !tile.renaming
            acceptedButtons: tile.mine ? Qt.LeftButton | Qt.RightButton : Qt.LeftButton
            onClicked: (ev) => ev.button === Qt.RightButton ? tileMenu.open() : fly.pickBrush(tile.modelData.id)
        }
        Menu { id: tileMenu; y: tile.height; width: 208     // "Also keep in this project" in full
               property bool rename: false     // Rename starts once the menu has closed (it hands focus back as it goes)
               entries: tile.mine ? tile.modelData.menu : []
               onPicked: (v) => v === "rename" ? (rename = true) : painter.brushAction(tile.modelData.id, v)
               onClosed: if (rename) { rename = false; tile.renaming = true } }
    }
    function pickTool(id) { backend.paintTool.use(id); close() }

    contentItem: Item {
      implicitWidth: content.implicitWidth; implicitHeight: content.implicitHeight
      Column {
        id: content
        spacing: 6
        Row {       // the five paint tools, icon over name; the key in the hover tip
            spacing: 2
            Repeater {
                model: fly.tools
                delegate: Rectangle {
                    id: tool
                    required property var modelData
                    readonly property bool on: backend.tool === "draw" && backend.paintTool.now === modelData.id
                    objectName: "paint_" + modelData.id
                    width: (3 * fly.tileW + 2 * 8 - 4 * 2) / 5; height: 48; radius: Theme.radiusCtl
                    color: toolTap.pressed || tool.on ? Theme.active : toolHover.hovered ? Theme.hover : "transparent"
                    border.color: tool.on ? Theme.accent : "transparent"
                    PaintToolIcon { anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 7 }
                                    name: tool.modelData.id; ink: tool.on || toolHover.hovered ? Theme.fg : Theme.fg2 }
                    Text { anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 5 }
                           text: tool.modelData.name; color: tool.on || toolHover.hovered ? Theme.fg : Theme.fg2
                           font.family: uiFont; font.pixelSize: Theme.body }
                    HoverHandler { id: toolHover; cursorShape: Qt.PointingHandCursor }
                    HoverTip { hovered: toolHover.hovered; pressed: toolTap.pressed; text: tool.modelData.name; key: tool.modelData.key }
                    MouseArea { id: toolTap; anchors.fill: parent; onClicked: fly.pickTool(tool.modelData.id) }
                }
            }
        }
        Rectangle { width: parent.width; height: 1; color: Theme.popupEdge }
        Flickable {
            id: list
            width: 3 * fly.tileW + 2 * 8
            height: Math.min(groups.height, fly.room)
            contentHeight: groups.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: groups
                width: parent.width
                Repeater {
                    model: painter.presets
                    delegate: Column {
                        id: grp
                        required property var modelData
                        width: groups.width
                        Text { text: grp.modelData.group; height: 22; verticalAlignment: Text.AlignVCenter
                               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                        Grid {
                            columns: 3; columnSpacing: 8; rowSpacing: 4
                            Repeater {
                                model: grp.modelData.presets
                                delegate: BrushTile { }
                            }
                        }
                        Item { width: 1; height: 4 }
                    }
                }
                Text { text: "My brushes"; height: 22; verticalAlignment: Text.AlignVCenter     // as the groups' headings
                       color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                Grid {
                    columns: 3; columnSpacing: 8; rowSpacing: 4
                    Repeater { model: painter.myBrushes; delegate: BrushTile { mine: true } }
                    Rectangle {     // + Save this brush: the last tile, its name field in place
                        width: saveTile.naming ? 2 * fly.tileW + 8 : fly.tileW; height: fly.tileH + 22; radius: Theme.radiusCtl
                        color: "transparent"; border.color: saveTile.naming ? "transparent" : Theme.popupEdge
                        SaveBrush { id: saveTile; align: Text.AlignHCenter
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 1 } }
                    }
                }
                Item { width: 1; height: 4 }
            }
        }
      }
      Rectangle {     // the brush the pointer rests on, its stroke larger (no text), centred on the tile
          id: bigPreview
          objectName: "brushBigPreview"
          readonly property var t: fly.hoverTile
          visible: t !== null && !t.renaming && showDelay.done
          width: 232 + 8; height: 56 + 8; radius: Theme.radiusCtl; z: 10
          color: Theme.raised; border.color: Theme.popupEdge
          x: t ? Math.max(0, Math.min(parent.width - width, t.mapToItem(parent, t.width / 2, 0).x - width / 2)) : 0
          readonly property real ty: t ? t.mapToItem(parent, 0, 0).y : 0
          y: ty - height - 2 >= 0 ? ty - height - 2 : ty + (t ? t.height : 0) + 2     // above the tile, else below
          Image { x: 4; y: 4; width: 232; height: 56; asynchronous: false; smooth: true
                  source: bigPreview.t ? "image://brushes/" + bigPreview.t.modelData.id : "" }
          Timer { id: showDelay; property bool done: false; interval: 350
                  onTriggered: done = true }
          onTChanged: { showDelay.done = false; if (t) showDelay.restart() }
      }
    }
}
