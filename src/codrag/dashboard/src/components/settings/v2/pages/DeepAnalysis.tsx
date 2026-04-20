import { SettingsPage } from '../SettingsPage';

export interface DeepAnalysisPageProps {
  // filled in Task 14
}

export function DeepAnalysisPage(_props: DeepAnalysisPageProps) {
  return (
    <SettingsPage
      title="Deep Analysis"
      scope="project"
      description="LLM-assisted enrichment and its budgets."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
