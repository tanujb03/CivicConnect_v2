import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // CivicConnect Design System tokens — shared with admin
        ground: "var(--ground)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        dot: "var(--dot)",
        wine: "var(--wine)",
        "on-wine": "var(--on-wine)",
        fire: "var(--fire)",
        "on-fire": "var(--on-fire)",
        rust: "var(--rust)",
        "rust-deep": "var(--rust-deep)",
        lime: "var(--lime)",
        amber: "var(--amber)",
        "lime-tint": "var(--lime-tint)",
        "heat-1": "var(--heat-1)",
        "heat-2": "var(--heat-2)",
        "heat-3": "var(--heat-3)",
        "heat-4": "var(--heat-4)",
        "heat-5": "var(--heat-5)",

        // Shadcn compatibility
        border: "var(--ink)",
        input: "var(--dot)",
        ring: "var(--lime)",
        background: "var(--ground)",
        foreground: "var(--ink)",
        primary: {
          DEFAULT: "var(--wine)",
          foreground: "var(--on-wine)",
        },
        secondary: {
          DEFAULT: "var(--surface)",
          foreground: "var(--ink)",
        },
        destructive: {
          DEFAULT: "var(--fire)",
          foreground: "var(--on-fire)",
        },
        accent: {
          DEFAULT: "var(--lime-tint)",
          foreground: "var(--ink)",
        },
        popover: {
          DEFAULT: "var(--surface)",
          foreground: "var(--ink)",
        },
        card: {
          DEFAULT: "var(--surface)",
          foreground: "var(--ink)",
        },
      },
      borderRadius: {
        xl: "var(--radius-xl)",
        lg: "var(--radius-lg)",
        md: "var(--radius-md)",
        sm: "var(--radius-sm)",
      },
      boxShadow: {
        hard: "var(--shadow-hard)",
        card: "var(--shadow-card)",
        lift: "var(--shadow-lift)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
        script: ["var(--font-script)"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
