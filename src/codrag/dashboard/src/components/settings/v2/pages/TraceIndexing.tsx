import { SettingsPage } from '../SettingsPage';

export interface TraceIndexingPageProps {
  // filled in Task 14
}

export function TraceIndexingPage(_props: TraceIndexingPageProps) {
  return (
    <SettingsPage
      title="Trace & Indexing"
      scope="project"
      description="How the trace graph is built and refreshed."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
