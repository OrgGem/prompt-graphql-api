// pgql/dashboard/static/js/tabs/apps.js
// Apps tab — multi-app access control management

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";

// ── Load & Display Apps ─────────────────────────────────────

export async function loadApps() {
  try {
    const data = await api("/apps");
    const container = document.getElementById("apps-list");
    if (!container) return;

    const apps = data.apps || [];
    if (apps.length === 0) {
      container.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:20px">No apps created yet. Create one above to get started.</div>`;
      return;
    }

    container.innerHTML = "";
    for (const app of apps) {
      const tableList = (app.allowed_tables || [])
        .map((t) => `<span style="background:var(--bg-input);padding:2px 8px;border-radius:12px;font-size:11px;margin:2px">${escapeHtml(t)}</span>`)
        .join(" ");

      const roleBadge =
        app.role === "write"
          ? `<span class="badge warning">✏️ Write</span>`
          : `<span class="badge success">🔒 Read</span>`;

      const statusBadge = app.active !== false
        ? `<span class="badge success">Active</span>`
        : `<span class="badge error">Disabled</span>`;

      container.innerHTML += `
        <div class="key-card" style="margin-bottom:12px">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
            <div>
              <div class="provider" style="font-size:15px">📱 ${escapeHtml(app.app_id)}</div>
              <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${escapeHtml(app.description || "")}</div>
            </div>
            <div style="display:flex;gap:6px;align-items:center">
              ${roleBadge} ${statusBadge}
            </div>
          </div>

          <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px">
            API Key: <code style="background:var(--bg-input);padding:2px 6px;border-radius:3px">${escapeHtml(app.api_key)}</code>
          </div>

          <div style="margin-bottom:8px">
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">Allowed Tables:</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px">
              ${tableList || '<span style="color:var(--text-muted);font-size:12px">No tables assigned</span>'}
            </div>
          </div>

          <div class="actions" style="display:flex;gap:6px;margin-top:8px">
            <button class="btn btn-outline btn-sm" onclick="editApp('${escapeHtml(app.app_id)}')">✏️ Edit</button>
            <button class="btn btn-outline btn-sm" onclick="regenerateAppKey('${escapeHtml(app.app_id)}')">🔄 New Key</button>
            <button class="btn btn-outline btn-sm" onclick="toggleApp('${escapeHtml(app.app_id)}', ${app.active === false})">${app.active !== false ? "⏸ Disable" : "▶ Enable"}</button>
            <button class="btn btn-danger btn-sm" onclick="deleteApp('${escapeHtml(app.app_id)}')">🗑 Delete</button>
          </div>
        </div>`;
    }
  } catch (e) {
    showToast(`Failed to load apps: ${e.message}`, "error");
  }
}

// ── Schema Loader ───────────────────────────────────────────

export async function reloadSchema() {
  const container = document.getElementById("schema-tables-container");
  if (container) {
    container.innerHTML = `<div style="color:var(--text-muted);font-size:13px">⏳ Loading tables from Hasura...</div>`;
  }

  try {
    const data = await api("/apps/schema/reload", { method: "POST" });
    renderSchemaCheckboxes(data.tables || []);
    showToast(`Loaded ${data.total} tables from Hasura`, "success");
  } catch (e) {
    if (container) {
      container.innerHTML = `<div style="color:var(--error);font-size:13px">❌ ${escapeHtml(e.message)}</div>`;
    }
    showToast(`Schema reload failed: ${e.message}`, "error");
  }
}

export async function loadSchemaCache() {
  try {
    const data = await api("/apps/schema/tables");
    if (data.tables && data.tables.length > 0) {
      renderSchemaCheckboxes(data.tables);
    }
  } catch {
    // Silent fail — user can click reload
  }
}

