// pgql/dashboard/static/js/tabs/monitoring.js
// Monitoring tab — request and error logs

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";

export async function loadMonitoring() {
  try {
    const [requests, errors] = await Promise.all([
      api("/metrics/requests?limit=20"),
      api("/metrics/errors?limit=10"),
    ]);

    const reqBody = document.getElementById("request-log");
    reqBody.innerHTML = "";
    (requests.requests || []).reverse().forEach((req) => {
      reqBody.innerHTML += `
                <tr>
                    <td style="font-size:11px">${new Date(req.timestamp).toLocaleTimeString()}</td>
                    <td style="color:var(--text-primary)">${escapeHtml(req.tool)}</td>
                    <td>${req.duration_ms}ms</td>
                    <td><span class="badge ${req.success ? "success" : "error"}">${req.success ? "OK" : "Error"}</span></td>
                    <td style="font-size:11px;color:var(--text-muted)">${req.error ? escapeHtml(req.error) : "—"}</td>
                </tr>`;
    });
    if ((requests.requests || []).length === 0) {
      reqBody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No requests yet</td></tr>';
    }

    const errBody = document.getElementById("error-log");
    errBody.innerHTML = "";
    (errors.errors || []).reverse().forEach((err) => {
      errBody.innerHTML += `
                <tr>
                    <td style="font-size:11px">${new Date(err.timestamp).toLocaleTimeString()}</td>
                    <td style="color:var(--text-primary)">${escapeHtml(err.tool)}</td>
                    <td style="color:var(--error)">${escapeHtml(err.error)}</td>
                </tr>`;
    });
    if ((errors.errors || []).length === 0) {
      errBody.innerHTML =
        '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">No errors 🎉</td></tr>';
    }
  } catch (e) {
    showToast("Failed to load monitoring: " + e.message, "error");
  }
}
