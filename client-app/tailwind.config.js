/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: { DEFAULT: '#0969da', hover: '#0550ae' },
        success: '#1a7f37',
        warning: '#9a6700',
        danger: '#cf222e',
        bg: {
          primary: '#ffffff',
          secondary: '#f6f8fa',
          tertiary: '#eaeef2',
          hover: '#d0d7de',
        },
        border: { DEFAULT: '#d0d7de' },
        text: {
          primary: '#1f2328',
          secondary: '#57606a',
          muted: '#8c959f',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
