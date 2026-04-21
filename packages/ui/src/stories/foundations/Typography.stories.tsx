import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta = {
  title: 'Foundations/Tokens/Typography',
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;

type Story = StoryObj;

function Sample({
  label,
  className,
  text,
}: {
  label: string;
  className: string;
  text: string;
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-mono text-text-muted">{label}</div>
      <div className={`text-text ${className}`}>{text}</div>
    </div>
  );
}

export const Scale: Story = {
  render: () => (
    <div className="space-y-6">
      <Sample
        label="Heading XL — --text-4xl"
        className="text-[length:var(--text-4xl)] leading-[var(--leading-tight)] font-bold"
        text="RunPrep Design System"
      />
      <Sample
        label="Heading — --text-2xl"
        className="text-[length:var(--text-2xl)] leading-[var(--leading-snug)] font-semibold"
        text="Trust-first developer tooling"
      />
      <Sample
        label="Body — --text-base"
        className="text-[length:var(--text-base)] leading-[var(--leading-normal)]"
        text="RunPrep helps you build, search, and assemble grounded context from your codebase."
      />
      <Sample
        label="Small — --text-sm"
        className="text-[length:var(--text-sm)] leading-[var(--leading-normal)] text-text-muted"
        text="Use semantic tokens for consistent styling across themes."
      />

      <div className="space-y-2">
        <div className="text-xs font-mono text-text-muted">Monospace — --font-mono</div>
        <pre className="rounded-md border border-border bg-surface-raised p-3 text-[length:var(--text-sm)] leading-[var(--leading-normal)] font-mono text-text overflow-x-auto">
{`def build_index(repo_root: str) -> None:
    """Build the code index."""
    ...`}
        </pre>
      </div>
    </div>
  ),
};
