// pgql/dashboard/static/js/tabs/config.js
// Config tab — server configuration form

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";
import { updateConfigBadge } from "./overview.js";

export async function loadConfig() {
  try {
    const data = await api("/config");
    const container = document.getElementById("config-fields");
    container.innerHTML = "";

    // Show missing fields warning if not configured
    const requiredMissing = (data.missing_fields || []).filter(f => f.required !== false);
    const optionalMissing = (data.missing_fields || []).filter(f => f.required === false);

    if (requiredMissing.length > 0) {
      let warningHtml = `<div style="background:var(--error-bg);border:1px solid var(--error-border);border-radius:var(--radius-sm);padding:14px 18px;margin-bottom:16px">
        <div style="font-weight:600;color:var(--error);margin-bottom:8px">⛔ Missing Required Configuration</div>
        <div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">The following fields must be set for the server to function:</div>
        <ul style="margin:0;padding-left:20px;font-size:13px;color:var(--text-primary)">`;
      requiredMissing.forEach(f => {
        warningHtml += `<li style="margin-bottom:6px"><strong>${escapeHtml(f.label)}</strong> — <code style="background:var(--bg-input);padding:1px 6px;border-radius:3px;font-size:12px">${escapeHtml(f.env)}</code><br><span style="color:var(--text-muted);font-size:12px">${escapeHtml(f.hint)}</span></li>`;
      });
      warningHtml += `</ul></div>`;
      container.innerHTML += warningHtml;
    }

    if (optionalMissing.length > 0) {
      let infoHtml = `<div style="background:var(--info-bg);border:1px solid var(--info-border);border-radius:var(--radius-sm);padding:14px 18px;margin-bottom:16px">
        <div style="font-weight:600;color:var(--info);margin-bottom:8px">ℹ️ Optional Configuration</div>
        <ul style="margin:0;padding-left:20px;font-size:13px;color:var(--text-primary)">`;
      optionalMissing.forEach(f => {
        infoHtml += `<li style="margin-bottom:4px"><strong>${escapeHtml(f.label)}</strong> — <code style="background:var(--bg-input);padding:1px 6px;border-radius:3px;font-size:12px">${escapeHtml(f.env)}</code><br><span style="color:var(--text-muted);font-size:12px">${escapeHtml(f.hint)}</span></li>`;
      });
      infoHtml += `</ul></div>`;
      container.innerHTML += infoHtml;
    }

    // Config field labels
    const fieldLabels = {
      api_key: "API Key",
      base_url: "PGQL Base URL",
      auth_mode: "Auth Mode",
      hasura_graphql_endpoint: "Hasura GraphQL Endpoint",
      hasura_admin_secret: "Hasura Admin Secret",
      auth_token: "Auth Token (DDN — Optional)",
    };

    for (const [key, value] of Object.entries(data.config || {})) {
      const isSensitive = [
        "api_key",
        "auth_token",
        "hasura_admin_secret",
      ].includes(key);
      const label = fieldLabels[key] || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const inputId = `cfg-${key}`;
      const toggleId = `toggle-${key}`;

      // Auth Mode — render as dropdown
      if (key === "auth_mode") {
        container.innerHTML += `
                <div class="form-group">
                    <label>${label}</label>
                    <div style="display:flex;gap:6px">
                        <select id="${inputId}" style="flex:1;padding:8px 10px;border:1px solid var(--border-color);border-radius:var(--radius-sm);font-size:14px;font-family:Inter,sans-serif;background:var(--bg-card);color:var(--text-primary)">
                            <option value="public" ${value === "public" ? "selected" : ""}>Public — Auth-Token header (DDN default)</option>
                            <option value="private" ${value === "private" ? "selected" : ""}>Private — x-hasura-ddn-token header</option>
                        </select>
                        <button class="btn btn-outline btn-sm" onclick="updateConfig('${key}')">Save</button>
                    </div>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:4px">Controls which HTTP header is used for DDN authentication. Only relevant when Auth Token is set.</div>
                </div>`;
        continue;
      }

      let extraButtons = "";

      // Show/Hide toggle for sensitive fields
      if (isSensitive) {
        extraButtons += `<button id="${toggleId}" class="btn btn-outline btn-sm" onclick="togglePasswordVisibility('${inputId}', '${toggleId}')" title="Show/Hide" style="min-width:36px">👁</button>`;
      }

      // Generate button only for api_key
      if (key === "api_key") {
        extraButtons += `<button class="btn btn-outline btn-sm" onclick="generateApiKey()" title="Generate random key" style="min-width:80px">🎲 Generate</button>`;
      }

      container.innerHTML += `
                <div class="form-group">
                    <label>${label}</label>
                    <div style="display:flex;gap:6px">
                        <input id="${inputId}" value="${escapeHtml(value || "")}"
                               type="${isSensitive ? "password" : "text"}"
                               placeholder="Not set"
                               style="flex:1" />
                        ${extraButtons}
                        <button class="btn btn-outline btn-sm" onclick="updateConfig('${key}')">Save</button>
                    </div>
                </div>`;
    }
  } catch (e) {
    showToast("Failed to load config: " + e.message, "error");
  }
}

export async function generateApiKey() {
  try {
    const data = await api("/config/generate-key", { method: "POST" });
    const input = document.getElementById("cfg-api_key");
    if (input) {
      input.value = data.key;
      input.type = "text"; // Show the generated key
      const toggle = document.getElementById("toggle-api_key");
      if (toggle) {
        toggle.textContent = "🔒";
        toggle.title = "Hide";
      }
    }
    showToast("Key generated! Click Save to apply.", "success");
  } catch (e) {
    showToast("Failed to generate key: " + e.message, "error");
  }
}

export async function updateConfig(key) {
  const input = document.getElementById(`cfg-${key}`);
  if (!input || !input.value) return;
  try {
    await api("/config", {
      method: "PUT",
      body: JSON.stringify({ key, value: input.value }),
    });
    showToast(`Updated ${key}`, "success");
    loadConfig();
    updateConfigBadge();
  } catch (e) {
    showToast(`Failed: ${e.message}`, "error");
  }
}
