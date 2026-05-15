import type { Meta, StoryObj } from '@storybook/react';
import { EmptyState } from '../../components/patterns/EmptyState';
import { LoadingState } from '../../components/patterns/LoadingState';
import { ErrorState } from '../../components/patterns/ErrorState';

// EmptyState Stories
const emptyStateMeta: Meta<typeof EmptyState> = {
  title: 'Patterns/StatePatterns',
  component: EmptyState,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default emptyStateMeta;
type StateStory = StoryObj<typeof EmptyState>;

export const EmptyNoProjects: StateStory = {
  render: () => (
    <EmptyState
      title="No projects yet"
      description="Add your first project to get started with SourcePrep. Projects are indexed locally; nothing is uploaded."
      action={{
        label: 'Add Project',
        onClick: () => console.log('Add project'),
      }}
    />
  ),
};

export const EmptyNoSearchResults: StateStory = {
  render: () => (
    <EmptyState
      title="No results found"
      description="Try adjusting your search terms or rebuilding the index if files have changed."
    />
  ),
};

export const EmptyNoIndex: StateStory = {
  render: () => (
    <EmptyState
      title="Knowledge not built yet"
      description="Build your codebase knowledge to enable semantic search."
      action={{
        label: 'Build Knowledge',
        onClick: () => console.log('Build knowledge'),
      }}
    />
  ),
};

// LoadingState Stories
export const LoadingCard: StateStory = {
  render: () => <LoadingState message="Loading project..." variant="card" />,
};

export const LoadingInline: StateStory = {
  render: () => <LoadingState message="Searching..." variant="inline" />,
};

export const LoadingFullscreen: StateStory = {
  render: () => (
    <div className="relative h-64 border rounded">
      <LoadingState message="Building index..." variant="fullscreen" />
    </div>
  ),
};

// ErrorState Stories
export const ErrorOllamaUnavailable: StateStory = {
  render: () => (
    <ErrorState
      title="Connection Failed"
      error={{
        code: 'OLLAMA_UNAVAILABLE',
        message: 'Could not connect to Ollama at localhost:11434',
        hint: 'Make sure Ollama is running. Try: ollama serve',
      }}
      onRetry={() => console.log('Retry')}
    />
  ),
};

export const ErrorBuildFailed: StateStory = {
  render: () => (
    <ErrorState
      title="Build Failed"
      error={{
        code: 'BUILD_FAILED',
        message: 'Index build failed during embedding phase',
        hint: 'Check that Ollama has the required model installed.',
      }}
      onRetry={() => console.log('Retry')}
      onDismiss={() => console.log('Dismiss')}
    />
  ),
};

export const ErrorPermissionDenied: StateStory = {
  render: () => (
    <ErrorState
      error={{
        code: 'PERMISSION_DENIED',
        message: 'Cannot read directory: /private/var/root',
        hint: 'Check file permissions or choose a different project path.',
      }}
      onDismiss={() => console.log('Dismiss')}
    />
  ),
};

export const ErrorProjectNotFound: StateStory = {
  render: () => (
    <ErrorState
      error={{
        code: 'PROJECT_NOT_FOUND',
        message: "Project with ID 'abc123' not found",
        hint: 'The project may have been removed. Select another project from the sidebar.',
      }}
    />
  ),
};

// Combined trust-console states demo
export const TrustConsoleStates: StateStory = {
  render: () => (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Trust Console State Patterns</h2>
      <p className="text-sm text-gray-500">
        The dashboard should consistently render one of: Loading, Empty, Ready, or Error.
        Each state should be clear and actionable.
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-medium mb-2">Loading</h3>
          <LoadingState message="Checking index status..." variant="card" />
        </div>
        
        <div>
          <h3 className="text-sm font-medium mb-2">Empty</h3>
          <EmptyState
            title="No results"
            description="Try a different query"
          />
        </div>
        
        <div className="md:col-span-2">
          <h3 className="text-sm font-medium mb-2">Error (Actionable)</h3>
          <ErrorState
            error={{
              code: 'INDEX_NOT_BUILT',
              message: 'No index exists for this project',
              hint: 'Build the index to enable search.',
            }}
            onRetry={() => {}}
          />
        </div>
      </div>
    </div>
  ),
};
