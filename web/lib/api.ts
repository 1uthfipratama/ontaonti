export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = { method?: string; json?: unknown };

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const hasBody = opts.json !== undefined;
  const res = await fetch(API_URL + path, {
    method: opts.method ?? (hasBody ? "POST" : "GET"),
    credentials: "include",
    headers: hasBody ? { "Content-Type": "application/json" } : undefined,
    body: hasBody ? JSON.stringify(opts.json) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : Array.isArray(body.detail)
            ? body.detail.map((d: { msg: string }) => d.msg).join("; ")
            : JSON.stringify(body);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const fetcher = <T,>(path: string) => api<T>(path);

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
