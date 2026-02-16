// pgql/dashboard/static/js/api.js
// API helper and authentication functions

export const API_BASE = "/api";
export const AUTH_KEY_STORAGE = "promptql_dashboard_key";

// --- Auth ---
export function getDashboardKey() {
  return localStorage.getItem(AUTH_KEY_STORAGE) || "";
}

export function setDashboardKey(key) {
  localStorage.setItem(AUTH_KEY_STORAGE, key);
}

export function showLoginPrompt() {
  const key = prompt("Enter Dashboard API Key (X-Dashboard-Key):");
  if (key) {
    setDashboardKey(key.trim());
    location.reload();
  }
}

export function logout() {
  localStorage.removeItem(AUTH_KEY_STORAGE);
  location.reload();
}

// --- API Fetch Wrapper ---
export async function api(path, options = {}) {
  try {
    const key = getDashboardKey();
    const headers = {
      "Content-Type": "application/json",
      ...(key ? { "X-Dashboard-Key": key } : {}),
      ...options.headers,
    };
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
      showLoginPrompt();
      throw new Error("Authentication required");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    return await res.json();
  } catch (e) {
    console.error(`API ${path}:`, e);
    throw e;
  }
}
