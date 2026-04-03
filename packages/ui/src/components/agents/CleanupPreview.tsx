/**
 * CleanupPreview — Shows custodian scan results and lets users trigger scans.
 */

export interface CleanupCandidate {
  file_path: string;
  finding_id: string;
  dependent_count: number;
  classification: string;
  reason: string;
}

export interface CleanupPreviewProps {
  candidates: CleanupCandidate[];
  archiveCount: number;
  onScan: (dryRun: boolean) => void;
  scanning?: boolean;
  className?: string;
}

export function CleanupPreview({
  candidates,
  archiveCount,
  onScan,
  scanning = false,
  className = '',
}: CleanupPreviewProps) {
  return (
    <div className={`rounded-lg border border-border p-4 space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Digital Custodian</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onScan(true)}
            disabled={scanning}
            className="px-3 py-1 text-xs rounded-md bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 transition-colors"
          >
            {scanning ? 'Scanning...' : 'Dry Run'}
          </button>
          <button
            onClick={() => onScan(false)}
            disabled={scanning}
            className="px-3 py-1 text-xs rounded-md bg-red-500/10 text-red-600 hover:bg-red-500/20 disabled:opacity-40 transition-colors"
          >
            Live Run
          </button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Detects dead code, verifies safety via LLM, and plans cleanup with archive-first strategy.
        Dry run is the default — no files are modified.
      </p>

      <div className="flex gap-4 text-xs text-muted-foreground">
        <span>Archived items: <span className="font-medium text-foreground">{archiveCount}</span></span>
        {candidates.length > 0 && (
          <span>Last scan: <span className="font-medium text-foreground">{candidates.length} candidates</span></span>
        )}
      </div>

      {candidates.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">
          No cleanup candidates. Run a scan to detect dead code.
        </p>
      ) : (
        <div className="border border-border rounded overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-3 py-1.5 font-medium">File</th>
                <th className="text-center px-3 py-1.5 font-medium">Status</th>
                <th className="text-left px-3 py-1.5 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => (
                <tr key={i} className="border-t border-border/50">
                  <td className="px-3 py-1.5 font-mono">{c.file_path}</td>
                  <td className="px-3 py-1.5 text-center">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      c.classification === 'safe_to_delete'
                        ? 'bg-green-500/10 text-green-600'
                        : c.classification === 'needs_review'
                        ? 'bg-yellow-500/10 text-yellow-600'
                        : 'bg-muted text-muted-foreground'
                    }`}>
                      {c.classification.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-muted-foreground truncate max-w-[200px]">{c.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
