import { useReducer, useCallback } from 'react';

export interface DirtyState {
  dirty: boolean;
  saving: boolean;
}

export type DirtyAction =
  | { type: 'EDIT' }
  | { type: 'SAVE_START' }
  | { type: 'SAVE_SUCCESS' }
  | { type: 'SAVE_ERROR' }
  | { type: 'DISCARD' };

export function dirtyReducer(state: DirtyState, action: DirtyAction): DirtyState {
  switch (action.type) {
    case 'EDIT':         return { ...state, dirty: true };
    case 'SAVE_START':   return { ...state, saving: true };
    case 'SAVE_SUCCESS': return { dirty: false, saving: false };
    case 'SAVE_ERROR':   return { ...state, saving: false };
    case 'DISCARD':      return { dirty: false, saving: false };
  }
}

export function useSettingsDirty() {
  const [state, dispatch] = useReducer(dirtyReducer, { dirty: false, saving: false });
  const markEdited = useCallback(() => dispatch({ type: 'EDIT' }), []);
  const startSave  = useCallback(() => dispatch({ type: 'SAVE_START' }), []);
  const finishSave = useCallback((ok: boolean) =>
    dispatch({ type: ok ? 'SAVE_SUCCESS' : 'SAVE_ERROR' }), []);
  const discard    = useCallback(() => dispatch({ type: 'DISCARD' }), []);
  return { ...state, markEdited, startSave, finishSave, discard };
}
