/**
 * React Bits - SpotlightCard Universal Engine for QuestionIQ
 * Replicates the exact physics, math, and rendering of React Bits SpotlightCard
 * Automatically applies spotlight effects across all university cards.
 */

(function () {
  'use strict';

  const THEMES = {
    dark: {
      surface: '#002244',
      border: 'rgba(255, 255, 255, 0.12)',
      shadow: '0 24px 48px -24px rgba(0, 0, 0, 0.6)',
      light: '#ffffff',
      fill: 0.9,
      edge: 1
    },
    light: {
      surface: '#ffffff',
      border: 'rgba(226, 232, 240, 0.85)',
      shadow: '0 1px 3px rgba(0, 0, 0, 0.04), 0 10px 24px -4px rgba(0, 51, 102, 0.06)',
      light: '#C8961E', // University Gold accent for QuestionIQ!
      fill: 0.28,
      edge: 0.85
    }
  };

  const SHAPES = ['circle', 'beam'];

  const NOISE =
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const falloff = (color, softness) => {
    const soft = clamp(softness, 0, 1);
    const core = Math.pow(1 - soft, 1.5) * 0.85;
    const stop = (alpha, at) =>
      `color-mix(in srgb, ${color} ${(alpha * 100).toFixed(2)}%, transparent) ${(at * 100).toFixed(2)}%`;
    const list = [stop(1, 0)];
    for (let i = 0; i <= 14; i++) {
      const t = core + ((1 - core) * i) / 14;
      const g = (t - core) / (1 - core);
      const smooth = 1 - g * g * (3 - 2 * g);
      const glow = Math.exp(-4.6 * g * g) * (1 - Math.pow(g, 6));
      list.push(stop(smooth + (glow - smooth) * soft, t));
    }
    return list.join(', ');
  };

  /**
   * Initializes a single DOM element with the SpotlightCard behavior
   */
  function attachSpotlightCard(root, options = {}) {
    if (!root || root.dataset.spotlightInit === 'true') return;
    root.dataset.spotlightInit = 'true';

    const cardTheme = options.theme || root.dataset.theme || (root.classList.contains('dark-theme') ? 'dark' : 'light');
    const palette = THEMES[cardTheme] || THEMES.light;
    const color = options.spotlightColor || root.dataset.spotlightColor || palette.light;
    const shape = options.shape || root.dataset.shape || 'circle';
    const form = SHAPES.includes(shape) ? shape : 'circle';
    const softness = options.softness !== undefined ? options.softness : 0.7;
    const intensity = options.intensity !== undefined ? options.intensity : 0.18;
    const borderGlow = options.borderGlow !== undefined ? options.borderGlow : 0.85;
    const proximity = options.proximity !== undefined ? options.proximity : 90;
    const smoothing = options.smoothing !== undefined ? options.smoothing : 0.28;
    const ambient = options.ambient !== undefined ? options.ambient : false;
    const flare = options.flare !== undefined ? options.flare : true;
    const grain = options.grain !== undefined ? options.grain : 0;
    const spotlightSize = options.spotlightSize || 260;

    // Apply spotlight card classes and CSS variables
    root.classList.add('spotlight-card');
    root.style.setProperty('--spotlight-card-surface', palette.surface);
    root.style.setProperty('--spotlight-card-border', palette.border);
    root.style.setProperty('--spotlight-card-shadow', palette.shadow);

    // Create required structural spans
    const light = document.createElement('span');
    light.className = 'spotlight-card__light';
    light.setAttribute('aria-hidden', 'true');

    const noise = document.createElement('span');
    noise.className = 'spotlight-card__grain';
    noise.setAttribute('aria-hidden', 'true');
    noise.style.backgroundImage = NOISE;

    const border = document.createElement('span');
    border.className = 'spotlight-card__border';
    border.setAttribute('aria-hidden', 'true');

    const edge = document.createElement('span');
    edge.className = 'spotlight-card__edge';
    edge.setAttribute('aria-hidden', 'true');

    // Light and grain go behind children
    root.insertBefore(noise, root.firstChild);
    root.insertBefore(light, root.firstChild);

    // Border and edge go on top of borders
    root.appendChild(border);
    root.appendChild(edge);

    const settings = {
      shape: form,
      fill: falloff(color, softness),
      edge: falloff(color, 1),
      size: Math.max(20, spotlightSize),
      intensity: clamp(intensity, 0, 1) * palette.fill,
      borderGlow: clamp(borderGlow, 0, 1) * palette.edge,
      proximity: Math.max(0, proximity),
      smoothing: clamp(smoothing, 0, 1),
      ambient,
      flare,
      grain: clamp(grain, 0, 1)
    };

    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const state = { x: 0, y: 0, presence: 0, flare: 0, time: Math.random() * 60, pressed: false, visible: true };
    const pointer = { x: 0, y: 0, active: false };
    const drawn = { light: '', edge: '', noise: '' };
    let focus = null;
    let raf = 0;
    let last = 0;
    let alive = true;

    const gradient = (s, size, x, y, stops) => {
      if (s.shape === 'beam') {
        const reach = Math.max(size * 0.6, y + size * 0.55);
        return `radial-gradient(${(size * 0.55).toFixed(1)}px ${reach.toFixed(1)}px at ${x.toFixed(1)}px 0px, ${stops})`;
      }
      return `radial-gradient(circle ${size.toFixed(1)}px at ${x.toFixed(1)}px ${y.toFixed(1)}px, ${stops})`;
    };

    const paint = s => {
      const size = s.size * (1 + 0.2 * state.flare);
      const boost = 1 + 0.7 * state.flare;
      const fill = gradient(s, size, state.x, state.y, s.fill);
      const rim = gradient(s, size * 0.6, state.x, s.shape === 'beam' ? 0 : state.y, s.edge);
      if (fill !== drawn.light) {
        drawn.light = fill;
        light.style.background = fill;
      }
      if (rim !== drawn.edge) {
        drawn.edge = rim;
        edge.style.background = rim;
      }
      light.style.opacity = String(Math.min(1, state.presence * s.intensity * boost));
      edge.style.opacity = String(Math.min(1, state.presence * s.borderGlow * boost));
      const grainy = s.grain > 0 ? gradient(s, size, state.x, state.y, '#000 0%, transparent 100%') : 'none';
      if (grainy !== drawn.noise) {
        drawn.noise = grainy;
        noise.style.webkitMaskImage = grainy;
        noise.style.maskImage = grainy;
      }
      noise.style.opacity = String(state.presence * s.grain);
    };

    const tick = now => {
      raf = 0;
      if (!alive) return;
      const s = settings;
      const dt = Math.min(0.05, Math.max(0.001, (now - last) / 1000));
      last = now;
      const rect = root.getBoundingClientRect();
      let tx = state.x;
      let ty = state.y;
      let target = 0;
      if (focus && root.contains(focus)) {
        const box = focus.getBoundingClientRect();
        tx = box.left + box.width / 2 - rect.left;
        ty = box.top + box.height / 2 - rect.top;
        target = 1;
      } else if (pointer.active) {
        tx = pointer.x - rect.left;
        ty = pointer.y - rect.top;
        const gap = Math.hypot(Math.max(0, -tx, tx - rect.width), Math.max(0, -ty, ty - rect.height));
        if (gap === 0) target = 1;
        else if (s.proximity > 0) target = Math.pow(Math.max(0, 1 - gap / s.proximity), 2);
      }
      if (target < 0.6 && s.ambient && state.visible) {
        if (!reduce) state.time += dt;
        const drift = 0.6 - target;
        tx += (rect.width * (0.5 + 0.34 * Math.sin(state.time * 0.43)) - tx) * (drift / 0.6);
        ty += (rect.height * (0.5 + 0.3 * Math.sin(state.time * 0.61 + 1.3)) - ty) * (drift / 0.6);
        target = 0.6;
      }
      if (state.presence < 0.02 && target > 0 && !s.ambient) {
        state.x = tx;
        state.y = ty;
      }
      const follow = reduce || s.smoothing === 0 ? 1 : 1 - Math.exp(-dt / (0.015 + s.smoothing * 0.22));
      state.x += (tx - state.x) * follow;
      state.y += (ty - state.y) * follow;
      const fade = reduce ? 1 : 1 - Math.exp(-dt / (target > state.presence ? 0.1 : 0.32));
      state.presence += (target - state.presence) * fade;
      if (Math.abs(target - state.presence) < 0.002) state.presence = target;
      const press = state.pressed && s.flare && !reduce ? 1 : 0;
      state.flare += (press - state.flare) * (1 - Math.exp(-dt / (press ? 0.05 : 0.28)));
      if (Math.abs(press - state.flare) < 0.002) state.flare = press;
      paint(s);
      const moving = Math.abs(tx - state.x) > 0.1 || Math.abs(ty - state.y) > 0.1;
      const settled = !moving && state.presence === target && state.flare === press;
      if (!settled || (s.ambient && state.visible && !reduce)) raf = requestAnimationFrame(tick);
    };

    const wake = () => {
      if (raf || !alive) return;
      last = performance.now();
      raf = requestAnimationFrame(tick);
    };

    const onMove = event => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
      if (state.presence > 0 || settings.proximity > 0 || root.contains(event.target)) wake();
    };
    const onOut = event => {
      if (event.relatedTarget) return;
      pointer.active = false;
      wake();
    };
    const onDown = event => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
      state.pressed = true;
      wake();
    };
    const onUp = event => {
      if (event.pointerType !== 'mouse') pointer.active = false;
      if (!state.pressed && event.pointerType === 'mouse') return;
      state.pressed = false;
      wake();
    };
    const onFocusIn = event => {
      if (!(event.target instanceof Element) || !event.target.matches(':focus-visible')) return;
      focus = event.target;
      wake();
    };
    const onFocusOut = event => {
      if (root.contains(event.relatedTarget)) return;
      focus = null;
      wake();
    };
    const onScroll = () => {
      if (pointer.active || state.presence > 0) wake();
    };

    const observer = new IntersectionObserver(entries => {
      state.visible = entries.some(entry => entry.isIntersecting);
      if (state.visible) wake();
    });
    observer.observe(root);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerup', onUp, { passive: true });
    window.addEventListener('pointercancel', onUp, { passive: true });
    window.addEventListener('scroll', onScroll, { capture: true, passive: true });
    document.addEventListener('pointerout', onOut, { passive: true });
    root.addEventListener('pointerdown', onDown, { passive: true });
    root.addEventListener('focusin', onFocusIn);
    root.addEventListener('focusout', onFocusOut);
    wake();
  }

  /**
   * Scans and applies the SpotlightCard component to all cards on the page.
   */
  function initAllSpotlightCards() {
    const cardSelectors = [
      '.kpi-card-exact',
      '.topic-card-item',
      '.dept-card-item',
      '.panel-card',
      '.landing-kpi-inner',
      '.landing-kpi-card',
      '.programme-card',
      '.explain-card',
      '.spotlight-card'
    ].join(', ');

    const cards = document.querySelectorAll(cardSelectors);
    cards.forEach(card => {
      // Determine spotlight color
      let spotlightColor = card.dataset.spotlightColor;
      if (!spotlightColor) {
        if (card.classList.contains('topic-card-item') || card.classList.contains('kpi-card-exact')) {
          spotlightColor = '#C8961E'; // University Gold accent for KPI and Topics
        } else if (card.classList.contains('dept-card-item')) {
          spotlightColor = '#C8961E';
        } else {
          spotlightColor = '#C8961E'; // Refined warm gold sheen
        }
      }

      attachSpotlightCard(card, {
        spotlightColor: spotlightColor,
        intensity: 0.16,
        borderGlow: 0.82,
        spotlightSize: 260,
        softness: 0.7,
        proximity: 85,
        smoothing: 0.28,
        flare: true
      });
    });
  }

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllSpotlightCards);
  } else {
    initAllSpotlightCards();
  }

  // Re-run on dynamic updates (e.g., search filtering, modals)
  window.initAllSpotlightCards = initAllSpotlightCards;
  window.attachSpotlightCard = attachSpotlightCard;
})();
