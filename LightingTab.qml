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
  property var run

  readonly property var lighting: d && d.lighting ? d.lighting : ({})
  readonly property var modelInfo: lighting.model || ({})
  readonly property var hw: lighting.hardware || ({})
  readonly property string keyboardKind: modelInfo.keyboard || "none"
  readonly property bool isPerKey: keyboardKind === "perkey"
  readonly property bool isFourZone: keyboardKind === "4zone"
  readonly property bool isWhite: keyboardKind === "white"
  readonly property bool hasColor: isPerKey || isFourZone

  property string pendingColor: lighting.color || "#ffffff"
  onLightingChanged: pendingColor = lighting.color || "#ffffff"

  width: parent ? parent.width : implicitWidth
  spacing: Style.space(10)

  // --- Model ---------------------------------------------------------
  Text {
    textFormat: Text.PlainText
    text: "Keyboard Model"
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    font.bold: true
  }

  Text {
    textFormat: Text.PlainText
    width: parent.width
    text: {
      var bits = ["Detected: " + (modelInfo.label || "Unknown") + " (" + (modelInfo.source || "unknown") + ")."]
      bits.push("Lighting: " + root.keyboardKind + (modelInfo.logo ? ", logo" : "") + (modelInfo.io_port ? ", IO-port bar (not yet controllable)" : "") + ".")
      return bits.join(" ")
    }
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.Wrap
  }

  Dropdown {
    width: Math.min(parent.width, Style.space(280))
    label: "Model override"
    value: modelInfo.override || "auto"
    options: lighting.known_models || ["auto"]
    foreground: root.foreground
    accent: root.accentColor
    onChanged: function(value) { root.run(["--set-model-override", value]) }
  }

  BorderSurface {
    visible: hw.available !== true
    width: parent.width
    implicitHeight: noHwText.implicitHeight + Style.space(16)
    color: Style.hoverFillFor(root.foreground, root.foreground)
    borderSpec: Border.controlSpec("normal", root.dim, root.accentColor)
    radius: Style.cornerRadius

    Text {
      id: noHwText
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: Style.space(8)
      text: root.keyboardKind === "none"
        ? "No lighting hardware detected for this model. If your Legion has RGB, try a model override above."
        : "Lighting hardware expected but not found — check that the udev permissions below are installed."
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.Wrap
    }
  }

  PanelSeparator { width: parent.width; visible: hw.available === true }

  // --- Power + brightness ---------------------------------------------
  ToggleRow {
    visible: hw.available === true
    width: parent.width
    title: "Keyboard lighting"
    description: "Turn the keyboard/perimeter lighting on or off."
    checked: lighting.on !== false
    foreground: root.foreground
    dim: root.dim
    accentColor: root.accentColor
    fontFamily: root.fontFamily
    onToggled: root.run(["--set-lighting-power", lighting.on ? "0" : "1"])
  }

  Column {
    visible: hw.available === true
    width: parent.width
    spacing: Style.space(4)

    Text {
      textFormat: Text.PlainText
      text: "Brightness · " + (lighting.brightness !== undefined ? lighting.brightness : "--")
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }

    PanelSlider {
      width: parent.width
      minimum: 0
      maximum: root.isFourZone ? 50 : (root.isWhite ? (root.d && root.d.input && root.d.input.backlight_max || 2) : 9)
      integer: true
      value: lighting.brightness || 0
      fillColor: root.accentColor
      knobColor: root.foreground
      onReleased: function(value) { root.run(["--set-lighting-brightness", String(Math.round(value))]) }
    }
  }

  // --- Effect + color (RGB models only) --------------------------------
  Column {
    visible: root.hasColor && hw.available === true
    width: parent.width
    spacing: Style.space(8)

    Dropdown {
      width: Math.min(parent.width, Style.space(240))
      label: "Effect"
      value: lighting.effect || "static"
      options: hw.effects || ["static"]
      foreground: root.foreground
      accent: root.accentColor
      onChanged: function(value) { root.run(["--set-lighting-effect", value]) }
    }

    Row {
      spacing: Style.space(6)
      width: parent.width

      TextField {
        id: colorField
        width: Style.space(110)
        text: root.pendingColor
        placeholderText: "#rrggbb"
        foreground: root.foreground
        accent: root.accentColor
        // Applies as soon as a complete hex color is typed; no Apply step.
        onTextEdited: {
          var hex = root.normalizeHex(text)
          if (hex) root.chooseColor(hex)
        }
      }

      Repeater {
        model: ["#ffffff", "#ff2b2b", "#2bd6ff", "#5cff5c", "#c760ff", "#ffb020"]
        delegate: Rectangle {
          required property string modelData
          width: Style.space(22)
          height: Style.space(22)
          radius: width / 2
          color: modelData
          border.width: root.pendingColor.toLowerCase() === modelData ? 2 : 1
          border.color: root.pendingColor.toLowerCase() === modelData ? root.foreground : root.dim

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              colorField.text = modelData
              root.chooseColor(modelData)
            }
          }
        }
      }
    }
  }

  function normalizeHex(value) {
    var v = String(value).trim()
    if (v.charAt(0) !== "#") v = "#" + v
    return /^#[0-9a-fA-F]{6}$/.test(v) ? v.toLowerCase() : ""
  }

  // Selecting a color is the whole action: it becomes the paint color for
  // the per-key editor and is sent to the keyboard immediately.
  function chooseColor(hex) {
    root.pendingColor = hex
    colorDebounce.restart()
  }

  // Typing a hex code fires on every keystroke that forms a valid color;
  // this keeps it to one device write once input settles.
  Timer {
    id: colorDebounce
    interval: 120
    onTriggered: root.run(["--set-lighting-color", root.pendingColor])
  }

  // --- Theme sync --------------------------------------------------------
  ToggleRow {
    visible: root.hasColor && hw.available === true
    width: parent.width
    title: "Sync to Omarchy theme"
    description: "Keeps the keyboard color matched to the active theme's accent (" + (lighting.theme_color || "none set") + "), and updates automatically when you change themes."
    checked: lighting.sync_theme === true
    foreground: root.foreground
    dim: root.dim
    accentColor: root.accentColor
    fontFamily: root.fontFamily
    onToggled: root.run(["--set-theme-sync", lighting.sync_theme ? "0" : "1"])
  }

  // --- Logo --------------------------------------------------------------
  ToggleRow {
    visible: root.isPerKey && modelInfo.logo === true && hw.available === true
    width: parent.width
    title: "Legion logo light"
    description: "Lid logo LED, part of the same per-key controller."
    checked: lighting.logo_on !== false
    foreground: root.foreground
    dim: root.dim
    accentColor: root.accentColor
    fontFamily: root.fontFamily
    onToggled: root.run(["--set-lighting-logo", lighting.logo_on ? "0" : "1"])
  }

  // --- Per-key groups ------------------------------------------------
  Column {
    visible: root.isPerKey && hw.available === true
    width: parent.width
    spacing: Style.space(8)

    PanelSeparator { width: parent.width }

    Text {
      textFormat: Text.PlainText
      text: "Per-key groups"
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: true
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: "Recolor a named key group using the color set above."
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.Wrap
    }

    Flow {
      width: parent.width
      spacing: Style.space(6)

      Repeater {
        model: hw.groups || []
        delegate: BorderSurface {
          required property var modelData
          implicitWidth: groupText.implicitWidth + Style.space(14)
          implicitHeight: groupText.implicitHeight + Style.space(8)
          radius: Style.cornerRadius
          color: "transparent"
          borderSpec: Border.controlSpec("normal", root.dim, root.accentColor)

          Text {
            id: groupText
            textFormat: Text.PlainText
            anchors.centerIn: parent
            text: modelData
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.run(["--set-lighting-group", modelData, root.pendingColor])
          }
        }
      }
    }

    PerKeyGrid {
      width: parent.width
      layout: hw.layout || ({})
      activeColor: root.pendingColor
      foreground: root.foreground
      dim: root.dim
      onKeyMapChanged: function(map) { root.run(["--set-lighting-keymap", JSON.stringify(map)]) }
    }
  }

  // --- Permissions ------------------------------------------------------
  BorderSurface {
    visible: hw.available === true && lighting.permissions_installed !== true
    width: parent.width
    implicitHeight: permCol.implicitHeight + Style.space(16)
    color: Style.hoverFillFor(root.foreground, root.foreground)
    borderSpec: Border.controlSpec("normal", root.dim, root.accentColor)
    radius: Style.cornerRadius

    Column {
      id: permCol
      anchors.left: parent.left
      anchors.right: installBtn.left
      anchors.rightMargin: Style.space(8)
      anchors.top: parent.top
      anchors.margins: Style.space(8)
      spacing: Style.space(2)

      Text {
        textFormat: Text.PlainText
        text: "Lighting permissions"
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: "One-time setup so lighting changes don't need a password prompt each time."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.Wrap
      }
    }

    PanelActionButton {
      id: installBtn
      anchors.right: parent.right
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      iconText: "󰌾"
      tooltipText: "Install (needs password)"
      foreground: root.foreground
      onClicked: root.run(["--install-lighting-permissions"])
    }
  }
}
