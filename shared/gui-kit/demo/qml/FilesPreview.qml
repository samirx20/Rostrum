import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for S36's files pieces; see files_preview.py. Nothing here is an app.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    property string open: ""
    property string appName: "Rostrum2D"
    onOpenChanged: Qt.callLater(show)
    function show() {
        if (open === "view") control.openMenu()
        else if (open === "marker") ruler.openMarkerMenu(null, ruler.markers[0], ruler.xOfSec(2.0) + 20, 90)
        else if (open === "menu") menuButton.openMenu()
    }
    Rectangle {     // the main view, with the view control at its bottom right
        id: stage
        x: Theme.gap; y: 120; width: parent.width - 2 * Theme.gap; height: parent.height - 120 - Theme.gap
        radius: Theme.radiusPanel; color: Theme.panel
        Rectangle { anchors.centerIn: parent; width: 480; height: 270; color: Theme.sunken }
        // (ViewControl is not in qmldir until the lead adds it: loaded by its file here)
        Loader { id: control; source: Qt.resolvedUrl("../../qml/RostrumKit/ViewControl.qml")
                 anchors { right: parent.right; bottom: parent.bottom; margins: Theme.gap }
                 onLoaded: item.view = view
                 function openMenu() { item.openMenu() } }
    }
    FilesMenu { id: menuButton; x: Theme.gap; y: Theme.gap }
    Ruler {
        id: ruler
        x: 80; y: 40; width: parent.width - 2 * 80; height: implicitHeight
        duration: 20; value: 7.25
        markers: markerRows; editMarkers: true; canShare: true; markerSource: markerWatch
        onScrubbed: (t) => value = t
    }
    StartScreen { anchors.fill: parent; z: 100 }
}
