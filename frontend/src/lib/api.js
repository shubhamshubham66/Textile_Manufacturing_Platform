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

// The login lives in sessionStorage, which is separate for every browser tab.
// So you can be the owner in one tab and the Supermanager or a buyer in
// another, and logging in on one tab never changes who you are on the others.
// (localStorage is shared by all tabs, which made every tab switch role.)
function store() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function getToken() {
  const s = store();
  let t = s?.getItem(TOKEN_KEY) || null;
  // One-time move of a login saved by the older, shared-storage version.
  try {
    const old = localStorage.getItem(TOKEN_KEY);
    if (old) {
      localStorage.removeItem(TOKEN_KEY);
      if (!t) {
        t = old;
        s?.setItem(TOKEN_KEY, old);
      }
    }
  } catch {
    /* storage blocked: stay logged out */
  }
  return t;
}

export function setToken(token) {
  const s = store();
  if (!s) return;
  if (token) s.setItem(TOKEN_KEY, token);
  else s.removeItem(TOKEN_KEY);
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

// Open a protected PDF in a new tab. A plain <a href> can't send the bearer
// token (the API answers 401), so fetch it with the token and show the blob.
// The tab is opened first, inside the click, so popup blockers allow it.
export async function openPdf(path) {
  const win = window.open("", "_blank");
  try {
    const res = await fetch(path, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) {
      let message = `Could not open the PDF (HTTP ${res.status})`;
      try {
        const data = await res.json();
        message = data?.error?.message || data?.detail || message;
      } catch {
        // not JSON
      }
      if (res.status === 401) onSessionExpired();
      throw new Error(message);
    }
    const url = URL.createObjectURL(await res.blob());
    if (win) win.location.href = url;
    else window.location.assign(url);
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    if (win) win.close();
    window.alert(e.message || "Could not open the PDF.");
  }
}
