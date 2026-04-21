import type { Meta, StoryObj } from '@storybook/react';
import { AppShell } from '../../components/navigation/AppShell';
import { Sidebar } from '../../components/navigation/Sidebar';
import { ProjectList } from '../../components/navigation/ProjectList';
import { ProjectTabs } from '../../components/navigation/ProjectTabs';
import { EmptyState } from '../../components/patterns/EmptyState';
import type { ProjectSummary } from '../../types';

const meta: Meta<typeof AppShell> = {
  title: 'Application/Navigation/AppShell',
  component: AppShell,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
};

export default meta;
type Story = StoryObj<typeof AppShell>;

const mockProjects: ProjectSummary[] = [
  { id: '1', name: 'prep', path: '/Users/dev/prep', mode: 'standalone', status: 'fresh', chunk_count: 1234 },
  { id: '2', name: 'website', path: '/Users/dev/website', mode: 'standalone', status: 'stale' },
  { id: '3', name: 'api-server', path: '/Users/dev/api', mode: 'standalone', status: 'building' },
];

const mockTabs = [
  { id: '1', name: 'prep', path: '/Users/dev/prep' },
  { id: '2', name: 'website', path: '/Users/dev/website' },
];

export const Default: Story = {
  render: () => (
    <AppShell
      sidebar={
        <Sidebar>
          <ProjectList
            projects={mockProjects}
            selectedProjectId="1"
            onProjectSelect={() => {}}
            onAddProject={() => {}}
          />
        </Sidebar>
      }
      tabs={
        <ProjectTabs
          tabs={mockTabs}
          activeTabId="1"
          onTabSelect={() => {}}
          onTabClose={() => {}}
        />
      }
    >
      <div className="p-4">
        <h1 className="text-2xl font-bold">Main Content Area</h1>
        <p className="mt-2 text-gray-500">This is where the project-specific content goes.</p>
      </div>
    </AppShell>
  ),
};

export const EmptyProjects: Story = {
  render: () => (
    <AppShell
      sidebar={
        <Sidebar>
          <ProjectList
            projects={[]}
            onProjectSelect={() => {}}
            onAddProject={() => {}}
          />
        </Sidebar>
      }
    >
      <EmptyState
        title="No projects yet"
        description="Add your first project to get started with RunPrep. Projects are indexed locally; nothing is uploaded."
        action={{
          label: 'Add Project',
          onClick: () => {},
        }}
      />
    </AppShell>
  ),
};

export const CollapsedSidebar: Story = {
  render: () => (
    <AppShell
      sidebar={
        <Sidebar collapsed onCollapseToggle={() => {}}>
          <div className="p-2 text-center text-gray-400">...</div>
        </Sidebar>
      }
      tabs={
        <ProjectTabs
          tabs={mockTabs}
          activeTabId="1"
          onTabSelect={() => {}}
          onTabClose={() => {}}
        />
      }
    >
      <div className="p-4">
        <h1 className="text-2xl font-bold">Main Content</h1>
      </div>
    </AppShell>
  ),
};
