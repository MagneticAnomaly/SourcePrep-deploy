"use client";

import { useState, useEffect, useCallback } from 'react';

type ThemeId = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n';

type HeroVariant = 'centered' | 'split' | 'neo' | 'swiss' | 'glass' | 'retro' | 'studio' | 'yale' | 'focus' | 'enterprise';

// Active themes (web = Focus, app-only = Retro x3)
// All others are LEGACY — kept for reference, not exposed in UI
const THEME_LABELS: Record<ThemeId, string> = {
  a: 'A — Default (legacy)',
  b: 'B — Split (legacy)',
  c: 'C — Warm (legacy)',
  d: 'D — Dark (legacy)',
  e: 'E — Neo-Brutalist (legacy)',
  f: 'F — Swiss Minimal (legacy)',
  g: 'G — Glass (legacy)',
  h: 'H — Retro: Synthwave',
  i: 'I — Studio (legacy)',
  j: 'J — Yale (legacy)',
  k: 'K — Focus ✓',
  l: 'L — Enterprise (legacy)',
  m: 'M — Retro: Aurora',
  n: 'N — Retro: Mirage',
};

const RETRO_THEMES: { id: ThemeId; label: string; sub: string }[] = [
  { id: 'h', label: 'Synth', sub: 'Pink/Purple' },
  { id: 'm', label: 'Aurora', sub: 'Cyan/Blue' },
  { id: 'n', label: 'Mirage', sub: 'Purple/Teal' },
];

const HERO_VARIANTS: HeroVariant[] = [
  'centered', 'split', 'neo', 'swiss', 'glass',
  'retro', 'studio', 'yale', 'focus', 'enterprise',
];

