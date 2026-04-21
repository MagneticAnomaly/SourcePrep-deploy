/**
 * GenerateWizard — 3-mode role generation interface.
 *
 * Lets users pick list/auto/hybrid mode, enter role names (for list/hybrid),
 * and trigger generation.
 */
import { useState } from 'react';

export interface GenerateWizardProps {
  readinessScore: number;
  readyForList: boolean;
  readyForAuto: boolean;
  onGenerate: (mode: string, roleNames: string[]) => void;
  generating?: boolean;
  className?: string;
}

export function GenerateWizard({
  readinessScore,
  readyForList,
  readyForAuto,
  onGenerate,
  generating = false,
  className = '',
}: GenerateWizardProps) {
  const [mode, setMode] = useState<'list' | 'auto' | 'hybrid'>('auto');
  const [roleInput, setRoleInput] = useState('');

  const handleGenerate = () => {
    const names = mode === 'auto'
      ? []
      : roleInput.split(',').map(s => s.trim()).filter(Boolean);

    if (mode === 'list' && names.length === 0) return;
    onGenerate(mode, names);
  };

  const canGenerate =
    (mode === 'auto' && readyForAuto) ||
    (mode === 'list' && readyForList) ||
    (mode === 'hybrid' && readyForAuto);

  return (
    <div className={`rounded-lg border border-border p-4 space-y-4 ${className}`}>
      <h3 className="font-semibold text-sm">Generate Agent Roles</h3>

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>Readiness: </span>
        <span className={readinessScore >= 0.7 ? 'text-green-500' : readinessScore >= 0.4 ? 'text-yellow-500' : 'text-red-500'}>
          {(readinessScore * 100).toFixed(0)}%
        </span>
      </div>

      {/* Mode selector */}
      <div className="flex gap-2">
        {(['auto', 'list', 'hybrid'] as const).map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            disabled={m === 'auto' && !readyForAuto || m === 'hybrid' && !readyForAuto || m === 'list' && !readyForList}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              mode === m
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {m === 'auto' ? 'Auto-Infer' : m === 'list' ? 'Specify Roles' : 'Hybrid'}
          </button>
        ))}
      </div>

      {/* Mode description */}
      <p className="text-xs text-muted-foreground">
        {mode === 'auto' && 'LLM analyzes your codebase and infers the optimal team structure.'}
        {mode === 'list' && 'You specify role names. Prep generates instructions grounded in your code.'}
        {mode === 'hybrid' && 'LLM infers roles, but your specified roles are guaranteed to be included.'}
      </p>

      {/* Role name input (for list/hybrid modes) */}
      {(mode === 'list' || mode === 'hybrid') && (
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">
            Role names (comma-separated)
          </label>
          <input
            type="text"
            value={roleInput}
            onChange={e => setRoleInput(e.target.value)}
            placeholder="Backend Developer, API Engineer, DevOps Lead"
            className="w-full px-3 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      )}

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={!canGenerate || generating}
        className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {generating ? 'Generating...' : `Generate (${mode} mode)`}
      </button>
    </div>
  );
}
