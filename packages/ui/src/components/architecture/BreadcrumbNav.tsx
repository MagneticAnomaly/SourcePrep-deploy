import { Fragment, memo } from 'react';
import type { ArchBreadcrumb } from '../../types/architecture';

export interface BreadcrumbNavProps {
  breadcrumbs: ArchBreadcrumb[];
  onNavigateToLayer: (path: string[]) => void;
}

function BreadcrumbNavInner({ breadcrumbs, onNavigateToLayer }: BreadcrumbNavProps) {
  return (
    <div className="flex items-center gap-1 px-4 py-2 border-b border-zinc-800 bg-zinc-950 text-sm">
      {breadcrumbs.map((crumb, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="text-zinc-600 mx-1">{'›'}</span>}
          <button
            onClick={() => onNavigateToLayer(crumb.layerPath)}
            className={`px-2 py-0.5 rounded hover:bg-zinc-800 transition-colors ${
              i === breadcrumbs.length - 1 ? 'text-zinc-200 font-medium' : 'text-zinc-500'
            }`}
          >
            {crumb.label}
          </button>
        </Fragment>
      ))}
    </div>
  );
}

export const BreadcrumbNav = memo(BreadcrumbNavInner);
