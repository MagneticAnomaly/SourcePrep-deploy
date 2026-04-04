import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiClient } from '@codrag/ui';
import type {
  ArchGraphResponse, ArchSummaryResponse, ArchNote,
  ArchState, ArchNoteCreate, ArchNodePosition,
} from '@codrag/ui';
import type { Viewport } from '@xyflow/react';

export interface UseArchitectureSystemReturn {
  summary: ArchSummaryResponse | null;
  graph: ArchGraphResponse | null;
  notes: ArchNote[];
  layerPath: string[];
  loading: boolean;
  error: string | null;
  selectedNodeId: string | null;
  savedPositions: ArchNodePosition[];
  savedViewport: Viewport | undefined;
  drillInto: (moduleId: string) => void;
  navigateToLayer: (path: string[]) => void;
  selectNode: (nodeId: string | null) => void;
  savePositions: (positions: ArchNodePosition[], viewport: Viewport) => void;
  createNote: (note: ArchNoteCreate) => void;
  updateNote: (noteId: string, content: string) => void;
  deleteNote: (noteId: string) => void;
}

export function useArchitectureSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal },
): UseArchitectureSystemReturn {
  const api = useApiClient();

  const [summary, setSummary] = useState<ArchSummaryResponse | null>(null);
  const [graph, setGraph] = useState<ArchGraphResponse | null>(null);
  const [notes, setNotes] = useState<ArchNote[]>([]);
  const [archState, setArchState] = useState<ArchState | null>(null);
  const [layerPath, setLayerPath] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const saveDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Hydrate on project change ────────────────────────────────────

  useEffect(() => {
    setSummary(null);
    setGraph(null);
    setNotes([]);
    setArchState(null);
    setLayerPath([]);
    setError(null);
    setSelectedNodeId(null);

    if (!selectedProjectId) return;

    setLoading(true);

    Promise.all([
      api.getArchitectureSummary(selectedProjectId),
      api.getArchitectureGraph(selectedProjectId),
      api.listArchitectureNotes(selectedProjectId),
      api.getArchitectureState(selectedProjectId),
    ])
      .then(([sum, g, n, s]) => {
        if (options?.signal?.aborted) return;
        setSummary(sum);
        setGraph(g);
        setNotes(n);
        setArchState(s);
      })
      .catch((err) => {
        if (options?.signal?.aborted) return;
        setError(err.message ?? 'Failed to load architecture');
      })
      .finally(() => {
        if (!options?.signal?.aborted) setLoading(false);
      });
  }, [selectedProjectId, api]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Navigation ───────────────────────────────────────────────────

  const fetchGraph = useCallback(
    (path: string[]) => {
      if (!selectedProjectId) return;
      setLoading(true);
      const layerParam = path.length > 0 ? path[path.length - 1] : undefined;
      api
        .getArchitectureGraph(selectedProjectId, layerParam)
        .then((g) => {
          if (!options?.signal?.aborted) setGraph(g);
        })
        .catch((err) => {
          if (!options?.signal?.aborted) setError(err.message);
        })
        .finally(() => {
          if (!options?.signal?.aborted) setLoading(false);
        });
    },
    [selectedProjectId, api, options?.signal],
  );

  const drillInto = useCallback(
    (moduleId: string) => {
      const newPath = [...layerPath, moduleId];
      setLayerPath(newPath);
      setSelectedNodeId(null);
      fetchGraph(newPath);
    },
    [layerPath, fetchGraph],
  );

  const navigateToLayer = useCallback(
    (path: string[]) => {
      setLayerPath(path);
      setSelectedNodeId(null);
      fetchGraph(path);
    },
    [fetchGraph],
  );

  // ── Layout persistence ───────────────────────────────────────────

  const savePositions = useCallback(
    (positions: ArchNodePosition[], viewport: Viewport) => {
      if (!selectedProjectId || !archState) return;

      const layerKey = layerPath.length === 0 ? 'root' : layerPath.join('/');
      const newState: ArchState = {
        ...archState,
        layouts: {
          ...archState.layouts,
          [layerKey]: {
            layer_path: layerKey,
            positions,
            viewport,
          },
        },
      };
      setArchState(newState);

      if (saveDebounce.current) clearTimeout(saveDebounce.current);
      saveDebounce.current = setTimeout(() => {
        api.saveArchitectureState(selectedProjectId, newState).catch((err) => {
          setError(`Layout save failed: ${err.message}`);
        });
      }, 1000);
    },
    [selectedProjectId, archState, layerPath, api],
  );

  // ── Notes CRUD ───────────────────────────────────────────────────

  const createNote = useCallback(
    (note: ArchNoteCreate) => {
      if (!selectedProjectId) return;
      api
        .createArchitectureNote(selectedProjectId, note)
        .then((created) => {
          setNotes((prev) => [...prev, created]);
        })
        .catch((err) => {
          setError(`Note creation failed: ${err.message}`);
        });
    },
    [selectedProjectId, api],
  );

  const updateNote = useCallback(
    (noteId: string, content: string) => {
      if (!selectedProjectId) return;
      setNotes((prev) =>
        prev.map((n) => (n.id === noteId ? { ...n, content } : n)),
      );
      api.updateArchitectureNote(selectedProjectId, noteId, { content }).catch((err) => {
        setError(`Note update failed: ${err.message}`);
        api.listArchitectureNotes(selectedProjectId).then(setNotes).catch(() => {});
      });
    },
    [selectedProjectId, api],
  );

  const deleteNote = useCallback(
    (noteId: string) => {
      if (!selectedProjectId) return;
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
      api.deleteArchitectureNote(selectedProjectId, noteId).catch((err) => {
        setError(`Note delete failed: ${err.message}`);
        api.listArchitectureNotes(selectedProjectId).then(setNotes).catch(() => {});
      });
    },
    [selectedProjectId, api],
  );

  // ── Derived: saved layout for current layer ──────────────────────

  const layerKey = layerPath.length === 0 ? 'root' : layerPath.join('/');
  const currentLayout = archState?.layouts[layerKey];
  const savedPositions = currentLayout?.positions ?? [];
  const savedViewport = currentLayout?.viewport as Viewport | undefined;

  return {
    summary,
    graph,
    notes,
    layerPath,
    loading,
    error,
    selectedNodeId,
    savedPositions,
    savedViewport,
    drillInto,
    navigateToLayer,
    selectNode: setSelectedNodeId,
    savePositions,
    createNote,
    updateNote,
    deleteNote,
  };
}
