import type { Meta, StoryObj } from '@storybook/react';
import { FullDashboard as FullDashboardStory } from '../dashboard/FullDashboard.stories';

// Demos/Dashboard — the welcome story. Renders the live FullDashboard
// composition (AppShell + Sidebar + grid) directly, full-bleed.

const meta: Meta = {
  title: 'Demos/Dashboard',
  parameters: { layout: 'fullscreen' },
};
export default meta;

const FullDashboardRender = FullDashboardStory.render as () => JSX.Element;

export const Welcome: StoryObj = {
  name: 'SourcePrep Demo',
  render: () => <FullDashboardRender />,
};
