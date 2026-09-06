/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        india: {
          DEFAULT: "#0f6b3d",
          light: "#e6f4ec",
        },
        intl: {
          DEFAULT: "#1d4ed8",
          light: "#e8edfc",
        },
        saffron: "#d97706",
      },
    },
  },
  plugins: [],
};
