export class LaiaApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'LaiaApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function describeError(error: unknown): string {
  if (error instanceof LaiaApiError) {
    if (error.status === 401) {
      return 'API key rejected. Check the key in Settings.';
    }
    if (error.status >= 500) {
      return `Server error (${error.status}): ${error.detail}`;
    }
    return error.detail;
  }
  if (error instanceof TypeError) {
    return 'Cannot reach LAIA. Are you on Tailscale/WireGuard, and is the host URL correct?';
  }
  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return 'Request cancelled.';
    }
    return error.message;
  }
  return 'Something went wrong.';
}
