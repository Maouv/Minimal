// theme.ts — color palette sesuai Minimal-tui.html
import { SyntaxStyle, RGBA } from "@opentui/core"

export const C = {
  bg:     "#0d0d0d",
  bg2:    "#141414",
  bg3:    "#1a1a1a",
  border: "#242424",
  green:  "#a8ff60",
  gdim:   "#4e7a22",
  orange: "#fd971f",
  pink:   "#f92672",
  purple: "#ae81ff",
  cyan:   "#66d9e8",
  blue:   "#89d4f5",
  white:  "#f8f8f2",
  gray:   "#6b6b6b",
  gray2:  "#3d3d3d",
  gray3:  "#2a2a2a",
} as const

export const MODE_COLOR: Record<string, string> = {
  "ask":        C.cyan,
  "edit-block": C.orange,
  "edit-udiff": C.purple,
  "edit-whole": C.pink,
}

const r = (hex: string) => RGBA.fromHex(hex)

export function createMonokaiStyle(): SyntaxStyle {
  return SyntaxStyle.fromStyles({
    // ── Code syntax ────────────────────────────────────────────────────────
    "keyword":               { fg: r(C.pink) },
    "keyword.control":       { fg: r(C.pink) },
    "keyword.return":        { fg: r(C.pink) },
    "keyword.import":        { fg: r(C.pink) },
    "string":                { fg: r("#e6db74") },
    "string.special":        { fg: r("#e6db74") },
    "number":                { fg: r(C.purple) },
    "float":                 { fg: r(C.purple) },
    "boolean":               { fg: r(C.purple) },
    "constant":              { fg: r(C.purple) },
    "constant.builtin":      { fg: r(C.purple) },
    "function":              { fg: r(C.green) },
    "function.call":         { fg: r(C.green) },
    "function.method":       { fg: r(C.green) },
    "function.builtin":      { fg: r(C.cyan) },
    "type":                  { fg: r(C.cyan) },
    "type.builtin":          { fg: r(C.cyan) },
    "variable":              { fg: r(C.white) },
    "variable.builtin":      { fg: r(C.orange) },
    "variable.parameter":    { fg: r(C.orange) },
    "operator":              { fg: r(C.pink) },
    "punctuation":           { fg: r(C.white) },
    "comment":               { fg: r(C.gray), italic: true },
    "comment.line":          { fg: r(C.gray), italic: true },
    "tag":                   { fg: r(C.pink) },
    "attribute":             { fg: r(C.green) },
    "escape":                { fg: r(C.cyan) },
    "conceal":               { fg: r(C.gray) },

    // ── Markdown markup ────────────────────────────────────────────────────
    "markup.heading":        { fg: r(C.blue) },
    "markup.heading.1":      { fg: r(C.blue) },
    "markup.heading.2":      { fg: r(C.cyan) },
    "markup.heading.3":      { fg: r(C.green) },
    "markup.heading.4":      { fg: r(C.orange) },
    "markup.heading.5":      { fg: r(C.purple) },
    "markup.heading.6":      { fg: r(C.gray) },
    "markup.bold":           { fg: r(C.orange) },
    "markup.strong":         { fg: r(C.orange) },
    "markup.italic":         { fg: r(C.purple) },
    "markup.emphasis":       { fg: r(C.purple) },
    "markup.raw":            { fg: r("#e6db74") },
    "markup.raw.inline":     { fg: r("#e6db74") },
    "markup.raw.block":      { fg: r("#e6db74") },
    "markup.list":           { fg: r(C.cyan) },
    "markup.list.bullet":    { fg: r(C.cyan) },
    "markup.list.numbered":  { fg: r(C.cyan) },
    "markup.link":           { fg: r(C.blue) },
    "markup.link.url":       { fg: r(C.blue) },
    "markup.link.label":     { fg: r(C.cyan) },
    "markup.quote":          { fg: r(C.gray) },
    "markup.separator":      { fg: r(C.gray2) },
  })
}

let _style: SyntaxStyle | null = null
export function getMonokaiStyle(): SyntaxStyle {
  if (!_style) _style = createMonokaiStyle()
  return _style
}
