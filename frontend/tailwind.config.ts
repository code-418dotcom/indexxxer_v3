/**
 * Tailwind CSS v4 config.
 * In v4, most theme customisation moves to globals.css via @theme.
 * This file is kept for any JS-side config that can't live in CSS
 * (e.g. content paths if auto-detection is insufficient).
 */
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  // darkMode handled via next-themes (class strategy, injected via ThemeProvider)
  darkMode: "class",
};

export default config;
