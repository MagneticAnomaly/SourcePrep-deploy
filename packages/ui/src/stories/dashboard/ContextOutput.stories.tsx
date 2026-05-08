import type { Meta, StoryObj } from '@storybook/react';
import { ContextViewer } from '../../components/context/ContextViewer';
import type { ContextChunk } from '../../components/context/ContextViewer';

const meta: Meta<typeof ContextViewer> = {
  title: 'Dashboard/Search/ContextOutput',
  component: ContextViewer,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof ContextViewer>;

const mockContext = `--- Source: src/prep/core/indexer.py:45-78 ---
def build_index(project_path: str, config: IndexConfig) -> Index:
    """Build a semantic index for the given project."""
    scanner = FileScanner(project_path, config)
    files = scanner.scan()
    chunks = chunker.chunk_files(files)
    embeddings = embed_chunks(chunks, config.model)
    return Index(chunks, embeddings)

--- Source: src/prep/api/routes.py:120-145 ---
@app.post("/projects/{project_id}/search")
async def search_project(project_id: str, request: SearchRequest):
    """Semantic search in project."""
    project = registry.get(project_id)
    results = project.index.search(request.query, k=request.k)
    return {"success": True, "data": {"results": results}}`;

const mockChunks: ContextChunk[] = [
  {
    chunk_id: 'chunk-001',
    source_path: 'src/prep/core/indexer.py',
    span: { start_line: 45, end_line: 78 },
    score: 0.92,
    truncated: false,
  },
  {
    chunk_id: 'chunk-002',
    source_path: 'src/prep/api/routes.py',
    span: { start_line: 120, end_line: 145 },
    score: 0.85,
    truncated: false,
  },
];

export const Default: Story = {
  render: () => (
    <ContextViewer
      context={mockContext}
      chunks={mockChunks}
      totalChars={1250}
      estimatedTokens={312}
      showSources
      showScores
    />
  ),
};

export const Minimal: Story = {
  render: () => (
    <ContextViewer
      context={mockContext}
      totalChars={1250}
    />
  ),
};

export const WithManySources: Story = {
  render: () => (
    <ContextViewer
      context={mockContext}
      chunks={[
        ...mockChunks,
        { chunk_id: 'chunk-003', source_path: 'docs/API.md', span: { start_line: 1, end_line: 30 }, score: 0.78 },
        { chunk_id: 'chunk-004', source_path: 'tests/test_indexer.py', span: { start_line: 50, end_line: 85 }, score: 0.72 },
        { chunk_id: 'chunk-005', source_path: 'src/prep/cli.py', span: { start_line: 10, end_line: 45 }, score: 0.68 },
      ]}
      totalChars={4500}
      estimatedTokens={1125}
      showSources
    />
  ),
};
