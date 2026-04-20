import { describe, it, expect } from 'vitest';
import { dirtyReducer, DirtyState } from '../useSettingsDirty';

const initial: DirtyState = { dirty: false, saving: false };

describe('dirtyReducer', () => {
  it('marks dirty on EDIT', () => {
    expect(dirtyReducer(initial, { type: 'EDIT' })).toEqual({ dirty: true, saving: false });
  });
  it('marks saving on SAVE_START', () => {
    expect(dirtyReducer({ dirty: true, saving: false }, { type: 'SAVE_START' }))
      .toEqual({ dirty: true, saving: true });
  });
  it('clears dirty on SAVE_SUCCESS', () => {
    expect(dirtyReducer({ dirty: true, saving: true }, { type: 'SAVE_SUCCESS' }))
      .toEqual({ dirty: false, saving: false });
  });
  it('keeps dirty on SAVE_ERROR', () => {
    expect(dirtyReducer({ dirty: true, saving: true }, { type: 'SAVE_ERROR' }))
      .toEqual({ dirty: true, saving: false });
  });
  it('clears dirty on DISCARD', () => {
    expect(dirtyReducer({ dirty: true, saving: false }, { type: 'DISCARD' }))
      .toEqual({ dirty: false, saving: false });
  });
});
