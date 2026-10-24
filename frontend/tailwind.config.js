/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F3F5F8", ink: "#12202F", slate2: "#5B6B7C", line: "#DCE2EA",
        thread: { DEFAULT: "#0E7C7B", soft: "#E1F2F1", deep: "#0A5857" },     // fashion (target domain)
        saffron: { DEFAULT: "#D98E1F", soft: "#FBEFD8", deep: "#8A560B" },    // home & lifestyle (source domain)
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Figtree", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
