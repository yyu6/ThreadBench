// Exact palette/type setup from the original site, compiled locally.
const path = require('node:path');
const root = path.resolve(__dirname, '..');
module.exports = {
  content: [path.join(root, 'docs/*.html'), path.join(root, 'scripts/templates/*.html'), path.join(root, 'scripts/paper_home.py')],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
        serif: ['Instrument Serif', 'Georgia', 'serif'],
      },
      colors: {
        bg: '#FFFFFF', surf: '#FAFAF7', ink: '#0E0E0F', text: '#1A1A1A',
        mute: '#555555', mute2: '#707070', line: '#E4E4E0', line2: '#D0D0CC',
        accent: '#0F62D7', red: '#B91C1C',
      },
    },
  },
};
