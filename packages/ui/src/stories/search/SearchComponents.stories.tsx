import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Table, TableBody } from '@tremor/react';
import { SearchInput } from '../../components/search/SearchInput';
import { SearchResultRow } from '../../components/search/SearchResultRow';
import { ChunkViewer } from '../../components/search/ChunkViewer';
import type { SearchResult, CodeChunk } from '../../types';

// SearchInput Stories
const searchInputMeta: Meta<typeof SearchInput> = {
  title: 'Dashboard/Widgets/Search/Components',
  component: SearchInput,
  tags: ['autodocs'],
};

export default searchInputMeta;
type SearchInputStory = StoryObj<typeof SearchInput>;

export const Default: SearchInputStory = {
  render: () => {
    const [value, setValue] = useState('');
    return (
      <SearchInput
        value={value}
        onChange={setValue}
        onSubmit={() => console.log('Search:', value)}
      />
    );
  },
};

export const Loading: SearchInputStory = {
  args: {
    value: 'authentication handler',
    onChange: () => {},
    loading: true,
  },
};

export const CustomPlaceholder: SearchInputStory = {
  render: () => {
    const [value, setValue] = useState('');
    return (
      <SearchInput
        value={value}
        onChange={setValue}
        placeholder="Find functions, classes, or documentation..."
      />
    );
  },
};

// SearchResultRow Stories
const mockResults: SearchResult[] = [
  {
    chunk_id: 'chunk-001',
    source_path: 'src/prep/core/indexer.py',
    span: { start_line: 45, end_line: 78 },
    preview: 'def build_index(project_path: str, config: IndexConfig) -> Index: """Build a semantic index for the given project...',
    score: 0.92,
  },
  {
    chunk_id: 'chunk-002',
    source_path: 'src/prep/api/routes.py',
    span: { start_line: 120, end_line: 145 },
    preview: '@app.post("/projects/{project_id}/search") async def search_project(project_id: str, request: SearchRequest)...',
    score: 0.85,
  },
  {
    chunk_id: 'chunk-003',
    source_path: 'docs/API.md',
    span: { start_line: 1, end_line: 30 },
    preview: '# Prep API Reference\n\nThis document describes the REST API endpoints for Prep...',
    score: 0.78,
  },
];

export const SearchResults: SearchInputStory = {
  render: () => (
    <div className="space-y-4">
      <SearchInput value="index build" onChange={() => {}} />
      <Table>
        <TableBody>
          {mockResults.map((result) => (
            <SearchResultRow
              key={result.chunk_id}
              result={result}
              showScore
              onClick={() => console.log('Selected:', result.chunk_id)}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  ),
};

export const SearchResultWithSelection: SearchInputStory = {
  render: () => (
    <Table>
      <TableBody>
        <SearchResultRow result={mockResults[0]} selected showScore />
        <SearchResultRow result={mockResults[1]} showScore />
        <SearchResultRow result={mockResults[2]} showScore />
      </TableBody>
    </Table>
  ),
};

// ChunkViewer Stories
const mockChunk: CodeChunk = {
  id: 'chunk-001',
  source_path: 'src/prep/core/indexer.py',
  span: { start_line: 45, end_line: 58 },
  language: 'python',
  content: `def build_index(project_path: str, config: IndexConfig) -> Index:
    """Build a semantic index for the given project.
    
    Args:
        project_path: Path to the project root
        config: Index configuration
        
    Returns:
        The built Index object
    """
    scanner = FileScanner(project_path, config)
    files = scanner.scan()
    chunks = chunker.chunk_files(files)
    embeddings = embed_chunks(chunks, config.model)
    return Index(chunks, embeddings)`,
};

export const ChunkDetail: SearchInputStory = {
  render: () => (
    <ChunkViewer
      chunk={mockChunk}
      onClose={() => console.log('Close viewer')}
    />
  ),
};
