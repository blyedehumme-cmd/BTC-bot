import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#04050f',
        surface: '#0f1320',
        glow: '#00d4ff',
        accent: '#3ba4ff',
        muted: '#7a8ba6',
      },
      boxShadow: {
        glow: '0 0 45px rgba(20, 205, 255, 0.14)',
      },
      backgroundImage: {
        'neon-grid': 'radial-gradient(circle at top, rgba(0, 212, 255, 0.14), transparent 25%), radial-gradient(circle at 20% 20%, rgba(59, 164, 255, 0.1), transparent 18%)',
      },
      animation: {
        float: 'float 10s ease-in-out infinite',
        pulseGlow: 'pulseGlow 4s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '0.88' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
