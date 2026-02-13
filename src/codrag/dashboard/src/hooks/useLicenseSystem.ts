import { useState, useCallback } from 'react'
import { useApiClient, type LicenseStatus, type LicenseTier } from '@codrag/ui'

export function useLicenseSystem() {
  const api = useApiClient()

  const [licenseStatus, setLicenseStatus] = useState<LicenseStatus | null>(null)
  const [licenseKeyInput, setLicenseKeyInput] = useState('')
  const [licenseLoading, setLicenseLoading] = useState(false)
  const [licenseError, setLicenseError] = useState<string | null>(null)
  const [devTierOverride, setDevTierOverride] = useState<LicenseTier | null>(() => {
    const stored = localStorage.getItem('codrag_dev_tier_override')
    return stored ? stored as LicenseTier : null
  })

  const fetchLicense = useCallback(async () => {
    try {
      const status = await api.getLicense()
      setLicenseStatus(status)
    } catch {
      // Silent — license endpoint may not be available
    }
  }, [api])

  const handleActivateLicense = useCallback(async () => {
    if (!licenseKeyInput.trim()) return
    setLicenseLoading(true)
    setLicenseError(null)
    try {
      const status = await api.activateLicense(licenseKeyInput.trim())
      setLicenseStatus(status)
      setLicenseKeyInput('')
    } catch (e) {
      setLicenseError(e instanceof Error ? e.message : 'Activation failed')
    } finally {
      setLicenseLoading(false)
    }
  }, [api, licenseKeyInput])

  const handleDeactivateLicense = useCallback(async () => {
    setLicenseLoading(true)
    setLicenseError(null)
    try {
      const status = await api.deactivateLicense()
      setLicenseStatus(status)
    } catch (e) {
      setLicenseError(e instanceof Error ? e.message : 'Deactivation failed')
    } finally {
      setLicenseLoading(false)
    }
  }, [api])

  const handleDevTierOverrideChange = useCallback((tier: LicenseTier | null) => {
    setDevTierOverride(tier)
    if (tier) {
      localStorage.setItem('codrag_dev_tier_override', tier)
    } else {
      localStorage.removeItem('codrag_dev_tier_override')
    }
  }, [])

  return {
    licenseStatus,
    licenseKeyInput,
    setLicenseKeyInput,
    licenseLoading,
    licenseError,
    devTierOverride,
    fetchLicense,
    handleActivateLicense,
    handleDeactivateLicense,
    handleDevTierOverrideChange,
  }
}
