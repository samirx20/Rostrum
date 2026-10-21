import QtQuick
import RostrumKit

// The piano roll's header button that opens and closes the picture in the corner.
Button {
    text: "Picture"; kind: "ghost"; down: backend.pictureOpen; height: Theme.field
    onClicked: backend.setPictureOpen(!backend.pictureOpen)
}
