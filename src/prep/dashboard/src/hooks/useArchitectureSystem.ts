import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiClient } from '@prep/ui';
import type {
  ArchGraphResponse, ArchSummaryResponse, ArchNote,
  ArchState, ArchNoteCreate, ArchNodePosition,
  ACR, ACRCreate, LinkedIssue, LinkIssueRequest,
} from '@prep/ui';
import type { Viewport } from '@xyflow/react';

export interface UseArchitectureSystemReturn {
  summary: ArchSummaryResponse | null;
  graph: ArchGraphResponse | null;
  notes: ArchNote[];
  acrs: ACR[];
  issueLinks: LinkedIssue[];
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
  createACR: (acr: ACRCreate) => void;
  approveACR: (acrId: string) => void;
  rejectACR: (acrId: string) => void;
  linkIssue: (nodeId: string, body: LinkIssueRequest) => void;
  unlinkIssue: (nodeId: string, issueId: string) => void;
  showOrphans: boolean;
  toggleOrphans: () => void;
}

export function useArchitectureSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal },
): UseArchitectureSystemReturn {
  const api = useApiClient();

  const [summary, setSummary] = useState<ArchSummaryResponse | null>(null);
  const [graph, setGraph] = useState<ArchGraphResponse | null>(null);
  const [notes, setNotes] = useState<ArchNote[]>([]);
  const [acrs, setACRs] = useState<ACR[]>([]);
  const [issueLinks, setIssueLinks] = useState<LinkedIssue[]>([]);
  const [archState, setArchState] = useState<ArchState | null>(null);
  const [layerPath, setLayerPath] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [showOrphans, setShowOrphans] = useState(false);

  const saveDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Hydrate on project change ────────────────────────────────────

  useEffect(() => {
    setSummary(null);
    setGraph(null);
    setNotes([]);
    setACRs([]);
    setIssueLinks([]);
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
      api.listACRs(selectedProjectId),
      api.listIssueLinks(selectedProjectId),
    ])
      .then(([sum, g, n, s, acrList, links]) => {
        if (options?.signal?.aborted) return;
        setSummary(sum);
        setGraph(g);
        setNotes(n);
        setArchState(s);
        setACRs(acrList);
        setIssueLinks(links);
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
    (path: string[], orphans?: boolean) => {
      if (!selectedProjectId) return;
      setLoading(true);
      const layerParam = path.length > 0 ? path[path.length - 1] : undefined;
      api
        .getArchitectureGraph(selectedProjectId, layerParam, orphans)
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

  const toggleOrphans = useCallback(
    () => {
      const next = !showOrphans;
      setShowOrphans(next);
      fetchGraph(layerPath, next);
    },
    [showOrphans, layerPath, fetchGraph],
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

  // ── ACR CRUD ─────────────────────────────────────────────────────

  const createACR = useCallback(
    (acr: ACRCreate) => {
      if (!selectedProjectId) return;
      api.createACR(selectedProjectId, acr)
        .then((created) => setACRs((prev) => [...prev, created]))
        .catch((err) => setError(`ACR creation failed: ${err.message}`));
    },
    [selectedProjectId, api],
  );

  const approveACR = useCallback(
    (acrId: string) => {
      if (!selectedProjectId) return;
      api.approveACR(selectedProjectId, acrId)
        .then((updated) => setACRs((prev) => prev.map((a) => a.id === acrId ? updated : a)))
        .catch((err) => setError(`ACR approve failed: ${err.message}`));
    },
    [selectedProjectId, api],
  );

  const rejectACR = useCallback(
    (acrId: string) => {
      if (!selectedProjectId) return;
      api.rejectACR(selectedProjectId, acrId)
        .then((updated) => setACRs((prev) => prev.map((a) => a.id === acrId ? updated : a)))
        .catch((err) => setError(`ACR reject failed: ${err.message}`));
    },
    [selectedProjectId, api],
  );

  // ── Issue Linking ────────────────────────────────────────────────

  const linkIssueAction = useCallback(
    (nodeId: string, body: LinkIssueRequest) => {
      if (!selectedProjectId) return;
      api.linkIssue(selectedProjectId, nodeId, body)
        .then(() => {
          setIssueLinks((prev) => [...prev, { ...body, node_id: nodeId }]);
        })
        .catch((err) => setError(`Issue link failed: ${err.message}`));
    },
    [selectedProjectId, api],
  );

  const unlinkIssueAction = useCallback(
    (nodeId: string, issueId: string) => {
      if (!selectedProjectId) return;
      api.unlinkIssue(selectedProjectId, nodeId, issueId)
        .then(() => {
          setIssueLinks((prev) => prev.filter(
            (l) => !(l.node_id === nodeId && l.paperclip_issue_id === issueId)
          ));
        })
        .catch((err) => setError(`Issue unlink failed: ${err.message}`));
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
    acrs,
    issueLinks,
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
    createACR,
    approveACR,
    rejectACR,
    linkIssue: linkIssueAction,
    unlinkIssue: unlinkIssueAction,
    showOrphans,
    toggleOrphans,
  };
}
