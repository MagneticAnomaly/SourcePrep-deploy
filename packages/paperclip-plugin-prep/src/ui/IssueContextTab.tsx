/**
 * Issue Context Tab — structural context for Prep-pushed issues.
 * For Prep issues: shows structural complexity, hubs, consensus.
 * For other issues: offers on-demand enrichment.
 */
import { useState } from 'react';

interface IssueEntity {
  id: string;
  title: string;
  description: string;
}

function parseCodragMetadata(description: string) {
  const addressMatch = description.match(/<!-- prep-address:(.*?) -->/);
  return {
    address: addressMatch?.[1] ?? null,
    isDelta: description.includes('<!-- prep-delta:true -->'),
    isConflict: description.includes('<!-- prep-conflict:true -->'),
  };
}

function parseStructuralContext(description: string) {
  if (!description.includes('### Structural Context')) return null;

  const complexityMatch = description.match(/\*\*Complexity:\*\*\s*(\w+)/);
  const hubMatch = description.match(/\*\*Hub files:\*\*\s*(.+)/);
  const modulesMatch = description.match(/\*\*Modules spanned:\*\*\s*(.+)/);
  const blastMatch = description.match(/\*\*Blast radius:\*\*\s*(.+)/);

  return {
    complexity: complexityMatch?.[1] ?? null,
    hubFiles: hubMatch?.[1]?.split(',').map((s: string) => s.trim()) ?? [],
    modulesSpanned: modulesMatch?.[1]?.split(',').map((s: string) => s.trim()) ?? [],
    blastRadius: blastMatch?.[1] ?? null,
  };
}

export interface IssueContextTabProps {
  issue: IssueEntity | null;
  onEnrich?: (issueId: string) => Promise<void>;
}

export function IssueContextTab({ issue, onEnrich }: IssueContextTabProps) {
  const [enriching, setEnriching] = useState(false);

  if (!issue) {
    return <div className="p-4 text-sm text-gray-500">No issue selected</div>;
  }

  const meta = parseCodragMetadata(issue.description);
  const structural = parseStructuralContext(issue.description);

  if (meta.address && structural) {
    const tierColor =
      structural.complexity === 'heavyweight' ? 'text-red-400' :
      structural.complexity === 'standard' ? 'text-amber-400' :
      'text-green-400';

    return (
      <div className="p-4 space-y-3">
        <div className="text-sm font-medium">Prep Structural Context</div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-500">Complexity:</span>
            <span className={`ml-1 font-medium ${tierColor}`}>
              {structural.complexity}
            </span>
          </div>
          {structural.blastRadius && (
            <div>
              <span className="text-gray-500">Blast radius:</span>
              <span className="ml-1 text-gray-300">{structural.blastRadius}</span>
            </div>
          )}
        </div>

        {structural.hubFiles.length > 0 && (
          <div className="text-xs">
            <div className="text-gray-500 mb-0.5">Hub files:</div>
            {structural.hubFiles.map((f: string) => (
              <div key={f} className="text-gray-400 font-mono pl-2">{f}</div>
            ))}
          </div>
        )}

        {structural.modulesSpanned.length > 1 && (
          <div className="text-xs">
            <span className="text-gray-500">Cross-module:</span>
            <span className="text-gray-400 ml-1">
              {structural.modulesSpanned.join(', ')}
            </span>
          </div>
        )}

        {meta.isDelta && (
          <div className="text-[10px] text-blue-400">Structural delta notification</div>
        )}
        {meta.isConflict && (
          <div className="text-[10px] text-amber-400">Agent conflict detected</div>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      <div className="text-sm text-gray-500">No Prep context for this issue.</div>
      {onEnrich && (
        <button
          onClick={async () => {
            setEnriching(true);
            try {
              await onEnrich(issue.id);
            } finally {
              setEnriching(false);
            }
          }}
          disabled={enriching}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 disabled:opacity-50 transition-colors"
        >
          {enriching ? 'Enriching...' : 'Add Structural Analysis'}
        </button>
      )}
      <div className="text-[10px] text-gray-600">
        Runs prep:impact on files mentioned in the issue description.
      </div>
    </div>
  );
}
