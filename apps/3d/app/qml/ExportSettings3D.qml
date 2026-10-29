import QtQuick
import RostrumKit

// Rostrum3D's rows in the render sheet (AppShell.exportSettings; screen3d/export3d.py): Quality and Size are the shot's
// own render settings (a change is a shot edit, saved on the shot), Render only (a collection alone, once the scene has
// one), then what file it saves as and, for an EXR, its passes
// (an MP4 has neither: it is the video). First, while the shot's simulation is not up to date, the line saying the render
// computes it first; then, when a stopped render of exactly this left frames, "Continues from 130 finished frames".
Column {
    id: root
    readonly property var job: backend.exporter
    width: parent ? parent.width : 0
    spacing: Theme.grid

    // a row's name on the left, what it comes to on the right (one line: the sheet keeps its room for the rows)
    component Head: Item {
        property string name: ""
        property string note: ""
        width: parent.width; height: nameText.implicitHeight
        Text { id: nameText; text: parent.name; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        Text { anchors { left: nameText.right; leftMargin: Theme.gap; right: parent.right; verticalCenter: nameText.verticalCenter }
               text: parent.note; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    }
    component Gap: Item { width: 1; height: Theme.grid }

    // the shot's simulation isn't up to date: the render computes it first (sim_qt.py renderLine; never a stale one)
    Text { objectName: "sheetSimLine"; visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap
           text: backend.sim.renderLine; color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.body }
    Gap { visible: backend.sim.renderLine !== "" }
    Text { objectName: "sheetResumeLine"; visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap
           text: root.job.resumeLine; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
    Gap { visible: root.job.resumeLine !== "" }
    Head { objectName: "sheetQualityHead"; name: "Quality"; note: (root.job.quality === "custom" ? "Custom · " : "") + root.job.qualityText }
    Segmented { objectName: "sheetQuality"; width: parent.width; options: root.job.qualities; current: root.job.quality
                onPicked: (v) => root.job.setShot("renderQuality", v) }
    Gap { }
    Head { objectName: "sheetSizeHead"; name: "Size"; note: root.job.size !== "full" ? root.job.sizeText : "" }
    Segmented { objectName: "sheetSize"; width: parent.width; options: root.job.sizes; current: root.job.size
                onPicked: (v) => root.job.setShot("renderSize", v) }
    // Render only (PR1): one collection alone (absent until the scene has a collection)
    Gap { visible: root.job.alone.length > 0 }
    Head { visible: root.job.alone.length > 0; name: "Render only" }
    ChoiceField { objectName: "sheetRenderOnly"; visible: root.job.alone.length > 0; width: parent.width
                  options: root.job.alone; current: root.job.aloneOn; onPicked: (v) => root.job.setShot("renderOnly", v) }
    Gap { visible: root.job.choice !== "video" }
    Head { visible: root.job.choice !== "video"; name: "Save as" }
    ChoiceField { objectName: "sheetFormat"; visible: root.job.choice !== "video"; width: parent.width; options: root.job.formats; current: root.job.format; onPicked: (v) => root.job.setFormat(v) }
    // the EXR's layers: only while it saves an EXR (absent for a PNG); ticked ones are in the file, the beauty always is
    Gap { visible: root.job.passes.length > 0 }
    Head { visible: root.job.passes.length > 0; objectName: "sheetPassesHead"; name: "Passes"; note: "the picture always" }
    Flow {
        objectName: "sheetPasses"
        visible: root.job.passes.length > 0; width: parent.width; spacing: Theme.grid
        Repeater {
            model: root.job.passes
            Button { objectName: "pass_" + modelData.value; text: (modelData.on ? "✓ " : "+ ") + modelData.label
                     down: modelData.on; help: modelData.help; onClicked: root.job.setPass(modelData.value, !modelData.on) }
        }
    }
}
