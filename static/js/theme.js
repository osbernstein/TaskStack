function hexToHSL(hex) {
  let r = parseInt(hex.slice(1, 3), 16) / 255;
  let g = parseInt(hex.slice(3, 5), 16) / 255;
  let b = parseInt(hex.slice(5, 7), 16) / 255;
  let max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;
  if (max === min) { h = s = 0; } else {
    let d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

function hslToHex(h, s, l) {
  l /= 100;
  const a = s * Math.min(l, 1 - l) / 100;
  const f = n => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function applyDynamicColor(hex) {
  const { h, s } = hexToHSL(hex);
  const root = document.documentElement;
  root.style.setProperty('--bg-outer', `hsl(${h}, ${Math.min(s, 75)}%, 88%)`);
  root.style.setProperty('--bg-inner', `hsl(${h}, ${Math.min(s, 65)}%, 95%)`);
  root.style.setProperty('--circle-glow', `hsl(${h}, ${Math.min(s, 60)}%, 94%)`);
  root.style.setProperty('--circle-border', `hsla(${h}, ${Math.min(s, 80)}%, 40%, 0.25)`);
  root.style.setProperty('--text', `hsl(${h}, ${Math.min(s + 10, 90)}%, 28%)`);
  root.style.setProperty('--text-muted', `hsl(${h}, ${Math.min(s + 5, 80)}%, 40%)`);
  root.style.setProperty('--accent', `hsl(${h}, ${Math.min(s, 85)}%, 45%)`);
  root.style.setProperty('--card-border', `hsla(${h}, ${Math.min(s, 70)}%, 80%, 0.8)`);
  localStorage.setItem('taskstack-hex', hex);
}

// Golden ratio conjugate dispersion ensures distinct hue for every tag
function hashStringToHue(str) {
  let hash = 0;
  const clean = (str || '').trim().toLowerCase();
  for (let i = 0; i < clean.length; i++) {
    hash = (hash * 31 + clean.charCodeAt(i)) & 0xFFFFFFFF;
  }
  const goldenRatioConjugate = 0.618033988749895;
  let h = ((Math.abs(hash) * goldenRatioConjugate) % 1) * 360;
  return Math.round(h);
}

function getTagStyle(tagName) {
  const clean = (tagName || '').trim().toLowerCase();

  // "General" is always neutral light grey
  if (clean === 'general') {
    return `background-color: #f1f5f9; color: #475569; border-color: #cbd5e1;`;
  }

  let customColors = {};
  try {
    customColors = JSON.parse(localStorage.getItem('taskstack-tag-colors')) || {};
  } catch (e) {}

  if (customColors[clean]) {
    const { h, s } = hexToHSL(customColors[clean]);
    return `background-color: hsl(${h}, ${Math.min(s, 70)}%, 90%); color: hsl(${h}, ${Math.min(s + 20, 95)}%, 24%); border-color: hsla(${h}, 70%, 50%, 0.3);`;
  }

  const hue = hashStringToHue(clean);
  return `background-color: hsl(${hue}, 75%, 91%); color: hsl(${hue}, 85%, 25%); border-color: hsla(${hue}, 70%, 50%, 0.3);`;
}
