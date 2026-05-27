/**
 * Thin client over the ShelfPulse FastAPI service.
 * Default base URL is the local backend at port 8000.
 */

import type {
  ActionPlan,
  AskRequest,
  AskResult,
  HealthStatus,
  Insight,
} from "./types";

const DEFAULT_API_BASE = "http://localhost:8000";
const ASK_TIMEOUT_MS = 90_000; // 90 seconds for /ask, much shorter for the others

function apiBase(): string {
    return process.env.NEXT_PUBLIC_API_BASE ?? DEFAULT_API_BASE;
}

class ApiError extends Error {
    constructor(message: string, public readonly status?: number) {
        super(message);
        this.name = "ApiError";
    }
}

/**
 * Calls POST /ask. Returns either a successful AskResponse or a RefusalResponse.
 * Both shapes are HTTP 200 from the backend; distinguish with isRefusal().
 * Throws ApiError on HTTP 4xx/5xx or timeout.
 */
export async function askShelfPulse(req: AskRequest): Promise<AskResult> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), ASK_TIMEOUT_MS);

    try {
        const res = await fetch(`${apiBase()}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(req),
            signal: controller.signal,
        });

        if (!res.ok) {
            const text = await res.text().catch(() => "");
            throw new ApiError(
                `Backend error ${res.status}: ${text || res.statusText}`,
                res.status
         );
    }

    return (await res.json()) as AskResult;
    } catch (e) {
        if (e instanceof ApiError) throw e;
        if ((e as Error).name === "AbortError") {
            throw new ApiError(
                "Request timed out after 90 seconds. The agent usually responds in 20-70s; this may indicate the backend is overloaded.",
            );
        }
        throw new ApiError(`Network error: ${e instanceof Error ? e.message : "unknown"}`);
    } finally {
        clearTimeout(timeout);
    }
}


/**
 * Fetch a persisted Insight by trace_id. 404 if unknown.
 */
export async function getInsight(traceId: string): Promise<Insight | null> {
    const res = await fetch(`${apiBase()}/insights/${traceId}`);
    if (res.status === 404) return null;
    if (!res.ok) {
        throw new ApiError(`Backend error (${res.status})`, res.status);
    }
    return (await res.json()) as Insight;
}

/**
 * Fetch a persisted ActionPlan by trace_id. 404 if unknown.
 */
export async function getActionPlan(traceId: string): Promise<ActionPlan | null> {
  const res = await fetch(`${apiBase()}/actions/${traceId}`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new ApiError(`Backend error (${res.status})`, res.status);
  }
  return (await res.json()) as ActionPlan;
}

/**
 * Liveness probe. Used at app startup to confirm the backend is reachable.
 */
export async function checkHealth(): Promise<HealthStatus> {
  const res = await fetch(`${apiBase()}/healthz`);
  if (!res.ok) {
    throw new ApiError(`Health check failed (${res.status})`, res.status);
  }
  return (await res.json()) as HealthStatus;
}

export { ApiError };