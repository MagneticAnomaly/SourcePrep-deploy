import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { SearchPanel } from '../../components/search/SearchPanel';
import { ContextOptionsPanel } from '../../components/search/ContextOptionsPanel';

const meta: Meta<typeof SearchPanel> = {
  title: 'Dashboard/Search/SearchPanel',
  component: SearchPanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof SearchPanel>;

export const Default: Story = {
  render: () => {
    const [query, setQuery] = useState('');
    const [k, setK] = useState(8);
    const [minScore, setMinScore] = useState(0.15);
    const [loading, setLoading] = useState(false);

    const handleSearch = () => {
      setLoading(true);
      setTimeout(() => setLoading(false), 1500);
    };

    return (
      <SearchPanel
        query={query}
        onQueryChange={setQuery}
        k={k}
        onKChange={setK}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        onSearch={handleSearch}
        loading={loading}
      />
    );
  },
};

export const WithQuery: Story = {
  render: () => {
    const [query, setQuery] = useState('how does the API client handle errors');
    const [k, setK] = useState(10);
    const [minScore, setMinScore] = useState(0.2);

    return (
      <SearchPanel
        query={query}
        onQueryChange={setQuery}
        k={k}
        onKChange={setK}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        onSearch={() => console.log('Search:', query)}
      />
    );
  },
};

export const Loading: Story = {
  render: () => {
    const [query, setQuery] = useState('authentication flow');
    const [k, setK] = useState(8);
    const [minScore, setMinScore] = useState(0.15);

    return (
      <SearchPanel
        query={query}
        onQueryChange={setQuery}
        k={k}
        onKChange={setK}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        onSearch={() => {}}
        loading={true}
      />
    );
  },
};

// ContextOptionsPanel Stories
export const ContextOptions: StoryObj<typeof ContextOptionsPanel> = {
  render: () => {
    const [k, setK] = useState(5);
    const [maxChars, setMaxChars] = useState(6000);
    const [includeSources, setIncludeSources] = useState(true);
    const [includeScores, setIncludeScores] = useState(false);
    const [structured, setStructured] = useState(false);

    return (
      <ContextOptionsPanel
        k={k}
        onKChange={setK}
        maxChars={maxChars}
        onMaxCharsChange={setMaxChars}
        includeSources={includeSources}
        onIncludeSourcesChange={setIncludeSources}
        includeScores={includeScores}
        onIncludeScoresChange={setIncludeScores}
        structured={structured}
        onStructuredChange={setStructured}
        onGetContext={() => console.log('Get context')}
        onCopyContext={() => console.log('Copy context')}
        hasContext={false}
      />
    );
  },
};

export const ContextOptionsWithContext: StoryObj<typeof ContextOptionsPanel> = {
  render: () => {
    const [k, setK] = useState(5);
    const [maxChars, setMaxChars] = useState(6000);
    const [includeSources, setIncludeSources] = useState(true);
    const [includeScores, setIncludeScores] = useState(true);
    const [structured, setStructured] = useState(true);

    return (
      <ContextOptionsPanel
        k={k}
        onKChange={setK}
        maxChars={maxChars}
        onMaxCharsChange={setMaxChars}
        includeSources={includeSources}
        onIncludeSourcesChange={setIncludeSources}
        includeScores={includeScores}
        onIncludeScoresChange={setIncludeScores}
        structured={structured}
        onStructuredChange={setStructured}
        onGetContext={() => console.log('Get context')}
        onCopyContext={() => console.log('Copy context')}
        hasContext={true}
      />
    );
  },
};

// Combined Demo
export const FullSearchDemo: Story = {
  render: () => {
    const [query, setQuery] = useState('');
    const [searchK, setSearchK] = useState(8);
    const [minScore, setMinScore] = useState(0.15);
    const [loading, setLoading] = useState(false);
    
    const [contextK, setContextK] = useState(5);
    const [maxChars, setMaxChars] = useState(6000);
    const [includeSources, setIncludeSources] = useState(true);
    const [includeScores, setIncludeScores] = useState(false);
    const [structured, setStructured] = useState(false);
    const [hasContext, setHasContext] = useState(false);

    const handleSearch = () => {
      setLoading(true);
      setTimeout(() => setLoading(false), 1500);
    };

    const handleGetContext = () => {
      setHasContext(true);
    };

    return (
      <div className="space-y-4 max-w-4xl">
        <SearchPanel
          query={query}
          onQueryChange={setQuery}
          k={searchK}
          onKChange={setSearchK}
          minScore={minScore}
          onMinScoreChange={setMinScore}
          onSearch={handleSearch}
          loading={loading}
        />
        <ContextOptionsPanel
          k={contextK}
          onKChange={setContextK}
          maxChars={maxChars}
          onMaxCharsChange={setMaxChars}
          includeSources={includeSources}
          onIncludeSourcesChange={setIncludeSources}
          includeScores={includeScores}
          onIncludeScoresChange={setIncludeScores}
          structured={structured}
          onStructuredChange={setStructured}
          onGetContext={handleGetContext}
          onCopyContext={() => console.log('Copy')}
          hasContext={hasContext}
          disabled={!query.trim()}
        />
      </div>
    );
  },
};
