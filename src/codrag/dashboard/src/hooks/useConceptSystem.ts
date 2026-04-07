import { useState, useEffect, useCallback } from 'react';
import type { ConceptItem, ConceptQuestionItem, ConceptStats } from '@codrag/ui';

export interface UseConceptSystemReturn {
  concepts: ConceptItem[];
  questions: ConceptQuestionItem[];
  stats: ConceptStats | null;
  loading: boolean;
  initializing: boolean;
  error: string | null;
  handleInitialize: () => void;
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
  const [initializing, setInitializing] = useState(false);
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

  const handleInitialize = useCallback(async () => {
    if (!projectId || initializing) return;
    setInitializing(true);
    setError(null);
    try {
      const res = await fetch(`/projects/${projectId}/concepts/initialize`, {
        method: 'POST',
      });
      const data = await res.json();
      const result = data?.data ?? data;

      if (result?.status === 'success') {
        // Refresh after seeding
        await fetchConcepts();
      } else {
        // Show error for any non-success status (llm_error, no_model, insufficient_data, etc.)
        setError(result?.message || 'Initialization returned no results');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Initialization failed');
    } finally {
      setInitializing(false);
    }
  }, [projectId, initializing, fetchConcepts]);

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
    error,
    handleInitialize,
    handleApprove,
    handleArchive,
    handleDelete,
    handleMarkFresh,
    handleAnswerQuestion,
    handleRefresh: fetchConcepts,
  };
}
