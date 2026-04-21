import { useState, useEffect, useCallback } from 'react';
import type { ConceptItem, ConceptQuestionItem, ConceptStats } from '@prep/ui';
import { useStageRegenerate } from './useStageRegenerate';

export interface UseConceptSystemReturn {
  concepts: ConceptItem[];
  questions: ConceptQuestionItem[];
  stats: ConceptStats | null;
  loading: boolean;
  initializing: boolean;
  error: string | null;
  handleInitialize: () => Promise<void>;
  handleApprove: (id: string) => void;
  handleArchive: (id: string) => void;
  handleDelete: (id: string) => void;
  handleMarkFresh: (id: string) => void;
  handleAnswerQuestion: (questionId: string, answer: string) => void;
  handleRefresh: () => void;
}

export function useConceptSystem(
  projectId: string | null,
  opts: { signal?: AbortSignal } = {},
): UseConceptSystemReturn {
  const [concepts, setConcepts] = useState<ConceptItem[]>([]);
  const [questions, setQuestions] = useState<ConceptQuestionItem[]>([]);
  const [stats, setStats] = useState<ConceptStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchConcepts = useCallback(async () => {
    if (!projectId) return;
    const signal = opts.signal;
    setLoading(true);
    setError(null);
    try {
      // Fetch concepts + stats (critical) and questions (optional) in parallel.
      // Questions are fetched with allSettled so a 404 doesn't break the panel.
      const [conceptsRes, statsRes] = await Promise.all([
        fetch(`/projects/${projectId}/concepts`, { signal }),
        fetch(`/projects/${projectId}/concepts/stats`, { signal }),
      ]);

      const conceptsData = await conceptsRes.json();
      const statsData = await statsRes.json();

      const cdata = conceptsData?.data ?? conceptsData;
      const sdata = statsData?.data ?? statsData;

      setConcepts(cdata?.concepts ?? []);
      setStats(sdata ?? null);

      // Questions are optional — don't let a failure break the whole panel
      try {
        const questionsRes = await fetch(`/projects/${projectId}/concepts/questions`, { signal });
        if (questionsRes.ok) {
          const questionsData = await questionsRes.json();
          const qdata = questionsData?.data ?? questionsData;
          setQuestions(qdata?.questions ?? []);
        } else {
          setQuestions([]);
        }
      } catch {
        setQuestions([]);
      }
    } catch (e) {
      // Don't set error for aborted requests (project switch)
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setError(e instanceof Error ? e.message : 'Failed to load concepts');
    } finally {
      setLoading(false);
    }
  }, [projectId, opts.signal]);

  useEffect(() => {
    setConcepts([]);
    setStats(null);
    setQuestions([]);
    setError(null);
    if (projectId) {
      fetchConcepts();
    }
  }, [projectId, fetchConcepts]);

  // Phase 105b: concept seeding routes through the orchestrator
  // (POST /pipeline/stages/concepts/run?force=true) so it shares queue,
  // journal, history, and pipeline-panel state with all other finalize
  // stage triggers. Same handler serves both the empty-state "Initialize
  // Concepts" button and the populated-state "Regenerate" button.
  const {
    regenerating: initializing,
    error: regenerateError,
    runStage: handleInitialize,
  } = useStageRegenerate({
    projectId,
    stageId: 'concepts',
    onComplete: fetchConcepts,
  });

  const handleApprove = useCallback(async (id: string) => {
    if (!projectId) return;
    try {
      await fetch(`/projects/${projectId}/concepts/${id}/approve`, { method: 'PATCH' });
      // Optimistic update
      setConcepts((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: 'active' as const } : c))
      );
      // Refresh stats
      const statsRes = await fetch(`/projects/${projectId}/concepts/stats`);
      const statsData = await statsRes.json();
      setStats(statsData?.data ?? statsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Approve failed');
    }
  }, [projectId]);

  const handleArchive = useCallback(async (id: string) => {
    if (!projectId) return;
    try {
      await fetch(`/projects/${projectId}/concepts/${id}/archive`, { method: 'PATCH' });
      // Optimistic remove from view
      setConcepts((prev) => prev.filter((c) => c.id !== id));
      const statsRes = await fetch(`/projects/${projectId}/concepts/stats`);
      const statsData = await statsRes.json();
      setStats(statsData?.data ?? statsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Archive failed');
    }
  }, [projectId]);

  const handleDelete = useCallback(async (id: string) => {
    if (!projectId) return;
    try {
      await fetch(`/projects/${projectId}/concepts/${id}`, { method: 'DELETE' });
      setConcepts((prev) => prev.filter((c) => c.id !== id));
      const statsRes = await fetch(`/projects/${projectId}/concepts/stats`);
      const statsData = await statsRes.json();
      setStats(statsData?.data ?? statsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  }, [projectId]);

  const handleMarkFresh = useCallback(async (id: string) => {
    if (!projectId) return;
    try {
      await fetch(`/projects/${projectId}/concepts/${id}/fresh`, { method: 'PATCH' });
      // Optimistic update
      setConcepts((prev) =>
        prev.map((c) => (c.id === id ? { ...c, stale: false, stale_reason: undefined } : c))
      );
      const statsRes = await fetch(`/projects/${projectId}/concepts/stats`);
      const statsData = await statsRes.json();
      setStats(statsData?.data ?? statsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Mark fresh failed');
    }
  }, [projectId]);

  const handleAnswerQuestion = useCallback(async (questionId: string, answer: string) => {
    if (!projectId) return;
    try {
      await fetch(`/projects/${projectId}/concepts/questions/${questionId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      });
      // Remove from unanswered
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
      // Refresh concepts (a new one was created from the answer)
      await fetchConcepts();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Answer failed');
    }
  }, [projectId, fetchConcepts]);

  return {
    concepts,
    questions,
    stats,
    loading,
    initializing,
    error: error ?? regenerateError,
    handleInitialize,
    handleApprove,
    handleArchive,
    handleDelete,
    handleMarkFresh,
    handleAnswerQuestion,
    handleRefresh: fetchConcepts,
  };
}
