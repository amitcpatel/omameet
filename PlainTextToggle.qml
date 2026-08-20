import QtQuick
import qs.Commons
import qs.Ui

// Toggle variant for labels that originate outside the plugin. Qt's default
// AutoText mode interprets HTML-looking strings; calendars are untrusted input.
BorderSurface {
  id: root
  property string label: ""
  property string description: ""
  property bool checked: false
  property color foreground: Color.foreground
  property color accent: Color.accent
  signal clicked()

  implicitHeight: Math.max(54, content.implicitHeight + Style.spacing.huge)
  radius: Style.cornerRadius
  color: Style.controlFill(activeFocus, mouse.containsMouse, foreground, accent)
  borderSpec: Border.controlSpec(activeFocus ? "focus" : (mouse.containsMouse ? "hover-cursor" : "normal"), foreground, accent)
  activeFocusOnTab: true
  Keys.onReturnPressed: root.clicked()
  Keys.onEnterPressed: root.clicked()
  Keys.onSpacePressed: root.clicked()

  Row {
    id: content
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: root.borderLeft + Style.spacing.rowPaddingX
    anchors.rightMargin: root.borderRight + Style.spacing.rowPaddingX
    spacing: Style.spacing.rowPaddingX
    Column {
      width: parent.width - track.width - parent.spacing
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.spacing.xs
      Text {
        width: parent.width
        text: root.label
        textFormat: Text.PlainText
        color: root.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.subtitle
        font.bold: true
        elide: Text.ElideRight
      }
      Text {
        width: parent.width
        visible: root.description !== ""
        text: root.description
        textFormat: Text.PlainText
        color: Qt.darker(root.foreground, 1.5)
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }
    ToggleSwitch {
      id: track
      checked: root.checked
      foreground: root.foreground
      accent: root.accent
      interactive: false
      anchors.verticalCenter: parent.verticalCenter
    }
  }
  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.clicked()
  }
}
