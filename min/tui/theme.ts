// theme.ts — Monokai color palette + SyntaxStyle
import { SyntaxStyle } from "@opentui/core"

// ── Monokai palette ───────────────────────────────────────────────────────────
export const MK = {
  bg:         "#272822",
  bg2:        "#1e1f1c",
  bg3:        "#2d2e2a",
  bgHL:       "#3e3d32",
  border:     "#49483e",
  comment:    "#75715e",
  white:      "#f8f8f2",
  yellow:     "#e6db74",
  orange:     "#fd971f",
  orangeL:    "#ef5f30",   // lighter orange / function names
  pink:       "#f92672",
  purple:     "#ae81ff",
  green:      "#a6e22e",
  cyan:       "#66d9e8",
  blue:       "#74b9ff",

  // Semantic
  user:       "#a6e22e",   // green — user messages
  assistant:  "#f8f8f2",   // white — assistant
  system:     "#75715e",   // comment grey
  streaming:  "#fd971f",   // orange — saat streaming
  error:      "#f92672",   // pink
  modeAsk:    "#a6e22e",
  modeEdit:   "#fd971f",
  modeEditU:  "#ae81ff",
  modeEditW:  "#f92672",

  // Diff
  addedBg:    "#293d1a",
  removedBg:  "#3d1a1a",
  addedSign:  "#a6e22e",
  removedSign:"#f92672",
  lineNumFg:  "#49483e",
  lineNumBg:  "#1e1f1c",
} as const

// ── Mode colors ───────────────────────────────────────────────────────────────
export const MODE_COLOR: Record<string, string> = {
  "ask":        MK.modeAsk,
  "edit-block": MK.modeEdit,
  "edit-udiff": MK.modeEditU,
  "edit-whole": MK.modeEditW,
}

// ── Monokai SyntaxStyle ───────────────────────────────────────────────────────
// Token names sesuai tree-sitter highlight names
export function createMonokaiStyle(): SyntaxStyle {
  return SyntaxStyle.fromStyles({
    // Keywords
    "keyword":                  { fg: MK.pink },
    "keyword.control":          { fg: MK.pink },
    "keyword.operator":         { fg: MK.pink },
    "keyword.return":           { fg: MK.pink },
    "keyword.import":           { fg: MK.pink },

    // Strings
    "string":                   { fg: MK.yellow },
    "string.special":           { fg: MK.yellow },
    "character":                { fg: MK.yellow },

    // Numbers & constants
    "number":                   { fg: MK.purple },
    "float":                    { fg: MK.purple },
    "boolean":                  { fg: MK.purple },
    "constant":                 { fg: MK.purple },
    "constant.builtin":         { fg: MK.purple },

    // Functions
    "function":                 { fg: MK.green },
    "function.call":            { fg: MK.green },
    "function.method":          { fg: MK.green },
    "function.builtin":         { fg: MK.cyan },
    "constructor":              { fg: MK.green },

    // Types & classes
    "type":                     { fg: MK.cyan },
    "type.builtin":             { fg: MK.cyan },
    "class":                    { fg: MK.cyan },

    // Variables
    "variable":                 { fg: MK.white },
    "variable.builtin":         { fg: MK.orange },
    "variable.parameter":       { fg: MK.orange },
    "property":                 { fg: MK.white },

    // Operators & punctuation
    "operator":                 { fg: MK.pink },
    "punctuation":              { fg: MK.white },
    "punctuation.bracket":      { fg: MK.white },
    "punctuation.delimiter":    { fg: MK.white },

    // Comments
    "comment":                  { fg: MK.comment, italic: true },
    "comment.line":             { fg: MK.comment, italic: true },
    "comment.block":            { fg: MK.comment, italic: true },

    // Tags (HTML/JSX)
    "tag":                      { fg: MK.pink },
    "tag.attribute":            { fg: MK.green },
    "attribute":                { fg: MK.green },

    // Misc
    "escape":                   { fg: MK.cyan },
    "namespace":                { fg: MK.cyan },
    "module":                   { fg: MK.white },
    "label":                    { fg: MK.cyan },
    "conceal":                  { fg: MK.comment },
  })
}

// Singleton — buat sekali, pakai di semua komponen
let _style: SyntaxStyle | null = null
export function getMonokaiStyle(): SyntaxStyle {
  if (!_style) _style = createMonokaiStyle()
  return _style
}
