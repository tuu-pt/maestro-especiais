/** HTTP client for /api. Every request says who is calling (development users, SPEC 4). */

const DEV_USER_KEY = "maestro.devUser";
export const DEFAULT_DEV_USER = "redator";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getDevUser(): string {
  try {
    return localStorage.getItem(DEV_USER_KEY) ?? DEFAULT_DEV_USER;
  } catch {
    return DEFAULT_DEV_USER;
  }
}

export function setDevUser(login: string): void {
  try {
    localStorage.setItem(DEV_USER_KEY, login);
  } catch {
    // private mode: the choice lasts until the page reloads
  }
}

export function authHeaders(): Record<string, string> {
  return { "X-Dev-User": getDevUser() };
}

async function errorMessage(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message: unknown }).message; // e.g. an invalid rule, with its position
      if (typeof message === "string") return message;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first.msg === "string") return first.msg.replace(/^Value error, /, "");
    }
  }
  return `Erro ${response.status}`;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { Accept: "application/json", ...authHeaders(), ...init.headers },
    });
  } catch {
    throw new ApiError(0, "Sem ligação ao servidor.");
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  return (await response.json()) as T;
}

/** Download a file from /api (a plain link would not say who is calling). */
export async function download(path: string, filename: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { headers: authHeaders() });
  } catch {
    throw new ApiError(0, "Sem ligação ao servidor.");
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** A small POST whose answer does not matter (e.g. the pilot's heartbeat); never throws. */
export async function beacon(path: string, body: unknown): Promise<void> {
  try {
    await fetch(`/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    });
  } catch {
    // offline: this beat is lost, the next one counts
  }
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
