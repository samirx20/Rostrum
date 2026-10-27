import QtQuick
import RostrumKit

// The render sheet's time (AppShell.exportSummary, just above Render; screen3d/estimate_sheet.py): a first guess at once
// ("About 40 s, a first guess · measuring…", its lines' places kept so Render below never moves), then
// "About 6 min" and under it "120 frames · 3 s a frame" (how it was measured: on hover), a note when another render was on the graphics card,
// and the test frame's picture (what is about to be rendered). Budget: click "Set a budget", type "10 min"; over it,
// the one-setting changes that fit, each a click.
Rectangle {
    id: box
    readonly property var est: backend.exporter.timeEstimate
    readonly property var job: backend.exporter
    width: parent ? parent.width : 0
    height: Math.max(col.implicitHeight, probe.height) + 2 * Theme.pad
    // "About 6 min · 120 frames · 3 s a frame": the time on its own line, the rest under it (it never breaks mid-figure)
    readonly property int cut: est.text.indexOf(" · ")
    readonly property string headline: cut < 0 ? est.text : est.text.substring(0, cut)
    readonly property string rest: cut < 0 ? "" : est.text.substring(cut + 3)
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

    HoverHandler { id: boxHover }
    HoverTip { text: box.est.how; hovered: boxHover.hovered && box.est.how !== "" }   // how it was measured: on hover, the box stays small
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
            Text { objectName: "estimateText"; width: col.width; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; text: box.headline
                   color: box.est.state === "failed" ? Theme.danger : Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   font.weight: box.est.state === "ready" ? Font.DemiBold : Font.Normal }
            Line { text: box.rest; color: Theme.fg2 }    // always in place, so the box keeps its height when the number lands
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
            Link { id: budgetLink; objectName: "estimateBudgetLink"; visible: !budgetField.visible
                   opacity: box.est.state === "ready" ? 1 : 0; enabled: box.est.state === "ready"   // its place kept while measuring
                   text: box.est.budget ? "Budget " + box.est.budget : "Set a budget"; onClicked: budgetField.visible = true }
            TextField {
                id: budgetField
                objectName: "estimateBudget"
                visible: false
                width: Math.min(col.width, 160)
                value: box.est.budget
                placeholder: "10 min"
                onEdited: (t) => { const why = box.est.setBudget(t); if (why === "") visible = false; else backend.say(why) }
            }
        }
    }
}
