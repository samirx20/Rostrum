import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The listen pictures of the last render: the loudness curve and the spectrum, drawn off the GUI thread.
// Opens itself when pictures arrive. A failure is written here, in words. Click a picture to see it large.
Rectangle {
    id: l
    readonly property var pics: mixer.listen
    property bool open: false
    property real room: 1000          // the most it may take: what the master card leaves (MixPage); it never covers it
    // Open, at most a quarter of the page: the strips' faders keep their travel (buses and sends made them taller).
    readonly property real openHeight: Math.min(room, Math.max(150, Math.min(292, (parent ? parent.height : 1000) * 0.25)))
    readonly property bool fits: room >= 150     // too little room to open in place: the pictures open large instead
    implicitHeight: open && fits ? openHeight : 36
    color: Theme.app; radius: Theme.radiusPanel
    clip: true
    Behavior on implicitHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
    Connections { target: l.pics; function onChanged() { if (l.pics.loudness !== "" || l.pics.status !== "") l.open = true } }

    Item {
        id: bar
        width: parent.width; height: 36
        Chevron { id: chev; x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; rotation: l.open ? 0 : -90
                  color: tap.containsMouse ? Theme.fg : Theme.fg3 }
        Text { x: chev.x + 22; anchors.verticalCenter: parent.verticalCenter; text: "Listen"; color: Theme.fg2
               font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
            text: l.pics.status !== "" ? l.pics.status : l.pics.loudness === "" ? "Render to see the loudness and the spectrum" : ""
            color: l.pics.status.indexOf("Could not") === 0 ? Theme.danger : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.body
        }
        MouseArea { id: tap; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: l.fits ? l.open = !l.open : l.showLarge() }
    }
    Row {
        x: Theme.pad; y: bar.height; width: parent.width - 2 * Theme.pad; height: l.openHeight - bar.height - Theme.pad
        spacing: Theme.gap
        Repeater {
            model: [{ src: l.pics.loudness, what: "Loudness" }, { src: l.pics.spectrum, what: "Spectrum" }]
            delegate: Rectangle {
                required property var modelData
                width: (parent.width - Theme.gap) / 2; height: parent.height
                color: Theme.sunken; radius: Theme.radiusCtl
                Image { anchors.fill: parent; anchors.margins: 2; fillMode: Image.PreserveAspectFit; asynchronous: true; mipmap: true
                        source: modelData.src ? "file:///" + modelData.src : "" }
                MouseArea { anchors.fill: parent; enabled: modelData.src !== ""; cursorShape: Qt.PointingHandCursor
                            onClicked: { pic.source = "file:///" + modelData.src; big.open() } }
            }
        }
    }
    function showLarge() {           // a small window: both pictures in the large view
        if (pics.loudness === "") return
        pic.source = "file:///" + pics.loudness; big.open()
    }
    QQC.Popup {
        id: big
        parent: QQC.Overlay.overlay
        anchors.centerIn: parent
        width: parent.width * 0.8; height: parent.height * 0.8
        padding: Theme.gap; modal: true; closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
        background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
        contentItem: Image { id: pic; fillMode: Image.PreserveAspectFit; mipmap: true }
    }
}
