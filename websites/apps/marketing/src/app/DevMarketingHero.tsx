"use client";

import { useEffect, useState } from 'react';
import { MarketingHero, type MarketingHeroProps } from '@prep/ui';

type ThemeId = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n';

type HeroVariant = NonNullable<MarketingHeroProps['variant']>;

type HeroSelection = 'default' | HeroVariant;

const themeIds = new Set<ThemeId>(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n']);

const heroSelections = new Set<HeroSelection>([
  'default',
  'centered',
  'split',
  'neo',
  'swiss',
  'glass',
  'retro',
  'studio',
  'yale',
  'focus',
  'enterprise',
]);

function isThemeId(value: string | null): value is ThemeId {
  return value !== null && themeIds.has(value as ThemeId);
}

function isHeroSelection(value: string | null): value is HeroSelection {
  return value !== null && heroSelections.has(value as HeroSelection);
}

function getThemeDefaultHeroVariant(theme: ThemeId): HeroVariant {
  if (theme === 'e') return 'neo';
  if (theme === 'f') return 'swiss';
  if (theme === 'g') return 'glass';
  if (theme === 'h') return 'retro';
  if (theme === 'm') return 'yale';
  if (theme === 'n') return 'retro';
  if (theme === 'i') return 'studio';
  if (theme === 'j') return 'yale';
  if (theme === 'k') return 'yale';
  if (theme === 'l') return 'enterprise';
  if (theme === 'a' || theme === 'd') return 'centered';
  if (theme === 'b' || theme === 'c') return 'split';
  return 'centered';
}

function resolveHeroVariantFromLocation(fallbackTheme: ThemeId): HeroVariant {
  const params = new URLSearchParams(window.location.search);

  const queryTheme = params.get('theme');
  const attrTheme = document.documentElement.getAttribute('data-codrag-theme');

  const theme = isThemeId(queryTheme) ? queryTheme : isThemeId(attrTheme) ? attrTheme : fallbackTheme;

  const queryHero = params.get('hero');

  if (isHeroSelection(queryHero) && queryHero !== 'default') {
    return queryHero;
  }

  return getThemeDefaultHeroVariant(theme);
}

export interface DevMarketingHeroProps {
  fallbackTheme?: ThemeId;
}

export function DevMarketingHero({ fallbackTheme = 'm' }: DevMarketingHeroProps) {
  const showDevToolbar = process.env.NODE_ENV !== 'production';

  const [variant, setVariant] = useState<HeroVariant>(() => getThemeDefaultHeroVariant(fallbackTheme));

  useEffect(() => {
    if (!showDevToolbar) return;

    const updateVariant = () => {
      setVariant(resolveHeroVariantFromLocation(fallbackTheme));
    };

    updateVariant();

    window.addEventListener('codrag:dev-toolbar', updateVariant);
    window.addEventListener('popstate', updateVariant);

    return () => {
      window.removeEventListener('codrag:dev-toolbar', updateVariant);
      window.removeEventListener('popstate', updateVariant);
    };
  }, [fallbackTheme, showDevToolbar]);

  return <MarketingHero variant={variant} />;
}
