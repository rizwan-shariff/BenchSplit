/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#221a10",
        espresso: "#30251f",
        paper: "#fff8f3",
        parchment: "#fbecda",
        "parchment-deep": "#f5e6d4",
        brass: "#a77b42",
        "brass-soft": "#e7c088",
        oxblood: "#913f40",
        forest: "#426b53",
        outline: "#d1c4be",
        "muted-ink": "#6b625b",
      },
      fontFamily: {
        editorial: ["EB Garamond", "Georgia", "serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 1px 3px rgba(48, 37, 31, 0.06), 0 8px 24px rgba(48, 37, 31, 0.035)",
      },
    },
  },
  plugins: [],
};
