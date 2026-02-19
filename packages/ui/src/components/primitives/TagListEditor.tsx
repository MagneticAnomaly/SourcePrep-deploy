import { useState, useRef } from 'react';
import { cn } from '../../lib/utils';
import { X, Plus } from 'lucide-react';

export interface TagListEditorProps {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  /** Validate a candidate tag before adding. Return error message or null. */
  validate?: (tag: string) => string | null;
  disabled?: boolean;
  maxVisible?: number;
  className?: string;
}

/**
 * TagListEditor — editable list of string tags (globs, labels, etc).
 * Enter or comma to add; X to remove; duplicate-safe.
 */
export function TagListEditor({
  tags,
  onChange,
  placeholder = 'Add…',
  validate,
  disabled = false,
  maxVisible,
  className,
}: TagListEditorProps) {
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addTag = (raw: string) => {
    const val = raw.trim();
    if (!val) return;
    if (tags.includes(val)) { setError('Already in list'); return; }
    if (validate) {
      const msg = validate(val);
      if (msg) { setError(msg); return; }
    }
    onChange([...tags, val]);
    setInput('');
    setError(null);
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(input);
    } else if (e.key === 'Backspace' && input === '' && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
    } else {
      setError(null);
    }
  };

  const visible = maxVisible && !showAll ? tags.slice(0, maxVisible) : tags;
  const hidden = maxVisible ? tags.length - maxVisible : 0;

  return (
    <div className={cn('space-y-1.5', className)}>
      {/* Tag chips */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {visible.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-raised px-2 py-0.5 text-xs font-mono text-text"
            >
              {tag}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="text-text-subtle hover:text-error transition-colors"
                  aria-label={`Remove ${tag}`}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </span>
          ))}
          {!showAll && hidden > 0 && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="text-xs text-text-subtle hover:text-text transition-colors"
            >
              +{hidden} more
            </button>
          )}
          {showAll && maxVisible && tags.length > maxVisible && (
            <button
              type="button"
              onClick={() => setShowAll(false)}
              className="text-xs text-text-subtle hover:text-text transition-colors"
            >
              show less
            </button>
          )}
        </div>
      )}

      {/* Input row */}
      {!disabled && (
        <div className="flex gap-1.5">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => { setInput(e.target.value); setError(null); }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className={cn(
              'flex-1 min-w-0 rounded-md border border-border bg-surface-raised px-2.5 py-1.5 text-xs font-mono text-text',
              'placeholder:text-text-subtle',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
              error && 'border-error focus-visible:ring-error'
            )}
          />
          <button
            type="button"
            onClick={() => addTag(input)}
            disabled={!input.trim()}
            className="flex items-center justify-center w-7 h-7 rounded-md border border-border bg-surface-raised text-text-muted hover:bg-surface hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            aria-label="Add tag"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {error && (
        <p className="text-xs text-error">{error}</p>
      )}
    </div>
  );
}
