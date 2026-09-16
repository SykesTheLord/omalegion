import QtQuick
import qs.Commons
import qs.Ui

// Per-key editor drawn as the actual keyboard. Key positions and sizes come
// from the layout matching the keyboard's physical format (ANSI/ISO/JIS, read
// from the keyboard itself); the labels come from the keyboard layout the
// system is using, so a Danish layout shows Æ Ø Å where a US one shows ; ' [.
//
// Paints apply live. Changes are batched over a short debounce and sent as
// the full painted map in one engine call (one HID report), so clicking
// through many keys doesn't spawn a process per click.
Column {
  id: root

  // { format, format_source, os_layout, os_layout_name, width, height,
  //   keys: [{ code, x, y, w, h, label }] } — positions in key units.
  property var layout: ({})
  property color activeColor: "#ffffff"
  property color foreground
  property color dim
  property var keyColors: ({})

  readonly property var keys: layout && layout.keys ? layout.keys : []
  readonly property real unit: layout && layout.width ? board.width / layout.width : 0

  signal keyMapChanged(var map)

  // Keeps a key's label readable once it's painted with an arbitrary color.
  function textOn(paintColor) {
    var c = Qt.color(paintColor)
    return (c.r * 0.299 + c.g * 0.587 + c.b * 0.114) > 0.6 ? "#000000" : "#ffffff"
  }

  function summary() {
    var bits = []
    if (layout.os_layout_name)
      bits.push(layout.os_layout_name + (layout.os_layout ? " (" + layout.os_layout + ")" : ""))
    if (layout.format)
      bits.push(String(layout.format).toUpperCase() + (layout.format_source === "keyboard"
        ? " layout, detected from the keyboard"
        : " layout, guessed from the system layout"))
    return bits.join(" · ")
  }

  spacing: Style.space(6)

  Text {
    visible: root.summary() !== ""
    textFormat: Text.PlainText
    width: parent.width
    text: root.summary()
    color: root.dim
    font.pixelSize: Style.font.caption
    wrapMode: Text.Wrap
  }

  Text {
    textFormat: Text.PlainText
    width: parent.width
    text: "Click keys to paint them with the color above; changes apply immediately. "
      + Object.keys(root.keyColors).length + " of " + root.keys.length + " painted."
    color: root.dim
    font.pixelSize: Style.font.caption
    wrapMode: Text.Wrap
  }

  Item {
    id: board
    width: parent.width
    height: root.layout && root.layout.height ? root.layout.height * root.unit : 0

    Repeater {
      model: root.keys
      delegate: Rectangle {
        id: cell
        required property var modelData
        readonly property string code: String(modelData.code)
        readonly property bool painted: root.keyColors[code] !== undefined
        readonly property real gap: Math.max(1, root.unit * 0.1)

        x: modelData.x * root.unit + gap / 2
        y: modelData.y * root.unit + gap / 2
        width: Math.max(1, modelData.w * root.unit - gap)
        height: Math.max(1, modelData.h * root.unit - gap)
        radius: Math.max(2, root.unit * 0.12)
        color: cell.painted ? root.keyColors[cell.code] : "transparent"
        border.width: 1
        border.color: cell.painted ? Qt.darker(root.keyColors[cell.code], 1.5) : root.dim

        Text {
          anchors.fill: parent
          anchors.margins: 1
          textFormat: Text.PlainText
          text: modelData.label || ""
          color: cell.painted ? root.textOn(root.keyColors[cell.code]) : root.foreground
          font.pixelSize: Math.max(7, Math.min(Style.font.caption, root.unit * 0.34))
          horizontalAlignment: Text.AlignHCenter
          verticalAlignment: Text.AlignVCenter
          elide: Text.ElideRight
        }

        MouseArea {
          anchors.fill: parent
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            var next = Object.assign({}, root.keyColors)
            if (cell.painted && next[cell.code] === root.activeColor.toString())
              delete next[cell.code]
            else
              next[cell.code] = root.activeColor.toString()
            root.keyColors = next
            applyDebounce.restart()
          }
        }
      }
    }
  }

  Row {
    spacing: Style.space(8)

    PanelActionButton {
      iconText: "▦"
      tooltipText: "Select all keys with the color above"
      foreground: root.foreground
      onClicked: {
        var next = {}
        var color = root.activeColor.toString()
        for (var i = 0; i < root.keys.length; i++)
          next[String(root.keys[i].code)] = color
        root.keyColors = next
        applyDebounce.restart()
      }
    }

    PanelActionButton {
      iconText: "✕"
      tooltipText: "Clear painted keys"
      foreground: root.foreground
      onClicked: {
        root.keyColors = ({})
        applyDebounce.restart()
      }
    }
  }

  Timer {
    id: applyDebounce
    interval: 150
    onTriggered: root.keyMapChanged(root.keyColors)
  }
}
