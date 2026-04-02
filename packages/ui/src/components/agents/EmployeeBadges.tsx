/**
 * EmployeeBadges — Compact role badges for Paperclip-managed employees.
 *
 * Shows a row of small badges, one per generated agent role.
 */
export interface RoleBadge {
  slug: string;
  displayName: string;
  hasAgentsMd: boolean;
  hasSoulMd: boolean;
  hasKnowledgeMd: boolean;
}

export interface EmployeeBadgesProps {
  roles: RoleBadge[];
  className?: string;
}

export function EmployeeBadges({ roles, className = '' }: EmployeeBadgesProps) {
  if (roles.length === 0) {
    return (
      <div className={`text-xs text-muted-foreground italic ${className}`}>
        No roles generated yet
      </div>
    );
  }

  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {roles.map((role) => {
        const complete = role.hasAgentsMd && role.hasSoulMd && role.hasKnowledgeMd;
        return (
          <span
            key={role.slug}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
              complete
                ? 'bg-green-500/10 text-green-700 dark:text-green-400'
                : 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400'
            }`}
            title={`${role.displayName} — ${complete ? 'Complete' : 'Partial'}`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                complete ? 'bg-green-500' : 'bg-yellow-500'
              }`}
            />
            {role.displayName}
          </span>
        );
      })}
    </div>
  );
}
