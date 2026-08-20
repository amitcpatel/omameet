import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "acp.omascribe"

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool recording: panelLoader.item ? panelLoader.item.recording === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  function open() { if (panelLoader.item) panelLoader.item.open() }
  function openSettings() { if (panelLoader.item) panelLoader.item.openSettings() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: root.injectPanel()
  }
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // Nerd Font calendar-check. Keep this escaped: raw private-use glyphs can
    // be stripped in transit and leave a silently invisible bar widget.
    text: root.recording ? "\uf111" : "\uf274"
    active: root.recording
    slotSize: Style.bar.statusSlot
    tooltipText: panelLoader.item ? panelLoader.item.tooltip : "OmaScribe"
    onPressed: function(b) {
      if (!root.bar || !panelLoader.item) return
      if (b === Qt.RightButton) root.openSettings()
      else if (b === Qt.MiddleButton) panelLoader.item.refresh()
      else panelLoader.item.toggle()
    }
  }
}
