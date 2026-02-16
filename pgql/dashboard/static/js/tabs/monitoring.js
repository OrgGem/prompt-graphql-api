// pgql/dashboard/static/js/tabs/monitoring.js
// Monitoring tab — request and error logs with daily file-based persistence

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";

let autoRefreshInterval = null;

export async function loadMonitoring() {
  try {
    const [requests, errors] = await Promise.all([
      api("/metrics/requests?limit=20"),
      api("/metrics/errors?limit=10"),
    ]);

    renderRequestTable(requests.requests || []);
    renderErrorTable(errors.errors || []);
    
    // Load available log dates for date picker
    await loadLogDates();
  } catch (e) {
    showToast("Failed to load monitoring: " + e.message, "error");
  }
}

function renderRequestTable(requests) {
  const reqBody = document.getElementById("request-log");
  reqBody.innerHTML = "";
  requests.reverse().forEach((req) => {
    // Highlight chat requests with special styling
    const isChatRequest = req.tool === "chat_request";
    const toolDisplay = isChatRequest 
      ? `<span class="badge info" style="font-weight:600">💬 ${escapeHtml(req.tool)}</span>`
      : `<span style="color:var(--text-primary)">${escapeHtml(req.tool)}</span>`;
    
    reqBody.innerHTML += `
              <tr>
                  <td style="font-size:11px">${new Date(req.timestamp).toLocaleTimeString()}</td>
                  <td>${toolDisplay}</td>
                  <td>${req.duration_ms}ms</td>
                  <td><span class="badge ${req.success ? "success" : "error"}">${req.success ? "OK" : "Error"}</span></td>
                  <td style="font-size:11px;color:var(--text-muted)">${req.error ? escapeHtml(req.error) : "—"}</td>
              </tr>`;
  });
  if (requests.length === 0) {
    reqBody.innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No requests yet</td></tr>';
  }
}

function renderErrorTable(errors) {
  const errBody = document.getElementById("error-log");
  errBody.innerHTML = "";
  errors.reverse().forEach((err) => {
    errBody.innerHTML += `
              <tr>
                  <td style="font-size:11px">${new Date(err.timestamp).toLocaleTimeString()}</td>
                  <td style="color:var(--text-primary)">${escapeHtml(err.tool)}</td>
                  <td style="color:var(--error)">${escapeHtml(err.error)}</td>
              </tr>`;
  });
  if (errors.length === 0) {
    errBody.innerHTML =
      '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">No errors 🎉</td></tr>';
  }
}

async function loadLogDates() {
  try {
    const data = await api("/metrics/logs/dates");
    const selector = document.getElementById("log-date-selector");
    if (!selector) return;
    
    // Keep "Today (Live)" option, add historical dates
    const currentValue = selector.value;
    selector.innerHTML = '<option value="">Today (Live)</option>';
    
    (data.dates || []).forEach(date => {
      const option = document.createElement("option");
      option.value = date;
      option.textContent = date;
      selector.appendChild(option);
    });
    
    // Restore selection
    selector.value = currentValue;
  } catch (e) {
    console.warn("Failed to load log dates:", e);
  }
}

export async function loadLogByDate(date) {
  const badge = document.getElementById("log-view-badge");
  
  if (!date) {
    // Live mode - load current requests
    if (badge) {
      badge.textContent = "Live";
      badge.className = "badge success";
    }
    
    // Re-enable auto-refresh
    startAutoRefresh();
    await loadMonitoring();
    return;
  }
  
  // Historical mode - load from file
  if (badge) {
    badge.textContent = `Archive: ${date}`;
    badge.className = "badge info";
  }
  
  // Disable auto-refresh for historical view
  stopAutoRefresh();
  
  try {
    const data = await api(`/metrics/logs/${date}?limit=100`);
    renderRequestTable(data.entries || []);
    
    // Clear error table for historical view (errors included in entries)
    const errBody = document.getElementById("error-log");
    if (errBody) {
      const errorEntries = (data.entries || []).filter(e => !e.success);
      if (errorEntries.length > 0) {
        renderErrorTable(errorEntries.map(e => ({
          timestamp: e.timestamp,
          tool: e.tool,
          error: e.error || "Unknown error"
        })));
      } else {
        errBody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">No errors on this date 🎉</td></tr>';
      }
    }
    
    showToast(`Loaded ${data.total} entries from ${date}`, "success");
  } catch (e) {
    showToast(`Failed to load logs for ${date}: ${e.message}`, "error");
  }
}

function startAutoRefresh() {
  if (autoRefreshInterval) return;
  autoRefreshInterval = setInterval(() => {
    const selector = document.getElementById("log-date-selector");
    if (selector && !selector.value) {
      // Only auto-refresh if in live mode
      loadMonitoring();
    }
  }, 10000); // 10 seconds
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
}

// Export for global access
window.loadLogByDate = loadLogByDate;

// Start auto-refresh when monitoring tab is active
export function initMonitoring() {
  startAutoRefresh();
}
