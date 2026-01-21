export const theme = {
  colors: {
    bg: "#0b0e11", // near-black
    surface: "#0f141a", // charcoal panel
    surface2: "#121a22",
    border: "#1f2a35",
    text: "#e6e9ee",
    textMuted: "#a9b4c0",
    textFaint: "#7f8a96",
    accent: "#d71920", // IBKR-ish red
    accentHover: "#ff2a33",
    danger: "#b31318",
    success: "#2bb673",
    codeBg: "#0d1117",
  },
  radius: {
    sm: "6px",
    md: "10px",
    lg: "14px",
  },
  spacing: {
    xs: "6px",
    sm: "10px",
    md: "14px",
    lg: "18px",
    xl: "24px",
  },
  typography: {
    fontSans:
      "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji",
    fontMono:
      "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace",
    sizeSm: "13px",
    sizeMd: "14px",
    sizeLg: "16px",
    line: "1.45",
  },
} as const;

export type Theme = typeof theme;