function renderSchemaCheckboxes(tables, selectedTables = []) {
  const container = document.getElementById("schema-tables-container");
  if (!container) return;

  if (tables.length === 0) {
    container.innerHTML = `<div style="color:var(--text-muted);font-size:13px">No tracked tables found. Click "Reload from Hasura" to refresh.</div>`;
    return;
  }

  const selectAllChecked = selectedTables.length === tables.length;
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:var(--bg-card);border:1px solid var(--border-color);border-bottom:none;border-radius:var(--radius-sm) var(--radius-sm) 0 0">
      <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:500;font-size:13px">
        <input type="checkbox" id="schema-select-all" onchange="toggleAllTables(this.checked)" ${selectAllChecked ? "checked" : ""} />
        <span>Select All</span>
      </label>
      <span class="badge info" style="font-size:11px">${tables.length} tables</span>
    </div>
    <div style="max-height:280px;overflow-y:auto;border:1px solid var(--border-color);border-radius:0 0 var(--radius-sm) var(--radius-sm)">
      ${tables
        .sort((a, b) => a.localeCompare(b))
        .map(
          (t) => `
        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px 12px;border-bottom:1px solid var(--border-color);transition:background 0.15s;font-size:13px" onmouseover="this.style.background='var(--bg-card-hover)'" onmouseout="this.style.background='var(--bg-card)'">
          <input type="checkbox" class="schema-table-cb" value="${escapeHtml(t)}" ${selectedTables.includes(t) ? "checked" : ""} style="margin:0;flex-shrink:0" />
          <span style="color:var(--text-primary);flex:1">${escapeHtml(t)}</span>
        </label>`
        )
        .join("")}
    </div>`;
}

export function toggleAllTables(checked) {
  document.querySelectorAll(".schema-table-cb").forEach((cb) => {
    cb.checked = checked;
  });
}

function getSelectedTables() {
  return Array.from(document.querySelectorAll(".schema-table-cb:checked")).map(
    (cb) => cb.value
  );
}

// ── Create App ──────────────────────────────────────────────

export async function createApp() {
  const appId = document.getElementById("new-app-id")?.value?.trim();
  const description = document.getElementById("new-app-description")?.value?.trim() || "";
  const role = document.getElementById("new-app-role")?.value || "read";
  const allowedTables = getSelectedTables();

  if (!appId) {
    showToast("App ID is required", "error");
    return;
  }

  try {
    const data = await api("/apps", {
      method: "POST",
      body: JSON.stringify({
        app_id: appId,
        description,
        allowed_tables: allowedTables,
        role,
      }),
    });

    if (data.success) {
      // Show the API key (only shown once)
      const keyDisplay = document.getElementById("new-app-key-display");
      const keyValue = document.getElementById("new-app-key-value");
      if (keyDisplay && keyValue) {
        keyValue.textContent = data.app.api_key;
        keyDisplay.style.display = "block";
      }

      // Clear form
      document.getElementById("new-app-id").value = "";
      document.getElementById("new-app-description").value = "";
      document.getElementById("new-app-role").value = "read";

      showToast(`App '${appId}' created successfully`, "success");
      loadApps();
    }
  } catch (e) {
    showToast(`Failed to create app: ${e.message}`, "error");
  }
}

// ── Edit App ────────────────────────────────────────────────

export async function editApp(appId) {
  try {
    const data = await api(`/apps/${encodeURIComponent(appId)}`);
    const app = data.app;
    if (!app) return;

    // Load schema tables for editing
    let tables = [];
    try {
      const schemaData = await api("/apps/schema/tables");
      tables = schemaData.tables || [];
    } catch {
      // Use app's own tables as fallback
      tables = app.allowed_tables || [];
    }

    // Build edit modal content
    const modal = document.createElement("div");
    modal.id = "app-edit-modal";
    modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px";
    modal.innerHTML = `
      <div style="background:var(--bg-card);border-radius:var(--radius-md);padding:24px;max-width:600px;width:100%;max-height:80vh;overflow-y:auto;border:1px solid var(--border-color)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <h3 style="color:var(--text-primary)">Edit App: ${escapeHtml(appId)}</h3>
          <button class="btn btn-outline btn-sm" onclick="closeEditModal()">✕</button>
        </div>

        <div class="form-group">
          <label>Description</label>
          <input id="edit-app-description" type="text" value="${escapeHtml(app.description || "")}" />
        </div>

        <div class="form-group" style="margin-top:12px">
          <label>Role</label>
          <select id="edit-app-role" style="padding:8px 12px;border:1px solid var(--border-color);border-radius:var(--radius-sm);font-size:14px;background:var(--bg-card);color:var(--text-primary)">
            <option value="read" ${app.role === "read" ? "selected" : ""}>🔒 Read Only</option>
            <option value="write" ${app.role === "write" ? "selected" : ""}>✏️ Read + Write</option>
          </select>
        </div>

        <div class="form-group" style="margin-top:12px">
          <label>Allowed Tables</label>
          <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:var(--bg-card);border:1px solid var(--border-color);border-bottom:none;border-radius:var(--radius-sm) var(--radius-sm) 0 0;margin-top:8px">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:500;font-size:13px;margin:0">
              <input type="checkbox" id="edit-select-all" onchange="document.querySelectorAll('.edit-table-cb').forEach(cb => cb.checked = this.checked)" />
              <span>Select All</span>
            </label>
            <span class="badge info" style="font-size:11px">${tables.length} tables</span>
          </div>
          <div style="max-height:280px;overflow-y:auto;border:1px solid var(--border-color);border-radius:0 0 var(--radius-sm) var(--radius-sm)">
            ${tables.sort((a, b) => a.localeCompare(b)).map((t) => `
              <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px 12px;border-bottom:1px solid var(--border-color);transition:background 0.15s;font-size:13px" onmouseover="this.style.background='var(--bg-card-hover)'" onmouseout="this.style.background='var(--bg-card)'">
                <input type="checkbox" class="edit-table-cb" value="${escapeHtml(t)}" ${(app.allowed_tables || []).includes(t) ? "checked" : ""} style="margin:0;flex-shrink:0" />
                <span style="color:var(--text-primary);flex:1">${escapeHtml(t)}</span>
              </label>`).join("")}
          </div>
        </div>

        <div style="display:flex;gap:8px;margin-top:16px">
          <button class="btn btn-primary" onclick="saveAppEdit('${escapeHtml(appId)}')">💾 Save Changes</button>
          <button class="btn btn-outline" onclick="closeEditModal()">Cancel</button>
        </div>
      </div>`;

    document.body.appendChild(modal);
  } catch (e) {
    showToast(`Failed to load app: ${e.message}`, "error");
  }
}

export function closeEditModal() {
  const modal = document.getElementById("app-edit-modal");
  if (modal) modal.remove();
}

export async function saveAppEdit(appId) {
  const description = document.getElementById("edit-app-description")?.value?.trim();
  const role = document.getElementById("edit-app-role")?.value;
  const allowedTables = Array.from(
    document.querySelectorAll(".edit-table-cb:checked")
  ).map((cb) => cb.value);

  try {
    await api(`/apps/${encodeURIComponent(appId)}`, {
      method: "PUT",
      body: JSON.stringify({
        description,
        role,
        allowed_tables: allowedTables,
      }),
    });
    closeEditModal();
    showToast(`App '${appId}' updated`, "success");
    loadApps();
  } catch (e) {
    showToast(`Failed to update: ${e.message}`, "error");
  }
}

// ── Delete App ──────────────────────────────────────────────

export async function deleteApp(appId) {
  if (!confirm(`Delete app '${appId}'? This cannot be undone.`)) return;

  try {
    await api(`/apps/${encodeURIComponent(appId)}`, { method: "DELETE" });
    showToast(`App '${appId}' deleted`, "success");
    loadApps();
  } catch (e) {
    showToast(`Failed to delete: ${e.message}`, "error");
  }
}

// ── Regenerate Key ──────────────────────────────────────────

export async function regenerateAppKey(appId) {
  if (!confirm(`Regenerate API key for '${appId}'? The old key will stop working immediately.`)) return;

  try {
    const data = await api(`/apps/${encodeURIComponent(appId)}/regenerate-key`, {
      method: "POST",
    });
    if (data.success) {
      const keyDisplay = document.getElementById("new-app-key-display");
      const keyValue = document.getElementById("new-app-key-value");
      if (keyDisplay && keyValue) {
        keyValue.textContent = data.api_key;
        keyDisplay.style.display = "block";
      }
      showToast(`New API key generated for '${appId}'`, "success");
      loadApps();
    }
  } catch (e) {
    showToast(`Failed to regenerate key: ${e.message}`, "error");
  }
}

// ── Toggle Active ───────────────────────────────────────────

export async function toggleApp(appId, enable) {
  try {
    await api(`/apps/${encodeURIComponent(appId)}`, {
      method: "PUT",
      body: JSON.stringify({ active: enable }),
    });
    showToast(`App '${appId}' ${enable ? "enabled" : "disabled"}`, "success");
    loadApps();
  } catch (e) {
    showToast(`Failed to update: ${e.message}`, "error");
  }
}

// ── Copy Key ────────────────────────────────────────────────

export function copyAppKey() {
  const keyEl = document.getElementById("new-app-key-value");
  if (keyEl && keyEl.textContent) {
    navigator.clipboard
      .writeText(keyEl.textContent)
      .then(() => showToast("API key copied to clipboard", "success"))
      .catch(() => showToast("Failed to copy", "error"));
  }
}
