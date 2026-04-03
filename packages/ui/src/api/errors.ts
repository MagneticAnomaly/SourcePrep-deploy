import type { ApiError } from '../types';

export class ApiClientError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly apiError?: ApiError;
  readonly url?: string;
  /** True if the request was aborted (project switch or timeout) — not a real error */
  readonly aborted?: boolean;

  constructor(message: string, opts?: { status?: number; code?: string; apiError?: ApiError; url?: string; aborted?: boolean }) {
    super(message);
    this.name = 'ApiClientError';
    this.status = opts?.status;
    this.code = opts?.code;
    this.apiError = opts?.apiError;
    this.url = opts?.url;
    this.aborted = opts?.aborted;
  }
}
