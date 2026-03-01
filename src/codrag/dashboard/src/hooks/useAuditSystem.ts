import { useState, useCallback, useEffect } from 'react'
import { useApiClient } from '@codrag/ui'
import type { AuditFinding, AuditStatus, AuditReport } from '@codrag/ui'

export interface UseAuditSystemReturn {
  auditStatus: AuditStatus | null
  auditFindings: AuditFinding[]
  auditReports: AuditReport[]
  auditReportContent: string | null
  viewingAuditReport: string | null
  handleRunAudit: (synthesize?: boolean) => void
  handleViewAuditReport: (reportName: string) => void
}

export function useAuditSystem(selectedProjectId: string | null): UseAuditSystemReturn {
  const api = useApiClient()

  const [auditStatus, setAuditStatus] = useState<AuditStatus | null>(null)
  const [auditFindings, setAuditFindings] = useState<AuditFinding[]>([])
  const [auditReports, setAuditReports] = useState<AuditReport[]>([])
  const [auditReportContent, setAuditReportContent] = useState<string | null>(null)
  const [viewingAuditReport, setViewingAuditReport] = useState<string | null>(null)

  // Hydrate audit data on project change
  useEffect(() => {
    if (!selectedProjectId) {
      setAuditStatus(null)
      setAuditFindings([])
      setAuditReports([])
      return
    }
    api.getAuditStatus(selectedProjectId)
      .then((s) => {
        setAuditStatus(s)
        if (s.has_results) {
          api.getAuditFindings(selectedProjectId, { limit: 200 })
            .then((r) => setAuditFindings(r.findings || []))
            .catch(() => {})
          api.getAuditReports(selectedProjectId)
            .then((r) => setAuditReports(r.reports || []))
            .catch(() => {})
        }
      })
      .catch(() => {})
  }, [selectedProjectId, api])

  const handleRunAudit = useCallback((synthesize?: boolean) => {
    if (!selectedProjectId) return
    setAuditStatus((prev) => prev ? { ...prev, running: true } : { running: true, error: null, has_results: false })
    api.triggerAudit(selectedProjectId, { synthesize })
      .then(() => {
        // Poll for completion
        const poll = setInterval(() => {
          api.getAuditStatus(selectedProjectId)
            .then((s) => {
              setAuditStatus(s)
              if (!s.running) {
                clearInterval(poll)
                if (s.has_results) {
                  api.getAuditFindings(selectedProjectId, { limit: 200 })
                    .then((r) => setAuditFindings(r.findings || []))
                    .catch(() => {})
                  api.getAuditReports(selectedProjectId)
                    .then((r) => setAuditReports(r.reports || []))
                    .catch(() => {})
                }
              }
            })
            .catch(() => clearInterval(poll))
        }, 1500)
      })
      .catch(() => setAuditStatus((prev) => prev ? { ...prev, running: false, error: 'Failed to start audit' } : null))
  }, [selectedProjectId, api])

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
