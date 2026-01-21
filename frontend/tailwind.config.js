/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0e11",
        surface: "#0f141a",
        surface2: "#121a22",
        border: "#1f2a35",
        text: "#e6e9ee",
        muted: "#a9b4c0",
        faint: "#7f8a96",
        accent: "#d71920",
        accentHover: "#ff2a33",
        danger: "#b31318",
        codeBg: "#0d1117",
      },
      boxShadow: {
        ib: "0 0 0 1px rgba(31,42,53,0.9)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "Apple Color Emoji",
          "Segoe UI Emoji",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
}

