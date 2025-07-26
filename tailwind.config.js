/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html", // Scan your HTML file for Tailwind classes
    // Add other files if you have them, e.g., "./src/**/*.{js,jsx,ts,tsx}" for React
  ],
  theme: {
    extend: {
      fontFamily: {
        inter: ['Inter', 'sans-serif'], // Define Inter font
      },
    },
  },
  plugins: [],
}