"use client";

import {
  CenteredHero,
  NeoBrutalistHero,
  SwissHero,
  GlassHero,
  RetroHero,
  SplitHero,
  StudioHero,
  YaleHero,
  FocusHero,
  EnterpriseHero,
} from './heroes';

export interface MarketingHeroProps {
  isBetaMode?: boolean;
  variant?: 'centered' | 'split' | 'neo' | 'swiss' | 'glass' | 'retro' | 'studio' | 'yale' | 'focus' | 'enterprise';
}

export function MarketingHero({ variant = 'centered', isBetaMode = true }: MarketingHeroProps) {
  switch (variant) {
    case 'split': return <SplitHero isBetaMode={isBetaMode} />;
    case 'neo': return <NeoBrutalistHero isBetaMode={isBetaMode} />;
    case 'swiss': return <SwissHero isBetaMode={isBetaMode} />;
    case 'glass': return <GlassHero isBetaMode={isBetaMode} />;
    case 'retro': return <RetroHero isBetaMode={isBetaMode} />;
    case 'studio': return <StudioHero isBetaMode={isBetaMode} />;
    case 'yale': return <YaleHero isBetaMode={isBetaMode} />;
    case 'focus': return <FocusHero isBetaMode={isBetaMode} />;
    case 'enterprise': return <EnterpriseHero isBetaMode={isBetaMode} />;
    default: return <CenteredHero isBetaMode={isBetaMode} />;
  }
}

