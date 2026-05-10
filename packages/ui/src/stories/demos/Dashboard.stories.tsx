import type { Meta, StoryObj } from '@storybook/react';
import type { CSSProperties } from 'react';
import { FullDashboard as FullDashboardStory } from '../dashboard/FullDashboard.stories';

// Demos/Dashboard — the welcome story. Renders the live FullDashboard
// composition above a subtle grid pattern with a centered banner so first-
// time visitors land on something that looks like the actual product.

const meta: Meta = {
  title: 'Demos/Dashboard',
  parameters: { layout: 'fullscreen' },
};
export default meta;

const gridStyle: CSSProperties = {
  minHeight: '100vh',
  width: '100%',
  backgroundColor: 'hsl(var(--background))',
  backgroundImage:
    'linear-gradient(hsl(var(--border) / 0.35) 1px, transparent 1px),' +
    ' linear-gradient(90deg, hsl(var(--border) / 0.35) 1px, transparent 1px)',
  backgroundSize: '32px 32px',
  backgroundPosition: '-1px -1px',
};

const bannerStyle: CSSProperties = {
  maxWidth: '56rem',
  margin: '0 auto',
  padding: '2.5rem 2rem 1.5rem',
  textAlign: 'center',
  color: 'hsl(var(--text))',
};

const FullDashboardRender = FullDashboardStory.render as () => JSX.Element;

export const Welcome: StoryObj = {
  name: 'Welcome',
  render: () => (
    <div style={gridStyle}>
      <div style={bannerStyle}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.01em', margin: '0 0 0.5rem', color: 'hsl(var(--text))' }}>
          Dashboard Demo
        </h1>
        <p style={{ color: 'hsl(var(--text-muted))', lineHeight: 1.55, margin: 0 }}>
          A live render of the same dashboard you'd see in the desktop app, with mock data so you can
          interact with every panel.
        </p>
      </div>
      <FullDashboardRender />
    </div>
  ),
};
