export type ServiceStatus = {
  status: "ok" | "error";
  detail?: string | null;
};

export type HealthResponse = {
  status: "ok" | "degraded";
  services: Record<string, ServiceStatus>;
};

export class ApiUnavailableError extends Error {}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (v.status === "ok" || v.status === "degraded") && typeof v.services === "object";
}

/** GET /api/health. A 503 still carries the per-service status, so it is not an error here. */
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  let response: Response;
  try {
    response = await fetch("/api/health", { signal, headers: { Accept: "application/json" } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiUnavailableError("network");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!isHealthResponse(body)) throw new ApiUnavailableError(`http ${response.status}`);
  return body;
}
