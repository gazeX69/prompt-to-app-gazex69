/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#030304',
        foreground: '#F0F0F0',
        panel: '#0C0C0F',
        border: 'rgba(255, 255, 255, 0.08)',
        accent: '#18181B',
        'accent-hover': '#232328',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow': '0 0 40px -10px rgba(56, 189, 248, 0.15)',
        'glass': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
      }
    },
  },
  plugins: [],
}
