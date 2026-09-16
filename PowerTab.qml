import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: root

  property var d: ({})
  property color foreground
  property color dim
  property color urgent
  property color accentColor: Color.accent
  property string fontFamily
  signal commandRequested(var args)

  readonly property var power: d && d.power ? d.power : ({})
  readonly property var custom: power.custom || ({})
  readonly property var limits: power.limits || ({})
  readonly property var gpu: d && d.gpu ? d.gpu : ({})
  readonly property bool gpuLimitKnown: gpu.power_cap_w !== undefined && gpu.power_cap_w !== null

  function watts(value) {
    return Math.round(value) + " W"
  }

  width: parent ? parent.width : implicitWidth
  spacing: Style.space(10)

  Text {
    textFormat: Text.PlainText
    text: "Legion Power Mode"
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    font.bold: true
  }

  Text {
    textFormat: Text.PlainText
    width: parent.width
    text: {
      var bits = ["Same thermal mode as Fn+Q. Quiet, Balanced, and Performance stay synced with the Omarchy battery profile."]
      if (power.ppd_label)
        bits.push("Battery panel: " + power.ppd_label + ".")
      if (power.ppd_in_sync === false)
        bits.push("Power-profiles-daemon is out of sync — Legion mode is still applied in firmware.")
      return bits.join(" ")
    }
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.Wrap
  }

  Repeater {
    model: power.available_modes || []
    delegate: OptionCard {
      required property var modelData
      width: parent.width
      foreground: root.foreground
      dim: root.dim
      accentColor: root.accentColor
      fontFamily: root.fontFamily
      title: modelData.label
      description: modelData.blocked_on_battery
        ? modelData.desc + " Requires AC power."
        : modelData.desc
      selected: modelData.selected === true
      enabled: !modelData.blocked_on_battery
      actionTip: modelData.blocked_on_battery
        ? "Plug in AC power"
        : (modelData.selected ? "Active" : "Apply " + modelData.label)
      onActivated: root.commandRequested(["--set-power", modelData.profile])
    }
  }

  Column {
    visible: !!power.current_label
    width: parent.width
    spacing: Style.space(10)

    Text {
      textFormat: Text.PlainText
      text: "Limits in effect"
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: true
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: {
        var bits = []
        if (power.is_custom)
          bits.push("These are the limits Custom mode applies.")
        else
          bits.push("The firmware sets the CPU's limits for " + (power.current_label || "this profile")
            + " without reporting them to Linux. Switch to Custom to set and see them.")
        if (!root.gpuLimitKnown)
          bits.push("The GPU's limit appears while the NVIDIA GPU is active.")
        return bits.join(" ")
      }
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.Wrap
    }

    GridLayout {
      columns: 2
      width: parent.width
      columnSpacing: Style.space(8)
      rowSpacing: Style.space(8)

      Repeater {
        model: {
          var items = []
          if (root.gpuLimitKnown) {
            var bits = []
            if (gpu.power_draw_w !== undefined && gpu.power_draw_w !== null)
              bits.push("drawing " + root.watts(gpu.power_draw_w))
            if (gpu.power_limit_default_w !== undefined && gpu.power_limit_default_w !== null)
              bits.push("default " + root.watts(gpu.power_limit_default_w))
            if (gpu.power_limit_max_w !== undefined && gpu.power_limit_max_w !== null)
              bits.push("max " + root.watts(gpu.power_limit_max_w))
            items.push({ label: "GPU power limit", value: root.watts(gpu.power_cap_w), subtitle: bits.join(" · ") })
          }
          var cpu = limits.items || []
          for (var i = 0; i < cpu.length; i++)
            items.push({ label: cpu[i].label, value: cpu[i].value + " " + cpu[i].unit, subtitle: "" })
          return items
        }
        delegate: StatusCard {
          required property var modelData
          Layout.fillWidth: true
          Layout.fillHeight: true
          foreground: root.foreground
          dim: root.dim
          accentColor: root.accentColor
          fontFamily: root.fontFamily
          label: modelData.label
          value: modelData.value
          subtitle: modelData.subtitle
        }
      }
    }
  }

  Column {
    visible: !!(custom && custom.available)
    width: parent.width
    spacing: Style.space(10)

    Text {
      textFormat: Text.PlainText
      text: "Custom TDP"
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: true
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: power.is_custom
        ? "Firmware power limits for Custom mode. These apply immediately."
        : "Switch to Custom mode to edit PL1 and PL2 limits."
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.Wrap
    }

    PptLimitCard {
      visible: !!(custom && custom.pl1)
      width: parent.width
      limit: custom.pl1 || ({})
      enabled: power.is_custom === true && power.ac_connected !== false
      foreground: root.foreground
      dim: root.dim
      accentColor: root.accentColor
      fontFamily: root.fontFamily
      onPicked: function(watts) {
        if (custom.pl1 && custom.pl1.id)
          root.commandRequested(["--set-ppt", String(custom.pl1.id), String(watts)])
      }
    }

    PptLimitCard {
      visible: !!(custom && custom.pl2)
      width: parent.width
      limit: custom.pl2 || ({})
      enabled: power.is_custom === true && power.ac_connected !== false
      foreground: root.foreground
      dim: root.dim
      accentColor: root.accentColor
      fontFamily: root.fontFamily
      onPicked: function(watts) {
        if (custom.pl2 && custom.pl2.id)
          root.commandRequested(["--set-ppt", String(custom.pl2.id), String(watts)])
      }
    }
  }

  component PptLimitCard: BorderSurface {
    id: ppt
    property var limit: ({})
    property bool enabled: true
    property color foreground
    property color dim
    property color accentColor
    property string fontFamily
    signal picked(int watts)

    implicitHeight: pptCol.implicitHeight + Style.space(16)
    color: Style.hoverFillFor(foreground, foreground)
    borderSpec: Border.controlSpec("normal", dim, accentColor)
    radius: Style.cornerRadius
    opacity: enabled ? 1 : 0.55

    Column {
      id: pptCol
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: Style.space(8)
      spacing: Style.space(6)

      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: ppt.limit && ppt.limit.label ? ppt.limit.label : ""
        color: ppt.foreground
        font.family: ppt.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
        wrapMode: Text.Wrap
        elide: Text.ElideRight
        maximumLineCount: 2
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: (ppt.limit && ppt.limit.current !== undefined ? ppt.limit.current : "--")
          + " W  ·  "
          + (ppt.limit && ppt.limit.min !== undefined ? ppt.limit.min : "--")
          + "–"
          + (ppt.limit && ppt.limit.max !== undefined ? ppt.limit.max : "--")
          + " W"
        color: ppt.dim
        font.family: ppt.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
        maximumLineCount: 1
      }

      Row {
        spacing: Style.space(6)

        PptChip {
          label: "Min"
          watts: ppt.limit && ppt.limit.min !== undefined ? ppt.limit.min : -1
          enabled: ppt.enabled
          foreground: ppt.foreground
          dim: ppt.dim
          accentColor: ppt.accentColor
          fontFamily: ppt.fontFamily
          onClicked: if (watts >= 0) ppt.picked(watts)
        }
        PptChip {
          label: "Stock"
          watts: ppt.limit && ppt.limit.default_watts !== undefined ? ppt.limit.default_watts : -1
          enabled: ppt.enabled
          foreground: ppt.foreground
          dim: ppt.dim
          accentColor: ppt.accentColor
          fontFamily: ppt.fontFamily
          onClicked: if (watts >= 0) ppt.picked(watts)
        }
        PptChip {
          label: "Max"
          watts: ppt.limit && ppt.limit.max !== undefined ? ppt.limit.max : -1
          enabled: ppt.enabled
          foreground: ppt.foreground
          dim: ppt.dim
          accentColor: ppt.accentColor
          fontFamily: ppt.fontFamily
          onClicked: if (watts >= 0) ppt.picked(watts)
        }
      }
    }
  }

  component PptChip: BorderSurface {
    id: chip
    property string label: ""
    property int watts: -1
    property bool enabled: true
    property color foreground
    property color dim
    property color accentColor
    property string fontFamily
    signal clicked

    implicitWidth: chipText.implicitWidth + Style.space(14)
    implicitHeight: chipText.implicitHeight + Style.space(8)
    radius: Style.cornerRadius
    color: "transparent"
    borderSpec: Border.controlSpec("normal", dim, accentColor)
    opacity: enabled ? 1 : 0.55

    Text {
      id: chipText
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: chip.label
      color: chip.foreground
      font.family: chip.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
    }

    MouseArea {
      anchors.fill: parent
      enabled: chip.enabled
      cursorShape: Qt.PointingHandCursor
      onClicked: chip.clicked()
    }
  }
}