export function DevToolbar() {
  const [collapsed, setCollapsed] = useState(true);
  const [currentTheme, setCurrentTheme] = useState<ThemeId>('k');
  const [currentHero, setCurrentHero] = useState<string>('default');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    // Theme: URL param takes priority, then DOM attribute
    const urlTheme = params.get('theme');
    const attrTheme = document.documentElement.getAttribute('data-codrag-theme');
    const theme = (urlTheme && urlTheme in THEME_LABELS) ? urlTheme as ThemeId
      : (attrTheme && attrTheme in THEME_LABELS) ? attrTheme as ThemeId
      : 'a';
    document.documentElement.setAttribute('data-codrag-theme', theme);
    setCurrentTheme(theme);

    // Hero: from URL param
    const hero = params.get('hero');
    if (hero) setCurrentHero(hero);

    // Dark mode: from URL param
    const dark = params.get('dark');
    if (dark === '1') document.documentElement.classList.add('dark');
  }, []);

  // Intercept internal link clicks to preserve dev params across navigation
  useEffect(() => {
    if (process.env.NODE_ENV === 'production') return;

    const DEV_PARAMS = ['theme', 'hero', 'dark'];

    function handleClick(e: MouseEvent) {
      const anchor = (e.target as HTMLElement).closest('a');
      if (!anchor) return;

      const href = anchor.getAttribute('href');
      if (!href) return;

      // Skip external links, mailto, hash-only, and javascript:
      if (href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('#') || href.startsWith('javascript:')) return;

      // Gather current dev params
      const current = new URLSearchParams(window.location.search);
      const carry: [string, string][] = [];
      for (const key of DEV_PARAMS) {
        const val = current.get(key);
        if (val) carry.push([key, val]);
      }
      if (carry.length === 0) return;

      // Parse the href and merge params
      const [path, qs] = href.split('?');
      const target = new URLSearchParams(qs || '');
      for (const [k, v] of carry) {
        if (!target.has(k)) target.set(k, v);
      }
      const newHref = `${path}?${target.toString()}`;

      e.preventDefault();
      window.location.href = newHref;
    }

    document.addEventListener('click', handleClick, true);
    return () => document.removeEventListener('click', handleClick, true);
  }, []);

  const applyTheme = useCallback((theme: ThemeId) => {
    document.documentElement.setAttribute('data-codrag-theme', theme);
    setCurrentTheme(theme);

    const params = new URLSearchParams(window.location.search);
    params.set('theme', theme);
    window.history.replaceState({}, '', `?${params.toString()}`);
    window.dispatchEvent(new Event('codrag:dev-toolbar'));
  }, []);

  const applyHero = useCallback((hero: string) => {
    setCurrentHero(hero);

    const params = new URLSearchParams(window.location.search);
    if (hero === 'default') {
      params.delete('hero');
    } else {
      params.set('hero', hero);
    }
    window.history.replaceState({}, '', `?${params.toString()}`);
    window.dispatchEvent(new Event('codrag:dev-toolbar'));
  }, []);

  const toggleDarkMode = useCallback(() => {
    const isDark = document.documentElement.classList.toggle('dark');
    const params = new URLSearchParams(window.location.search);
    if (isDark) {
      params.set('dark', '1');
    } else {
      params.delete('dark');
    }
    window.history.replaceState({}, '', `?${params.toString()}`);
  }, []);

  if (process.env.NODE_ENV === 'production') return null;

  return (
    <div className="fixed bottom-4 right-4 z-[9999] font-mono text-xs">
      {collapsed ? (
        <button
          onClick={() => setCollapsed(false)}
          className="bg-black text-white px-3 py-2 rounded-lg shadow-xl hover:bg-gray-800 transition-colors border border-gray-700"
          title="Open Dev Toolbar"
        >
          🎨 Dev
        </button>
      ) : (
        <div className="bg-black/95 text-white rounded-xl shadow-2xl border border-gray-700 w-72 backdrop-blur-sm">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
            <span className="font-bold text-sm">🎨 Dev Toolbar</span>
            <button
              onClick={() => setCollapsed(true)}
              className="text-gray-400 hover:text-white transition-colors px-1"
            >
              ✕
            </button>
          </div>

          <div className="p-3 space-y-3 max-h-[60vh] overflow-y-auto">
            {/* Retro theme picker — h/m/n all render the RetroHero, just with different palettes */}
            <div>
              <label className="block text-gray-400 mb-1">Retro Theme</label>
              <div className="flex gap-1">
                {RETRO_THEMES.map(({ id, label, sub }) => (
                  <button
                    key={id}
                    onClick={() => applyTheme(id)}
                    className={`flex-1 px-1.5 py-1.5 rounded border transition-colors text-center ${
                      currentTheme === id
                        ? 'bg-purple-700 border-purple-500 text-white'
                        : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                    }`}
                    title={THEME_LABELS[id]}
                  >
                    <div className="text-[10px] font-bold">{label}</div>
                    <div className="text-[9px] text-gray-400">{sub}</div>
                  </button>
                ))}
                <button
                  onClick={() => applyTheme('k')}
                  className={`flex-1 px-1.5 py-1.5 rounded border transition-colors text-center ${
                    currentTheme === 'k'
                      ? 'bg-blue-700 border-blue-500 text-white'
                      : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                  }`}
                  title="K — Focus (web default)"
                >
                  <div className="text-[10px] font-bold">Focus</div>
                  <div className="text-[9px] text-gray-400">Default</div>
                </button>
              </div>
            </div>

            {/* Hero variant selector */}
            <div>
              <label className="block text-gray-400 mb-1">Hero Variant</label>
              <select
                value={currentHero}
                onChange={(e) => applyHero(e.target.value)}
                className="w-full bg-gray-800 text-white border border-gray-600 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-500"
              >
                <option value="default">Default (theme-matched)</option>
                {HERO_VARIANTS.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>

            {/* Dark mode toggle */}
            <div>
              <button
                onClick={toggleDarkMode}
                className="w-full bg-gray-800 hover:bg-gray-700 text-white border border-gray-600 rounded px-2 py-1.5 text-xs transition-colors text-left"
              >
                Toggle Dark Mode
              </button>
            </div>

            {/* Quick hero cycle */}
            <div>
              <label className="block text-gray-400 mb-1">Quick Switch</label>
              <div className="grid grid-cols-5 gap-1">
                {HERO_VARIANTS.map((v) => (
                  <button
                    key={v}
                    onClick={() => applyHero(v)}
                    className={`px-1 py-1 rounded text-[10px] border transition-colors ${
                      currentHero === v
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                    }`}
                    title={v}
                  >
                    {v.slice(0, 4)}
                  </button>
                ))}
              </div>
            </div>

            {/* Current state */}
            <div className="text-gray-500 border-t border-gray-700 pt-2 space-y-0.5">
              <div>theme: <span className="text-gray-300">{currentTheme}</span></div>
              <div>hero: <span className="text-gray-300">{currentHero}</span></div>
              <div>dark: <span className="text-gray-300">{typeof document !== 'undefined' ? String(document.documentElement.classList.contains('dark')) : '?'}</span></div>
              <div>url: <span className="text-gray-300 break-all">{typeof window !== 'undefined' ? window.location.search : ''}</span></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
