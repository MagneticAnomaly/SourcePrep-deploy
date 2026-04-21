import { useState, useCallback } from 'react'
import { useApiClient, type LicenseStatus, type LicenseTier } from '@prep/ui'

/**
 * Derives the dev tier override from the backend license response.
 * The backend writes a real license.json with activation_method="dev_override",
 * so we detect it here rather than relying solely on localStorage.
 */
function detectDevOverrideFromBackend(status: LicenseStatus | null): LicenseTier | null {
  const method = status?.license?.activation_method
  if (method === 'dev_override' || method === 'dev_env') {
    const tier = status?.license?.tier
    return tier && tier !== 'free' ? tier as LicenseTier : null
  }
  return null
}

/** Manages license activation, deactivation, dev-tier override, and status polling. */
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
      // Sync any stored dev tier override to the backend on startup.
      // The backend writes a real license.json so all feature gates work.
      const stored = localStorage.getItem('codrag_dev_tier_override')
      if (stored) {
        try { await api.setDevTierOverride(stored) } catch { /* ok */ }
      }
      const status = await api.getLicense()
      setLicenseStatus(status)

      // Hydrate devTierOverride from backend response as source of truth.
      // If backend says dev_override is active, reflect that in the dropdown
      // even if localStorage was cleared or desynchronized.
      const backendOverride = detectDevOverrideFromBackend(status)
      if (backendOverride) {
        setDevTierOverride(backendOverride)
        localStorage.setItem('codrag_dev_tier_override', backendOverride)
      } else if (!stored) {
        // No localStorage AND no backend override — ensure clean state
        setDevTierOverride(null)
      }
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

  const handleDevTierOverrideChange = useCallback(async (tier: LicenseTier | null) => {
    setDevTierOverride(tier)
    if (tier) {
      localStorage.setItem('codrag_dev_tier_override', tier)
    } else {
      localStorage.removeItem('codrag_dev_tier_override')
    }
    // Propagate to backend — this writes a REAL license.json file
    // so every feature gate works exactly like a real license.
    try {
      const status = await api.setDevTierOverride(tier)
      setLicenseStatus(status)
    } catch {
      // Silent — backend may not support dev-override yet
    }
  }, [api])

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
