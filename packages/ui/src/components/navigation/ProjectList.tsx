import { useState, type ReactNode } from 'react';
import type { ProjectSummary, PriorityLevel } from '../../types';
import { cn } from '../../lib/utils';
import { FolderPlus, X, Lock, Star } from 'lucide-react';
import { Button } from '../primitives/Button';
import { Toggle } from '../primitives/Toggle';

export interface ProjectListProps {
  projects: ProjectSummary[];
  selectedProjectId?: string;
  onProjectSelect: (projectId: string) => void;
  onAddProject: () => void;
  onDeleteProject?: (projectId: string, purge?: boolean) => void;
  onArchiveProject?: (projectId: string) => void;
  onUnarchiveProject?: (projectId: string) => void;
  onToggleActive?: (projectId: string, active: boolean, touch?: boolean) => void;
  onToggleStar?: (projectId: string, isStarred: boolean) => void;
  /** Called when user clicks the star to cycle priority. */
  onCyclePriority?: (projectId: string) => void;
  /** ID of the project that currently holds exclusive priority (for red star state). */
  exclusiveProjectId?: string | null;
  isPro?: boolean;
  extraActions?: ReactNode;
  beforeActions?: ReactNode;
  className?: string;
}

export interface ProjectListItemProps {
  project: ProjectSummary;
  selected: boolean;
  isPro: boolean;
  onClick: () => void;
  onDelete?: (purge?: boolean) => void;
  onArchive?: () => void;
  onUnarchive?: () => void;
  onToggleActive?: (active: boolean) => void;
  onToggleStar?: (isStarred: boolean) => void;
  onCyclePriority?: () => void;
  /** Whether another project holds exclusive priority (shows red deprioritized star). */
  isDeprioritized?: boolean;
}

/**
 * ProjectListItem - Single project row in the sidebar
 */
function ProjectListItem({ project, selected, isPro, onClick, onDelete, onArchive, onUnarchive, onToggleActive, onToggleStar, onCyclePriority, isDeprioritized }: ProjectListItemProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const rawStatus = project.activity_status ?? 'active';
  // In Pro tier, there are no locked projects — only active/inactive.
  // Force any stale locked from a race condition to "inactive".
  const status = isPro && rawStatus === 'locked' ? 'inactive' : rawStatus;
  const isLocked = status === 'locked';
  const isInactive = status === 'inactive';
  
  const isToggleChecked = status === 'active';
  // Pro: always toggleable. Free: can only toggle OFF projects ON (swap active slot), can't turn off the active one.
  const isToggleDisabled = (!isPro && isToggleChecked) || isLocked;

  const handleClick = () => {
    if (isLocked && !isPro) {
      // Locked projects on Free tier shouldn't be selectable
      // Instead, they might trigger an upsell modal (handled by parent or via unarchive)
      if (onUnarchive) {
        onUnarchive();
      }
      return;
    }
    onClick();
  };

  return (
    <div
      className={cn(
        'w-full text-left px-4 py-3 border-b border-border group relative overflow-hidden',
        'hover:bg-surface-raised transition-colors cursor-pointer',
        selected ? 'bg-surface-raised border-l-4 border-l-primary' : 'border-l-4 border-l-transparent',
        isLocked && 'bg-surface-base', // Mute background
        isInactive && 'opacity-90', // Slightly reduce opacity for paused/read-only
      )}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
    >
      {confirmingDelete ? (
        <div className="flex flex-col gap-2 relative z-10" onClick={(e) => e.stopPropagation()}>
          <div className="text-xs text-text-muted">
            {isPro ? "Delete project?" : "Archive or Delete?"}
          </div>
          {!isPro && (
            <div className="text-[10px] text-text-muted leading-tight mb-1">
              Archiving locks the project but saves your index data. Deleting permanently wipes it.
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            {!isPro && onArchive && !isLocked && (
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => { 
                  e.stopPropagation(); 
                  onArchive(); 
                  setConfirmingDelete(false); 
                }}
                className="text-xs h-7 w-full justify-start gap-1.5"
              >
                <Lock className="w-3 h-3" /> Archive (Lock)
              </Button>
            )}
            <div className="flex items-center gap-1.5">
              <Button
                variant="destructive"
                size="sm"
                onClick={(e) => { 
                  e.stopPropagation(); 
                  onDelete?.(!isPro); // purge if not pro
                  setConfirmingDelete(false); 
                }}
                className="text-xs h-7 px-2 flex-1"
              >
                Delete {isPro ? "" : "& Purge"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => { e.stopPropagation(); setConfirmingDelete(false); }}
                className="text-xs h-7 px-2 flex-1"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {isLocked && (
            <div className="absolute inset-0 z-0 bg-surface-base/50 flex items-center justify-center pointer-events-none">
              <div className="bg-surface p-1.5 rounded-full shadow-sm border border-border text-text-muted">
                <Lock className="w-4 h-4" />
              </div>
            </div>
          )}
          <div className="flex items-center justify-between relative z-10">
            <div className={cn("flex items-center gap-1.5 min-w-0", isLocked && "opacity-40")}>
              {(onCyclePriority || onToggleStar) && (() => {
                // Resolve priority level from new field or legacy is_starred
                const level: PriorityLevel = project.priority_level
                  ?? (project.is_starred ? 'boost' : 'none');
                const isNone = level === 'none';
                const isBoost = level === 'boost';
                const isExclusive = level === 'exclusive';

                // Visual states for the star icon
                const starClass = cn(
                  'w-4 h-4 transition-all duration-200',
                  isDeprioritized && isNone
                    ? 'text-destructive opacity-60'  // Red outline — deprioritized
                    : isExclusive
                      ? 'fill-primary text-primary drop-shadow-[0_0_4px_var(--color-primary)]'  // Gold with glow
                      : isBoost
                        ? 'fill-primary text-primary'  // Filled gold
                        : 'text-text-muted group-hover/star:text-primary opacity-20 group-hover/star:opacity-100'  // Muted outline
                );

                const tooltip = isDeprioritized && isNone
                  ? 'Queued — another project has exclusive priority'
                  : isExclusive
                    ? 'Exclusive priority (click to remove)'
                    : isBoost
                      ? 'Boosted (click for exclusive priority)'
                      : 'Click to boost priority';

                return (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onCyclePriority) {
                        onCyclePriority();
                      } else if (onToggleStar) {
                        onToggleStar(!project.is_starred);
                      }
                    }}
                    className={cn(
                      'flex-shrink-0 group/star p-0.5 -ml-1 hover:bg-surface-raised rounded transition-colors',
                      isExclusive && 'ring-1 ring-primary/40 rounded-full',
                      isDeprioritized && isNone && 'opacity-60'
                    )}
                    title={tooltip}
                  >
                    <Star className={starClass} />
                  </button>
                );
              })()}
              <div className="font-medium text-sm truncate max-w-[200px]" title={project.path}>
                {project.name}
              </div>
            </div>
            
            <div className="flex items-center gap-1">
              {!isLocked && onToggleActive && (
                <div onClick={(e) => e.stopPropagation()} className="px-1" title={isToggleDisabled ? 'Cannot deactivate active project on Free tier' : 'Toggle active status'}>
                  <Toggle
                    checked={isToggleChecked}
                    onChange={onToggleActive}
                    disabled={isToggleDisabled}
                    size="sm"
                  />
                </div>
              )}
              {onDelete && (
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmingDelete(true); }}
                  className={cn(
                    "p-1 hover:bg-surface-elevated rounded text-text-muted hover:text-destructive transition-all relative z-20 pointer-events-auto",
                    !isLocked && "opacity-0 group-hover:opacity-100"
                  )}
                  title="Remove project"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          <span className={cn("text-xs text-text-muted truncate block mt-1 relative z-10", isLocked && "opacity-40")}>
            {project.path}
          </span>
        </>
      )}
    </div>
  );
}

