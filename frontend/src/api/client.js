// src/api/client.js
//
// Single fetch wrapper for the whole frontend. One base URL (from
// VITE_API_BASE_URL — empty in dev = Vite proxy to backend), one
// AbortController-aware surface, one typed `ApiError` that the
// structured-error handler on the backend maps cleanly to.
//
// `humanize(error)` is the single place UI text comes from — replace
// M8a's noise (`alert(\`GEE Fusion failed: ${error.message}\`)`) with
// a single dispatch → toast / inline card. M9 will thread this into
// the Toast/ToastHost context.
//
// Backend contract reminder (M7):
//   200 OK                    → success
//   400 invalid_request       → semantic invalidity
//   404 no_imagery            → zero matching scenes
//   422 validation_error      → pydantic body validation
//   502 gee_compute_error     → ee.EEException
//   503 gee_unavailable       → GEE not initialised
//   500 internal_error        → anything else

const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  /**
   * @param {string} code    machine-readable code from the backend's
   *                         structured handler (e.g. "no_imagery").
   * @param {string} message human-readable backend message.
   * @param {number} status  HTTP status code.
   * @param {object} [extra] any extra fields the backend included.
   */
  constructor(code, message, status, extra) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.extra = extra || {};
  }
}

/** Map an HTTP error body onto a stable human message per code. */
export function humanize(err) {
  if (err instanceof ApiError) {
    switch (err.code) {
      case "gee_unavailable":
        return "Earth Engine is not ready. Check /health and the backend logs.";
      case "no_imagery":
        return "No cloud-free scenes for this area/date range. Widen the dates or raise the cloud tolerance.";
      case "validation_error":
        return "The request was rejected by the server. Check the date range and bounds.";
      case "gee_compute_error":
        return "Earth Engine rejected the request. Try a smaller AOI or different date range.";
      case "invalid_request":
        return err.message || "The request is invalid for the selected platform/mode.";
      case "internal_error":
        return "Internal server error. Check the backend logs.";
      default:
        return err.message || "Request failed.";
    }
  }
  if (err && err.name === "AbortError") return ""; // superseded click — silent
  return err?.message || "Network error.";
}

/**
 * @param {string} path  e.g. "/api/fusion/gee-harmonize".
 * @param {object} [opts]
 * @param {object} [opts.body]     JSON-serialisable body.
 * @param {object} [opts.query]    Query string params.
 * @param {AbortSignal} [opts.signal] AbortController signal.
 * @returns {Promise<any>}
 */
export async function request(path, { body, query, signal } = {}) {
  let url = BASE + path;
  if (query) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v == null) continue;
      qs.set(k, String(v));
    }
    const s = qs.toString();
    if (s) url += (url.includes("?") ? "&" : "?") + s;
  }

  const init = {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
  };
  if (body !== undefined) init.body = JSON.stringify(body);
  if (signal) init.signal = signal;

  const res = await fetch(url, init);

  if (res.status === 204) return null;

  const ct = res.headers.get("content-type") || "";
  const isJson = ct.includes("application/json");
  const payload = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    // The M7 handler returns {code, message, ...}. Older 4xx returns a
    // {detail: "..."} shape from FastAPI's default — handle both.
    if (isJson && payload && typeof payload === "object") {
      const { code, message, detail, ...extra } = payload;
      if (code) {
        throw new ApiError(code, message || detail || res.statusText, res.status, extra);
      }
      if (detail) {
        // Map FastAPI's auto-422 to our validation_error code so the UI
        // doesn't need to special-case the response shape.
        const inferred = res.status === 422 ? "validation_error" : "invalid_request";
        throw new ApiError(inferred, detail, res.status, extra);
      }
    }
    throw new ApiError("internal_error", String(payload || res.statusText), res.status, {});
  }

  return payload;
}
