import QtQuick
import RostrumKit

// Rostrum3D's rows in the render sheet (AppShell.exportSettings; screen3d/export3d.py): Quality and Size are the shot's
// own render settings (a change is a shot edit, saved on the shot), then what file it saves as.
Column {
    id: root
    readonly property var job: backend.exporter
    width: parent ? parent.width : 0
    spacing: Theme.grid

    component Label: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    component Note: Text { width: parent.width; elide: Text.ElideRight; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }

    Label { text: "Quality" }
    Segmented { width: parent.width; options: root.job.qualities; current: root.job.quality
                onPicked: (v) => root.job.setShot("renderQuality", v) }
    Note { text: (root.job.quality === "custom" ? "Custom · " : "") + root.job.qualityText }
    Item { width: 1; height: Theme.grid }
    Label { text: "Size" }
    Segmented { width: parent.width; options: root.job.sizes; current: root.job.size
                onPicked: (v) => root.job.setShot("renderSize", v) }
    Note { visible: root.job.size !== "full"; text: root.job.sizeText }
    Item { width: 1; height: Theme.grid }
    Label { text: "Save as" }
    ChoiceField { width: parent.width; options: root.job.formats; current: root.job.format; onPicked: (v) => root.job.setFormat(v) }
}
