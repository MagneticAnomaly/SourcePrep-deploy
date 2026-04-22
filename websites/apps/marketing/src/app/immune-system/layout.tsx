import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Immune System — Architectural Guardrails from Design Decisions',
  description: 'SourcePrep derives runtime defenses from your design decisions. Concepts become testable assertions that catch architectural violations before they ship.',
  path: '/immune-system',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
