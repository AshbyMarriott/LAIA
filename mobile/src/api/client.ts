import { LaiaApiError } from './errors';
import type {
  ChatRequest,
  ChatResponse,
  ConnectionCheckResult,
  EventList,
  OllamaHealth,
} from './types';

export interface LaiaClientConfig {
  baseUrl: string;
  apiKey: string;
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

async function parseDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    if (data.detail != null) {
      return JSON.stringify(data.detail);
    }
  } catch {
    // ignore
  }
  return response.statusText || `HTTP ${response.status}`;
}

export class LaiaClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor(config: LaiaClientConfig) {
    this.baseUrl = normalizeBaseUrl(config.baseUrl);
    this.apiKey = config.apiKey.trim();
  }

  private headers(json = false): HeadersInit {
    const headers: Record<string, string> = {
      'X-API-Key': this.apiKey,
    };
    if (json) {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }

  private async request<T>(
    path: string,
    init: RequestInit & { json?: boolean } = {},
  ): Promise<T> {
    const { json, ...rest } = init;
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...rest,
        headers: {
          ...this.headers(json),
          ...(rest.headers ?? {}),
        },
      });
    } catch (error) {
      throw error;
    }

    if (!response.ok) {
      throw new LaiaApiError(response.status, await parseDetail(response));
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }

  async healthz(signal?: AbortSignal): Promise<{ status: string }> {
    // /healthz does not require the API key
    const response = await fetch(`${this.baseUrl}/healthz`, { signal });
    if (!response.ok) {
      throw new LaiaApiError(response.status, await parseDetail(response));
    }
    return (await response.json()) as { status: string };
  }

  async ollamaHealth(signal?: AbortSignal): Promise<OllamaHealth> {
    return this.request<OllamaHealth>('/api/health/ollama', { signal });
  }

  async checkConnection(signal?: AbortSignal): Promise<ConnectionCheckResult> {
    try {
      await this.healthz(signal);
    } catch (error) {
      return {
        apiOk: false,
        ollamaOk: false,
        error:
          error instanceof TypeError
            ? 'Cannot reach LAIA. Are you on Tailscale/WireGuard, and is the host URL correct?'
            : error instanceof Error
              ? error.message
              : 'Cannot reach API',
      };
    }

    try {
      const ollama = await this.ollamaHealth(signal);
      const ollamaOk = ollama.ok !== false && ollama.status !== 'error';
      return { apiOk: true, ollamaOk, ollama };
    } catch (error) {
      return {
        apiOk: true,
        ollamaOk: false,
        error:
          error instanceof Error
            ? `API reachable, but Ollama check failed: ${error.message}`
            : 'API reachable, but Ollama check failed',
      };
    }
  }

  async chat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    return this.request<ChatResponse>('/api/assistant/chat', {
      method: 'POST',
      json: true,
      body: JSON.stringify(body),
      signal,
    });
  }

  async searchEvents(
    params: { q?: string; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<EventList> {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    if (params.limit != null) query.set('limit', String(params.limit));
    if (params.offset != null) query.set('offset', String(params.offset));
    const qs = query.toString();
    return this.request<EventList>(`/api/events${qs ? `?${qs}` : ''}`, { signal });
  }
}

export function createClient(config: LaiaClientConfig): LaiaClient {
  return new LaiaClient(config);
}
