import { SettingsPage } from '../SettingsPage';

export interface ChunkingEmbeddingsPageProps {
  // filled in Task 14
}

export function ChunkingEmbeddingsPage(_props: ChunkingEmbeddingsPageProps) {
  return (
    <SettingsPage
      title="Chunking & Embeddings"
      scope="global"
      description="How source files are split for embedding."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
