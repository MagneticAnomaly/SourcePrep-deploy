export interface DebouncedSaverOptions<T> {
  onSave: (value: T) => Promise<void> | void;
  delayMs: number;
  /** Fired synchronously after onSave resolves. */
  onPersist?: (value: T) => void;
  /** Equality test; defaults to JSON.stringify comparison. */
  equals?: (a: T, b: T) => boolean;
}

export interface DebouncedSaver<T> {
  /** Schedule a save; trailing-edge coalescing. */
  schedule(value: T): void;
  /** Force any pending save to run immediately; resolves after onPersist. */
  flush(): Promise<void>;
  /** Discard any pending save without firing. */
  cancel(): void;
}

export function createDebouncedSaver<T>(opts: DebouncedSaverOptions<T>): DebouncedSaver<T> {
  const equals = opts.equals ?? ((a: T, b: T) => JSON.stringify(a) === JSON.stringify(b));
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending: { value: T } | null = null;
  let lastPersisted: { value: T } | null = null;

  const runSave = async (): Promise<void> => {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    if (!pending) return;
    const { value } = pending;
    pending = null;
    if (lastPersisted && equals(lastPersisted.value, value)) return;
    await opts.onSave(value);
    lastPersisted = { value };
    opts.onPersist?.(value);
  };

  return {
    schedule(value: T): void {
      pending = { value };
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(() => {
        void runSave();
      }, opts.delayMs);
    },
    async flush(): Promise<void> {
      await runSave();
    },
    cancel(): void {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      pending = null;
    },
  };
}
