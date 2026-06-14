import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0d1117",
        panel: "#161b22",
        "panel-alt": "#1a1a2e",
        border: "#30363d",
        muted: "#8b949e",
        accent: "#ecad0a",
        blue: "#209dd7",
        purple: "#753991",
        up: "#16c784",
        down: "#ea3943",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "monospace"],
      },
      keyframes: {
        flashUp: {
          "0%": { backgroundColor: "rgba(22,199,132,0.45)" },
          "100%": { backgroundColor: "transparent" },
        },
        flashDown: {
          "0%": { backgroundColor: "rgba(234,57,67,0.45)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        "flash-up": "flashUp 0.6s ease-out",
        "flash-down": "flashDown 0.6s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
