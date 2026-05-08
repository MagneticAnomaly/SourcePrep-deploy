import type { Meta, StoryObj } from '@storybook/react';
import { useMemo, useState } from 'react';
import { ProjectSettingsPanel } from '../../components/project/ProjectSettingsPanel';
import type { ProjectConfig } from '../../types';

const meta: Meta<typeof ProjectSettingsPanel> = {
  title: 'Dashboard/Project/ProjectSettingsPanel',
  component: ProjectSettingsPanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;

type Story = StoryObj<typeof ProjectSettingsPanel>;

export const Default: Story = {
  render: () => {
    const initial = useMemo<ProjectConfig>(
      () => ({
        include_globs: ['**/*.{py,ts,tsx,md}'],
        exclude_globs: ['**/node_modules/**', '**/.git/**'],
        max_file_bytes: 200_000,
        use_gitignore: true,
        trace: { enabled: true },
        auto_rebuild: { enabled: false, debounce_ms: 5000 },
      }),
      []
    );

    const [config, setConfig] = useState<ProjectConfig>(initial);
    const [isDirty, setIsDirty] = useState(false);

    return (
      <ProjectSettingsPanel
        config={config}
        onChange={(c) => {
          setConfig(c);
          setIsDirty(true);
        }}
        onSave={() => {
          setIsDirty(false);
          console.log('Save', config);
        }}
        isDirty={isDirty}
      />
    );
  },
};

export const AutoRebuildEnabled: Story = {
  render: () => {
    const initial = useMemo<ProjectConfig>(
      () => ({
        include_globs: ['**/*.py'],
        exclude_globs: ['**/node_modules/**'],
        max_file_bytes: 500_000,
        use_gitignore: true,
        trace: { enabled: false },
        auto_rebuild: { enabled: true, debounce_ms: 3000 },
      }),
      []
    );

    const [config, setConfig] = useState<ProjectConfig>(initial);
    const [isDirty, setIsDirty] = useState(false);

    return (
      <ProjectSettingsPanel
        config={config}
        onChange={(c) => {
          setConfig(c);
          setIsDirty(true);
        }}
        onSave={() => {
          setIsDirty(false);
          console.log('Save', config);
        }}
        isDirty={isDirty}
      />
    );
  },
};
