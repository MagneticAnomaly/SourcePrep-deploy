import type { Meta, StoryObj } from '@storybook/react';

import { InitExcludeReviewModal } from './InitExcludeReviewModal';

const meta: Meta<typeof InitExcludeReviewModal> = {
  title: 'Project/InitExcludeReviewModal',
  component: InitExcludeReviewModal,
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj<typeof InitExcludeReviewModal>;

export const SkyPathLike: Story = {
  args: {
    open: true,
    proposed: [
      {
        rel_path: 'cesium-native',
        size_bytes: 1_700_000_000,
        file_count: 12_304,
        reason: 'Large directory, no classification signal',
        tier: 'propose',
        in_gitignore: false,
        is_git_repo: true,
      },
      {
        rel_path: 'huge-blob',
        size_bytes: 600_000_000,
        file_count: 3_200,
        reason: 'Large directory, no classification signal',
        tier: 'propose',
        in_gitignore: false,
        is_git_repo: false,
      },
    ],
    autoExcludedSummary: [
      {
        rel_path: 'Pods',
        size_bytes: 0,
        file_count: 0,
        reason: 'Canonical package-manager install dir',
        tier: 'auto',
        in_gitignore: false,
        is_git_repo: false,
      },
      {
        rel_path: 'build',
        size_bytes: 0,
        file_count: 0,
        reason: 'CMake/build output (CMakeCache.txt present)',
        tier: 'auto',
        in_gitignore: false,
        is_git_repo: false,
      },
      {
        rel_path: 'vcpkg',
        size_bytes: 0,
        file_count: 0,
        reason: 'Listed in .gitmodules',
        tier: 'auto',
        in_gitignore: false,
        is_git_repo: true,
      },
    ],
    onClose: () => alert('Close (X / Esc / backdrop)'),
    onApply: (s: string[], d: string[]) =>
      alert(`Apply: selected=${s.length}, dismissed=${d.length}`),
    onSkip: () => alert('Skip Excludes & Initialize'),
  },
};

export const NoProposals: Story = {
  args: {
    open: true,
    proposed: [],
    autoExcludedSummary: [
      {
        rel_path: 'node_modules',
        size_bytes: 0,
        file_count: 0,
        reason: 'Canonical package-manager install dir',
        tier: 'auto',
        in_gitignore: true,
        is_git_repo: false,
      },
    ],
    onClose: () => {},
    onApply: () => {},
    onSkip: () => {},
  },
};

export const Closed: Story = {
  args: {
    open: false,
    proposed: [],
    autoExcludedSummary: [],
    onClose: () => {},
    onApply: () => {},
    onSkip: () => {},
  },
};