/**
 * ProjectList - List of registered projects in sidebar
 */
export function ProjectList({
  projects,
  selectedProjectId,
  onProjectSelect,
  onAddProject,
  onDeleteProject,
  onArchiveProject,
  onUnarchiveProject,
  onToggleActive,
  onToggleStar,
  onCyclePriority,
  exclusiveProjectId,
  isPro = false,
  extraActions,
  beforeActions,
  className,
}: ProjectListProps) {
  return (
    <div className={cn('flex flex-col h-full bg-surface-sunken overflow-hidden relative', className)}>
      {/* Scrollable Project List */}
      <div className="flex-1 overflow-y-auto">
        {projects.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-sm italic py-8">
            No projects yet
          </div>
        ) : (
          projects.map((project) => (
            <ProjectListItem
              key={project.id}
              project={project}
              selected={project.id === selectedProjectId}
              isPro={isPro}
              onClick={() => onProjectSelect(project.id)}
              onDelete={onDeleteProject ? (purge) => onDeleteProject(project.id, purge) : undefined}
              onArchive={onArchiveProject ? () => onArchiveProject(project.id) : undefined}
              onUnarchive={onUnarchiveProject ? () => onUnarchiveProject(project.id) : undefined}
              onToggleActive={onToggleActive ? (active) => onToggleActive(project.id, active, !isPro) : undefined}
              onToggleStar={onToggleStar ? (isStarred) => onToggleStar(project.id, isStarred) : undefined}
              onCyclePriority={onCyclePriority ? () => onCyclePriority(project.id) : undefined}
              isDeprioritized={!!exclusiveProjectId && exclusiveProjectId !== project.id}
            />
          ))
        )}
      </div>
      {beforeActions && (
        <div className="flex-shrink-0 border-t border-border">
          {beforeActions}
        </div>
      )}
      <div className="px-2 py-2 border-t border-border flex gap-1.5">
        <Button
          onClick={onAddProject}
          variant="outline"
          size="sm"
          className="flex-1 bg-surface hover:bg-surface-raised"
          icon={FolderPlus}
        >
          Add Project
        </Button>
        {extraActions && (
          <div className="flex-1 [&>div]:w-full [&_button:first-child]:w-full">
            {extraActions}
          </div>
        )}
      </div>
    </div>
  );
}
