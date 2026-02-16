// pgql/dashboard/static/js/utils.js
// Shared utility functions

export function formatUptime(seconds) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${Math.floor(seconds % 60)}s`;
}

export function showToast(msg, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

export function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

export function togglePasswordVisibility(inputId, toggleId) {
  const input = document.getElementById(inputId);
  const btn = document.getElementById(toggleId);
  if (input.type === "password") {
    input.type = "text";
    btn.textContent = "🔒";
    btn.title = "Hide";
  } else {
    input.type = "password";
    btn.textContent = "👁";
    btn.title = "Show";
  }
}
