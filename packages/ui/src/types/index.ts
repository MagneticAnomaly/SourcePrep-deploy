/**
 * Prep UI Type Definitions — barrel re-export.
 *
 * The types directory exists so consumers can import from
 * ``@prep/ui/types`` or ``../types``.  All types are currently
 * defined in the parent ``types.ts`` and re-exported here.
 *
 * Future: split into domain files (common, project, trace, llm, system)
 * once cross-file type references are properly resolved.
 */
export * from '../types';
