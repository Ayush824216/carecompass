/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        surface: v("surface"),
        sunken: v("sunken"),
        ink: v("ink"),
        muted: v("muted"),
        line: v("line"),
        primary: { DEFAULT: v("primary"), deep: v("primary-deep"), soft: v("primary-soft"), ink: v("primary-ink") },
        accent: { DEFAULT: v("accent"), soft: v("accent-soft") },
        emergency: { DEFAULT: v("emergency"), deep: v("emergency-deep"), soft: v("emergency-soft") },
        routine: { DEFAULT: v("routine"), soft: v("routine-soft") },
        sameday: { DEFAULT: v("sameday"), soft: v("sameday-soft") },
      },
      fontFamily: {
        display: ['"Fraunces"', '"Noto Serif Devanagari"', "Georgia", "serif"],
        sans: ['"Source Sans 3"', '"Noto Sans Devanagari"', "system-ui", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "Consolas", "monospace"],
      },
      maxWidth: { page: "76rem" },
      borderRadius: { xl2: "1.25rem" },
      boxShadow: {
        card: "0 1px 2px rgb(16 42 38 / 0.06), 0 4px 16px -6px rgb(16 42 38 / 0.10)",
        lift: "0 2px 4px rgb(16 42 38 / 0.06), 0 14px 32px -12px rgb(16 42 38 / 0.22)",
      },
    },
  },
  plugins: [],
};
