import { useCallback, useEffect, useState } from 'react'
import { useApiClient } from '@prep/ui'
import type { AuditFinding, AuditStatus, AuditReport } from '@prep/ui'
import { useStageRegenerate } from './useStageRegenerate'

export interface UseAuditSystemReturn {
  auditStatus: AuditStatus | null
  auditFindings: AuditFinding[]
  auditReports: AuditReport[]
  auditReportContent: string | null
  viewingAuditReport: string | null
  handleRunAudit: (synthesize?: boolean) => void
  handleViewAuditReport: (reportName: string) => void
}

export function useAuditSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal; isHydrating?: boolean }
): UseAuditSystemReturn {
  const api = useApiClient()

  // Silence unused signal (Phase 105b: legacy polling ref removed alongside
  // the direct-call audit trigger; the shared useStageRegenerate hook now
  // handles completion polling).
  void options

  const [auditStatus, setAuditStatus] = useState<AuditStatus | null>(null)
  const [auditFindings, setAuditFindings] = useState<AuditFinding[]>([])
  const [auditReports, setAuditReports] = useState<AuditReport[]>([])
  const [auditReportContent, setAuditReportContent] = useState<string | null>(null)
  const [viewingAuditReport, setViewingAuditReport] = useState<string | null>(null)

  // Hydrate audit data on project change
  useEffect(() => {
    // Always clear previous project's data immediately to prevent cross-contamination
    setAuditStatus(null)
    setAuditFindings([])
    setAuditReports([])
    setAuditReportContent(null)
    setViewingAuditReport(null)

    if (!selectedProjectId) return

    const signal = options?.signal

    api.getAuditStatus(selectedProjectId)
      .then((s) => {
        if (signal?.aborted) return
        setAuditStatus(s)
        if (s.has_results) {
          api.getAuditFindings(selectedProjectId, { limit: 200 })
            .then((r) => { if (!signal?.aborted) setAuditFindings(r.findings || []) })
            .catch(() => {})
          api.getAuditReports(selectedProjectId)
            .then((r) => { if (!signal?.aborted) setAuditReports(r.reports || []) })
            .catch(() => {})
        }
      })
      .catch(() => {})
  }, [selectedProjectId, api])

  // Phase 105b: after the orchestrator-backed audit run completes, refresh
  // status + findings + reports so the panel reflects the new data.
  const onAuditComplete = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const s = await api.getAuditStatus(selectedProjectId)
      setAuditStatus(s)
      if (s.has_results) {
        const [f, r] = await Promise.all([
          api.getAuditFindings(selectedProjectId, { limit: 200 }),
          api.getAuditReports(selectedProjectId),
        ])
        setAuditFindings(f.findings || [])
        setAuditReports(r.reports || [])
      }
    } catch {
      // best-effort refresh
    }
  }, [selectedProjectId, api])

  const {
    regenerating: auditRunning,
    runStage: runAuditStage,
  } = useStageRegenerate({
    projectId: selectedProjectId,
    stageId: 'audit',
    onComplete: onAuditComplete,
  })

  // Keep auditStatus.running in sync with the orchestrator-reported state
  // so existing UI consumers that read auditStatus.running (HealthScannerPanel)
  // show the running indicator without a second state source.
  useEffect(() => {
    setAuditStatus((prev) => {
      if (prev) return { ...prev, running: auditRunning }
      return { running: auditRunning, error: null, has_results: false }
    })
  }, [auditRunning])

  // Phase 105b: synthesize flag is dropped — the orchestrator's audit
  // worker always runs Tier 2 synthesis. Signature kept compatible
  // (HealthScannerPanel passes false/true) so the existing UI doesn't
  // need to change.
  const handleRunAudit = useCallback((_synthesize?: boolean) => {
    void runAuditStage()
  }, [runAuditStage])

  const handleViewAuditReport = useCallback((reportName: string) => {
    if (!reportName) {
      setViewingAuditReport(null)
      setAuditReportContent(null)
      return
    }
    if (!selectedProjectId) return
    setViewingAuditReport(reportName)
    api.getAuditReport(selectedProjectId, reportName)
      .then((r) => setAuditReportContent(r.content || ''))
      .catch(() => setAuditReportContent('Failed to load report.'))
  }, [selectedProjectId, api])

  return {
    auditStatus,
    auditFindings,
    auditReports,
    auditReportContent,
    viewingAuditReport,
    handleRunAudit,
    handleViewAuditReport,
  }
}
