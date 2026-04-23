// theme.ts — color palette sesuai Minimal-tui.html
import { SyntaxStyle } from "@opentui/core"

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

export function createMonokaiStyle(): SyntaxStyle {
  return SyntaxStyle.fromStyles({
    // ── Code syntax ────────────────────────────────────────────────────────
    "keyword":               { fg: C.pink },
    "keyword.control":       { fg: C.pink },
    "keyword.return":        { fg: C.pink },
    "keyword.import":        { fg: C.pink },
    "string":                { fg: "#e6db74" },
    "string.special":        { fg: "#e6db74" },
    "number":                { fg: C.purple },
    "float":                 { fg: C.purple },
    "boolean":               { fg: C.purple },
    "constant":              { fg: C.purple },
    "constant.builtin":      { fg: C.purple },
    "function":              { fg: C.green },
    "function.call":         { fg: C.green },
    "function.method":       { fg: C.green },
    "function.builtin":      { fg: C.cyan },
    "type":                  { fg: C.cyan },
    "type.builtin":          { fg: C.cyan },
    "variable":              { fg: C.white },
    "variable.builtin":      { fg: C.orange },
    "variable.parameter":    { fg: C.orange },
    "operator":              { fg: C.pink },
    "punctuation":           { fg: C.white },
    "comment":               { fg: C.gray, italic: true },
    "comment.line":          { fg: C.gray, italic: true },
    "tag":                   { fg: C.pink },
    "attribute":             { fg: C.green },
    "escape":                { fg: C.cyan },
    "conceal":               { fg: C.gray },

    // ── Markdown markup ────────────────────────────────────────────────────
    // Headers — makin tinggi level makin terang
    "markup.heading":        { fg: C.blue },
    "markup.heading.1":      { fg: C.blue },
    "markup.heading.2":      { fg: C.cyan },
    "markup.heading.3":      { fg: C.green },
    "markup.heading.4":      { fg: C.orange },
    "markup.heading.5":      { fg: C.purple },
    "markup.heading.6":      { fg: C.gray },

    // Bold — orange supaya kelihatan berbeda
    "markup.bold":           { fg: C.orange },
    "markup.strong":         { fg: C.orange },

    // Italic — purple
    "markup.italic":         { fg: C.purple },
    "markup.emphasis":       { fg: C.purple },

    // Inline code — kuning + bg gelap
    "markup.raw":            { fg: "#e6db74" },
    "markup.raw.inline":     { fg: "#e6db74" },
    "markup.raw.block":      { fg: "#e6db74" },

    // List markers
    "markup.list":           { fg: C.cyan },
    "markup.list.bullet":    { fg: C.cyan },
    "markup.list.numbered":  { fg: C.cyan },

    // Links
    "markup.link":           { fg: C.blue },
    "markup.link.url":       { fg: C.blue },
    "markup.link.label":     { fg: C.cyan },

    // Quote
    "markup.quote":          { fg: C.gray },

    // Horizontal rule / separator
    "markup.separator":      { fg: C.gray2 },
  })
}

let _style: SyntaxStyle | null = null
export function getMonokaiStyle(): SyntaxStyle {
  // Selalu buat fresh — tidak cache, supaya markup styles selalu apply
  if (!_style) _style = createMonokaiStyle()
  return _style
}
