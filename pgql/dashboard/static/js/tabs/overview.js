// pgql/dashboard/static/js/tabs/overview.js
// Overview tab — stats, tool breakdown, config badge

import { api } from "../api.js";
import { showToast, formatUptime, escapeHtml } from "../utils.js";

export async function loadOverview() {
  try {
    const [metrics, health, config] = await Promise.all([
      api("/metrics"),
      api("/health"),
      api("/config"),
    ]);

    // Stats cards
    document.getElementById("stat-requests").textContent =
      metrics.total_requests;
    document.getElementById("stat-success-rate").textContent =
      `${(metrics.success_rate * 100).toFixed(1)}%`;
    document.getElementById("stat-avg-time").textContent =
      `${metrics.avg_response_time_ms.toFixed(0)}ms`;
    document.getElementById("stat-uptime").textContent = formatUptime(
      health.uptime_seconds,
    );
    document.getElementById("stat-cache-hit").textContent = metrics.cache
      ? `${((metrics.cache.hits / Math.max(metrics.cache.hits + metrics.cache.misses, 1)) * 100).toFixed(0)}%`
      : "N/A";
    document.getElementById("stat-errors").textContent =
      metrics.failed_requests;

    // Tool breakdown
    const toolsBody = document.getElementById("tools-breakdown");
    toolsBody.innerHTML = "";
    for (const [tool, stats] of Object.entries(metrics.tools || {})) {
      toolsBody.innerHTML += `
                <tr>
                    <td style="color:var(--text-primary);font-weight:500">${escapeHtml(tool)}</td>
                    <td>${stats.total}</td>
                    <td>${stats.errors}</td>
                    <td>${stats.avg_duration_ms.toFixed(0)}ms</td>
                    <td><span class="badge ${stats.errors > 0 ? "warning" : "success"}">${stats.errors > 0 ? "Issues" : "Healthy"}</span></td>
                </tr>`;
    }
    if (Object.keys(metrics.tools || {}).length === 0) {
      toolsBody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No requests recorded yet</td></tr>';
    }

    // Config status badge + tooltip
    const badge = document.getElementById("config-status-badge");
    badge.className = `badge ${config.configured ? "success" : "error"}`;
    if (config.configured) {
      badge.textContent = "Configured";
      badge.title = "All required fields are set";
    } else {
      const missing = (config.missing_fields || []).map(f => f.label).join(", ");
      badge.textContent = "Not Configured";
      badge.title = `Missing: ${missing}`;
    }
  } catch (e) {
    showToast("Failed to load overview: " + e.message, "error");
  }
}

export async function updateConfigBadge() {
  try {
    const config = await api("/config");
    const badge = document.getElementById("config-status-badge");
    badge.className = `badge ${config.configured ? "success" : "error"}`;
    if (config.configured) {
      badge.textContent = "Configured";
      badge.title = "All required fields are set";
    } else {
      const missing = (config.missing_fields || []).filter(f => f.required !== false).map(f => f.label).join(", ");
      badge.textContent = "Not Configured";
      badge.title = `Missing: ${missing}`;
    }
  } catch (e) {
    // Silently fail
  }
}
