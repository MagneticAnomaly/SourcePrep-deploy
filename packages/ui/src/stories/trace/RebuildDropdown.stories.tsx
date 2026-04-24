import type { Meta, StoryObj } from '@storybook/react';
import { RebuildDropdown } from '../../components/trace/RebuildDropdown';
import type { RebuildScope } from '../../types';

const meta: Meta<typeof RebuildDropdown> = {
  title: 'Dashboard/Widgets/Trace/RebuildDropdown',
  component: RebuildDropdown,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    onRebuild: { action: 'onRebuild' },
  },
};

export default meta;
type Story = StoryObj<typeof RebuildDropdown>;

// ── Stories ───────────────────────────────────────────────────

/**
 * Default state — primary "Rebuild" button triggers a full (all) rebuild;
 * caret opens the three-item dropdown. Click a menu item in the canvas to
 * see the onRebuild action logged in the Actions panel.
 */
export const Default: Story = {
  args: {
    onRebuild: (scope: RebuildScope) => {
      console.log('onRebuild:', scope);
    },
    disabled: false,
  },
};

/**
 * Disabled state — both the primary button and the caret are non-interactive.
 * Used while a rebuild is already in progress.
 */
export const Disabled: Story = {
  args: {
    onRebuild: (scope: RebuildScope) => {
      console.log('onRebuild:', scope);
    },
    disabled: true,
  },
};

/**
 * With custom className — demonstrates that the wrapper accepts an extra
 * Tailwind class for embedding inside toolbars with specific margin/layout.
 */
export const WithClassName: Story = {
  args: {
    onRebuild: (scope: RebuildScope) => {
      console.log('onRebuild:', scope);
    },
    disabled: false,
    className: 'ml-4',
  },
};
