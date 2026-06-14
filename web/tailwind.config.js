/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c2d3ff',
          300: '#93b0ff',
          400: '#5c83ff',
          500: '#3a5eff',  // primary
          600: '#2040e6',
          700: '#1730c0',
          800: '#19289b',
          900: '#1a277a',
          950: '#111749',
        },
        dark: {
          50:  '#f6f7f9',
          100: '#eceef2',
          200: '#d5d9e3',
          300: '#b0b9cc',
          400: '#8594ae',
          500: '#657594',
          600: '#505e7b',
          700: '#414d64',
          800: '#384155',
          900: '#323848',
          950: '#0f1117',  // bg-dark
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-glow': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(58,94,255,0.3), transparent)',
      },
    },
  },
  plugins: [],
}
