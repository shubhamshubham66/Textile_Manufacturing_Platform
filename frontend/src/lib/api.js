// Tiny fetch wrapper. Attaches the bearer token and normalises the backend's
// uniform error shape ({ error: { code, message } }) into a thrown Error.
//
// It also handles two cross-cutting concerns for the whole app:
//   * Expired/invalid session (HTTP 401): the stale token is cleared and the
//     user is sent to the login page once, instead of every page showing a
//     confusing error. (The login request itself opts out via auth:false.)
//   * Duplicate-sensitive writes: callers can pass an `idempotencyKey` so a
//     retried / double-clicked POST is de-duplicated by the backend.

const TOKEN_KEY = "etm_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

// A random key for idempotent writes. Uses crypto.randomUUID when available.
export function newIdempotencyKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// Guard so a storm of 401s (e.g. several pages loading at once) only triggers
// one redirect to /login.
let handlingExpiry = false;

function onSessionExpired() {
  if (handlingExpiry) return;
  handlingExpiry = true;
  setToken(null);
  // Avoid a redirect loop if we're already on an auth page.
  const path = window.location.pathname;
  if (path !== "/login" && path !== "/signup") {
    window.location.assign("/login?expired=1");
  }
}

export async function apiFetch(
  path,
  { method = "GET", body, auth = true, idempotencyKey } = {},
) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }
  }

  if (!res.ok) {
    // A 401 on an authenticated request means the session is gone — clear it
    // and bounce to login. We skip this for the login/signup calls themselves
    // (auth:false), whose 401 is a normal "wrong credentials" result the form
    // needs to display.
    if (res.status === 401 && auth) {
      onSessionExpired();
    }
    const message =
      data?.error?.message ||
      data?.detail ||
      `Request failed (HTTP ${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    err.code = data?.error?.code;
    throw err;
  }

  return data;
}
