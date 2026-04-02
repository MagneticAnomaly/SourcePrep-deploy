/**
 * ManagedEmployeesTab — Roster table for generated agent employees.
 *
 * Shows each role with its completion status (AGENTS.md, SOUL.md, KNOWLEDGE.md).
 * Includes a generate button for creating new roles.
 */
import { EmployeeBadges, type RoleBadge } from './EmployeeBadges';

export interface ManagedEmployeesData {
  roles: RoleBadge[];
  readinessScore: number;
  readyForList: boolean;
  readyForAuto: boolean;
}

export interface ManagedEmployeesTabProps {
  data: ManagedEmployeesData | null;
  onGenerate?: (mode: string, roleNames: string[]) => void;
  className?: string;
}

export function ManagedEmployeesTab({
  data,
  onGenerate,
  className = '',
}: ManagedEmployeesTabProps) {
  if (!data) {
    return <div className="text-muted-foreground">No data available</div>;
  }

  if (data.roles.length === 0) {
    return (
      <div className={`text-center py-12 ${className}`}>
        <div className="text-4xl mb-4">&#128100;</div>
        <h3 className="font-semibold text-lg mb-2">No Agent Employees Yet</h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
          Generate AI agent role definitions from your codebase structure.
          Each role gets AGENTS.md (behavior), SOUL.md (identity), and KNOWLEDGE.md (context).
        </p>
        <div className="text-sm text-muted-foreground mb-4">
          Readiness: {(data.readinessScore * 100).toFixed(0)}%
          {data.readyForList ? ' — Ready for list mode' : ''}
          {data.readyForAuto ? ' — Ready for auto mode' : ''}
        </div>
        {onGenerate && data.readyForAuto && (
          <button
            onClick={() => onGenerate('auto', [])}
            className="px-4 py-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Auto-Generate Roles
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{data.roles.length} Role(s)</h3>
        {onGenerate && (
          <button
            onClick={() => onGenerate('auto', [])}
            className="text-xs px-3 py-1.5 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
          >
            + Add Roles
          </button>
        )}
      </div>

      {/* Roster Table */}
      <div className="border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Role</th>
              <th className="text-center px-3 py-2 font-medium">AGENTS.md</th>
              <th className="text-center px-3 py-2 font-medium">SOUL.md</th>
              <th className="text-center px-3 py-2 font-medium">KNOWLEDGE.md</th>
            </tr>
          </thead>
          <tbody>
            {data.roles.map((role) => (
              <tr key={role.slug} className="border-t border-border">
                <td className="px-3 py-2">
                  <div className="font-medium">{role.displayName}</div>
                  <div className="text-xs text-muted-foreground">{role.slug}</div>
                </td>
                <td className="text-center px-3 py-2">
                  {role.hasAgentsMd ? (
                    <span className="text-green-500">&#10003;</span>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </td>
                <td className="text-center px-3 py-2">
                  {role.hasSoulMd ? (
                    <span className="text-green-500">&#10003;</span>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </td>
                <td className="text-center px-3 py-2">
                  {role.hasKnowledgeMd ? (
                    <span className="text-green-500">&#10003;</span>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Badge view */}
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-2">Quick View</h4>
        <EmployeeBadges roles={data.roles} />
      </div>
    </div>
  );
}
