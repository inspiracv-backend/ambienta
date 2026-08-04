const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
  ) {
    super(`API ${status}: ${statusText}`);
    this.name = 'ApiError';
  }
}

interface RequestOptions {
  tenantId?: string | null;
  signal?: AbortSignal;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (opts.tenantId) {
    headers['X-Tenant-Id'] = opts.tenantId;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, res.statusText, detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get<T>(path: string, opts?: RequestOptions) {
    return request<T>('GET', path, undefined, opts);
  },
  post<T>(path: string, body: unknown, opts?: RequestOptions) {
    return request<T>('POST', path, body, opts);
  },
  patch<T>(path: string, body: unknown, opts?: RequestOptions) {
    return request<T>('PATCH', path, body, opts);
  },
  delete<T>(path: string, opts?: RequestOptions) {
    return request<T>('DELETE', path, undefined, opts);
  },
};
