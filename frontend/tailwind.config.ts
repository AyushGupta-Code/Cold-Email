import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111318",
        mist: "#eff3f2",
        ember: "#d97706",
        spruce: "#0f766e",
        sand: "#f7efe1",
        slatewarm: "#384254",
      },
      boxShadow: {
        panel: "0 20px 60px rgba(17, 19, 24, 0.12)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"Aptos"', '"Segoe UI"', "sans-serif"],
        body: ['"Aptos"', '"Segoe UI"', "sans-serif"],
      },
      backgroundImage: {
        mesh:
          "radial-gradient(circle at top left, rgba(217,119,6,0.18), transparent 28%), radial-gradient(circle at 85% 0%, rgba(15,118,110,0.2), transparent 25%), linear-gradient(180deg, #f8faf8 0%, #f2ede4 100%)",
      },
    },
  },
  plugins: [],
} satisfies Config;

