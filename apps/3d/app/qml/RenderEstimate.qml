import QtQuick
import RostrumKit

// The render sheet's time (AppShell.exportSummary, just above Render; screen3d/estimate_sheet.py): "Measuring…", then
// "About 6 min · 120 frames · 3 s a frame", how it was measured, a note when another render was on the graphics card,
// and the test frame's picture (what is about to be rendered). Budget: click "Set a budget", type "10 min"; over it,
// the one-setting changes that fit, each a click.
Rectangle {
    id: box
    readonly property var est: backend.exporter.timeEstimate
    readonly property var job: backend.exporter
    width: parent ? parent.width : 0
    height: col.implicitHeight + 2 * Theme.pad
    visible: est.state !== ""
    radius: Theme.radiusCtl; color: "transparent"; border.color: est.over ? Theme.danger : Theme.popupEdge

    component Line: Text { width: col.width; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.family: uiFont; font.pixelSize: Theme.label; color: Theme.fg3 }
    component Link: Text {
        signal clicked()
        color: hov.hovered ? Theme.fg : Theme.accent; font.family: uiFont; font.pixelSize: Theme.label
        height: Math.max(implicitHeight, 16); verticalAlignment: Text.AlignVCenter
        HoverHandler { id: hov; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: parent.clicked() }
    }

    Row {
        x: Theme.pad; y: Theme.pad
        spacing: Theme.gap
        Image {     // the test frame: what is about to be rendered
            id: probe
            visible: box.est.picture !== ""
            source: box.est.picture
            width: 64; height: visible ? Math.round(64 * Math.max(1, sourceSize.height) / Math.max(1, sourceSize.width)) : 0
            fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false
        }
        Column {
            id: col
            width: box.width - 2 * Theme.pad - (probe.visible ? probe.width + Theme.gap : 0)
            spacing: 2
            Text { width: col.width; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; text: box.est.text
                   color: box.est.state === "failed" ? Theme.danger : Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   font.weight: box.est.state === "ready" ? Font.DemiBold : Font.Normal }
            Line { visible: text !== ""; text: box.est.how }
            Line { visible: text !== ""; text: box.est.card; color: Theme.warn }
            Line { visible: box.est.over; text: "Over the " + box.est.budget + " budget. Fits:" + (box.est.fits.length ? "" : " nothing by one setting; shorten the frames on the shot")
                   color: Theme.danger }
            Flow {
                visible: box.est.over && box.est.fits.length > 0
                width: col.width; spacing: Theme.gap
                Repeater {
                    model: box.est.over ? box.est.fits : []
                    delegate: Link { required property var modelData; text: modelData.text
                                     onClicked: box.job.setShot(modelData.field, modelData.value) }
                }
            }
            Item { width: 1; height: 2 }
            Link { id: budgetLink; visible: box.est.state === "ready" && !budgetField.visible
                   text: box.est.budget ? "Budget " + box.est.budget : "Set a budget"; onClicked: budgetField.visible = true }
            TextField {
                id: budgetField
                visible: false
                width: Math.min(col.width, 160)
                value: box.est.budget
                placeholder: "10 min"
                onEdited: (t) => { const why = box.est.setBudget(t); if (why === "") visible = false; else backend.say(why) }
            }
        }
    }
}
