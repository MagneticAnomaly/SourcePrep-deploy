import type { Meta, StoryObj } from '@storybook/react';

import { GitignoreHygieneModal } from './GitignoreHygieneModal';

const meta: Meta<typeof GitignoreHygieneModal> = {
  title: 'Project/GitignoreHygieneModal',
  component: GitignoreHygieneModal,
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj<typeof GitignoreHygieneModal>;

export const TwoGaps: Story = {
  args: {
    open: true,
    gaps: [
      {
        rel_path: 'node_modules',
        size_bytes: 450_000_000,
        file_count: 21_400,
        reason: 'Canonical package-manager install dir',
      },
      {
        rel_path: 'vcpkg_installed',
        size_bytes: 1_200_000_000,
        file_count: 8_900,
        reason: 'Canonical package-manager install dir',
      },
    ],
    onCancel: () => alert('Cancel Initialize'),
    onContinue: () => alert('Continue Anyway'),
  },
};

export const OneGap: Story = {
  args: {
    open: true,
    gaps: [
      {
        rel_path: 'build',
        size_bytes: 497_000_000,
        file_count: 1_200,
        reason: 'CMake/build output (CMakeCache.txt present)',
      },
    ],
    onCancel: () => {},
    onContinue: () => {},
  },
};

export const Closed: Story = {
  args: {
    open: false,
    gaps: [],
    onCancel: () => {},
    onContinue: () => {},
  },
};
