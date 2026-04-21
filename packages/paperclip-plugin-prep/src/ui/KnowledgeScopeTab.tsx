/**
 * Knowledge Scope Tab — read-only agent scope view in Paperclip.
 * Shows Prep-configured file scope + active claims. Edit in Prep dashboard only.
 */

interface Claim {
  id: string;
  agent_role: string;
  path: string;
  reason: string;
  expires_at: number;
}

export interface KnowledgeScopeTabProps {
  files: string[];
  role: string | null;
  claims?: Claim[];
  error?: string;
}

export function KnowledgeScopeTab({ files, role, claims = [], error }: KnowledgeScopeTabProps) {
  if (error) {
    return (
      <div className="p-4">
        <div className="text-sm text-yellow-400">{error}</div>
        <div className="text-xs text-gray-500 mt-2">
          Configure agent scopes in the Prep dashboard (Agent Knowledge Scopes panel).
        </div>
      </div>
    );
  }

  const relevantClaims = claims.filter((claim) =>
    files.some((f) => f.startsWith(claim.path) || claim.path.startsWith(f)),
  );

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">
          Knowledge Scope
          {role && <span className="text-gray-400 ml-1">({role})</span>}
        </div>
        <span className="text-xs text-gray-500">{files.length} files</span>
      </div>

      {files.length > 0 ? (
        <div className="space-y-0.5 max-h-64 overflow-y-auto">
          {files.map((file) => (
            <div key={file} className="text-xs text-gray-400 py-0.5 font-mono truncate">
              {file}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-gray-500 italic">
          No files in scope. Configure in Prep dashboard.
        </div>
      )}

      {relevantClaims.length > 0 && (
        <div>
          <div className="text-xs font-medium text-amber-400 mb-1">
            Active Claims ({relevantClaims.length})
          </div>
          {relevantClaims.map((claim) => (
            <div key={claim.id} className="text-xs text-gray-400 py-0.5">
              <span className="text-gray-300">{claim.agent_role}</span>
              {' → '}
              <span className="font-mono">{claim.path}</span>
              {claim.reason && (
                <span className="text-gray-500 ml-1">({claim.reason})</span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="text-[10px] text-gray-600 border-t border-gray-800 pt-2">
        Scope is read-only here. Edit in Prep dashboard → Agent Knowledge Scopes.
      </div>
    </div>
  );
}
