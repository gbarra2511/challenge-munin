// Cliente HTTP fino para a API Flask. Anexa o Bearer token, parseia o envelope
// de erro padrão {error:{code,message,details?}} e lança ApiError tipado.
// O backend usa Authorization: Bearer (não cookie) — guardamos o token no client.

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:5000";

const TOKEN_KEY = "munin.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ApiOptions {
  method?: string;
  body?: unknown;
  auth?: boolean; // default: true
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch {
    throw new ApiError(0, "network_error", "Não foi possível falar com o servidor.");
  }

  // Token inválido/expirado: limpa para o guard mandar pro login.
  if (res.status === 401 && auth) clearToken();

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      if (!res.ok) throw new ApiError(res.status, "parse_error", "Resposta inválida do servidor.");
    }
  }

  if (!res.ok) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const err = (data as any)?.error ?? {};
    throw new ApiError(
      res.status,
      err.code ?? "error",
      err.message ?? "Erro inesperado.",
      err.details,
    );
  }
  return data as T;
}
