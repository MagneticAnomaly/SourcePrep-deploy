import { cn } from '../../lib/utils';

export interface DocNode {
  title: string;
  href: string;
  active?: boolean;
  children?: DocNode[];
  expanded?: boolean;
}

export interface DocsSidebarNavProps {
  items: DocNode[];
  className?: string;
}

export function DocsSidebarNav({ items, className }: DocsSidebarNavProps) {
  return (
    <nav className={cn('w-4/5', className)}>
      <ul className="space-y-4">
        {items.map((section, idx) => (
          <li key={idx}>
            <h4 className="font-semibold text-xs uppercase tracking-wider text-primary mb-3 px-2 border-t border-border pt-4 mt-2">
              {section.title}
            </h4>
            {section.children && (
              <ul className="space-y-1">
                {section.children.map((item) => (
                  <li key={item.href}>
                    <a
                      href={item.href}
                      className={cn(
                        'block px-2 py-1.5 text-sm rounded-md transition-colors',
                        item.active
                          ? 'bg-primary/10 text-primary font-medium'
                          : 'text-text-muted hover:text-text hover:bg-surface-raised'
                      )}
                    >
                      {item.title}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
