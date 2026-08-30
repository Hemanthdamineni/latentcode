/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        latent: {
          bg: "#0b0d12",
          panel: "#13161d",
          border: "#1f2330",
          accent: "#7c5cff",
          warn: "#f59e0b",
          danger: "#ef4444",
          ok: "#10b981",
          muted: "#6b7280",
        },
      },
    },
  },
  plugins: [],
};