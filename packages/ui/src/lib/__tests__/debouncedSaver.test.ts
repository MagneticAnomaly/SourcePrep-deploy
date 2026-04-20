import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createDebouncedSaver } from '../debouncedSaver';

describe('createDebouncedSaver', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not fire before any schedule() call', () => {
    const onSave = vi.fn();
    createDebouncedSaver<number>({ onSave, delayMs: 100 });
    vi.advanceTimersByTime(1000);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('fires once after delayMs of quiet', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    saver.schedule(1);
    expect(onSave).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(100);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith(1);
  });

  it('coalesces rapid schedules into one save with the latest value', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    saver.schedule(1);
    await vi.advanceTimersByTimeAsync(50);
    saver.schedule(2);
    await vi.advanceTimersByTimeAsync(50);
    saver.schedule(3);
    await vi.advanceTimersByTimeAsync(100);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith(3);
  });

  it('flush() forces immediate save and resolves after onPersist', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onPersist = vi.fn();
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 10000, onPersist });
    saver.schedule(42);
    expect(onSave).not.toHaveBeenCalled();
    await saver.flush();
    expect(onSave).toHaveBeenCalledWith(42);
    expect(onPersist).toHaveBeenCalledWith(42);
  });

  it('flush() is a no-op when nothing is pending', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    await saver.flush();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('cancel() discards any pending save', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    saver.schedule(1);
    saver.cancel();
    await vi.advanceTimersByTimeAsync(200);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('skips save when scheduled value equals the last persisted value', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<{ v: number }>({ onSave, delayMs: 50 });
    saver.schedule({ v: 1 });
    await vi.advanceTimersByTimeAsync(50);
    expect(onSave).toHaveBeenCalledTimes(1);
    saver.schedule({ v: 1 });
    await vi.advanceTimersByTimeAsync(50);
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it('uses custom equals when provided', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const equals = vi.fn().mockReturnValue(true);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 50, equals });
    saver.schedule(1);
    await vi.advanceTimersByTimeAsync(50);
    expect(onSave).toHaveBeenCalledTimes(1);
    saver.schedule(2);
    await vi.advanceTimersByTimeAsync(50);
    expect(equals).toHaveBeenCalledWith(1, 2);
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
