import { useCallback, useEffect, useRef, useState } from 'react';
import type { AdminPolicy } from '../types';

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

interface UseAdminPolicyResult {
  policy: AdminPolicy | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

let _cachedPolicy: AdminPolicy | null = null;
let _cacheTimestamp = 0;

/**
 * React hook to fetch and cache the admin policy from the backend.
 *
 * The policy is cached globally for 5 minutes to avoid re-fetching
 * on every component mount. Call `refresh()` to force a re-fetch.
 */
export function useAdminPolicy(apiClient: { getAdminPolicy(): Promise<AdminPolicy> } | null): UseAdminPolicyResult {
  const [policy, setPolicy] = useState<AdminPolicy | null>(_cachedPolicy);
  const [loading, setLoading] = useState(!_cachedPolicy);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchPolicy = useCallback(async (force = false) => {
    if (!apiClient) return;

    const now = Date.now();
    if (!force && _cachedPolicy && now - _cacheTimestamp < CACHE_TTL_MS) {
      setPolicy(_cachedPolicy);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await apiClient.getAdminPolicy();
      if (mountedRef.current) {
        _cachedPolicy = result;
        _cacheTimestamp = Date.now();
        setPolicy(result);
        setLoading(false);
      }
    } catch (e: any) {
      if (mountedRef.current) {
        setError(e?.message || 'Failed to load admin policy');
        setLoading(false);
      }
    }
  }, [apiClient]);

  useEffect(() => {
    mountedRef.current = true;
    fetchPolicy();
    return () => { mountedRef.current = false; };
  }, [fetchPolicy]);

  const refresh = useCallback(() => fetchPolicy(true), [fetchPolicy]);

  return { policy, loading, error, refresh };
}
