// pgql/dashboard/static/js/tabs/chat.js
// Chat tab — send messages, handle LLM/PromptQL responses

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";

let chatConfigured = false;

export async function loadChat() {
  try {
    const config = await api("/config");
    chatConfigured = config.configured;
    document.getElementById("chat-not-configured").style.display = chatConfigured ? "none" : "block";
    document.getElementById("chat-container").style.display = chatConfigured ? "block" : "none";
    if (chatConfigured) {
      document.getElementById("chat-input").focus();
      // Load apps for selector
      await loadChatApps();
    }
  } catch (e) {
    document.getElementById("chat-not-configured").style.display = "block";
    document.getElementById("chat-container").style.display = "none";
  }
}

export async function loadChatApps() {
  try {
    const data = await api("/apps");
    const selector = document.getElementById("chat-app-selector");
    if (!selector) return;

    // Keep default option, add apps
    selector.innerHTML = '<option value="">Default (Config)</option>';
    
    const apps = data.apps || [];
    for (const app of apps) {
      if (app.active !== false) {
        const roleIcon = app.role === "write" ? "✏️" : "🔒";
        selector.innerHTML += `<option value="${escapeHtml(app.app_id)}">${roleIcon} ${escapeHtml(app.app_id)}</option>`;
      }
    }

    // Update badge on change
    selector.addEventListener("change", () => {
      const badge = document.getElementById("chat-app-badge");
      if (selector.value) {
        const app = apps.find(a => a.app_id === selector.value);
        if (app) {
          const roleText = app.role === "write" ? "Write" : "Read";
          badge.textContent = roleText;
          badge.style.background = app.role === "write" ? "var(--warning)" : "var(--success)";
          badge.style.color = "#fff";
        }
      } else {
        badge.textContent = "";
        badge.style.background = "var(--bg-input)";
      }
    });
  } catch (e) {
    console.error("Failed to load apps for chat:", e);
  }
}

export async function sendChat() {
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  const messagesDiv = document.getElementById("chat-messages");
  const sendBtn = document.getElementById("chat-send-btn");

  // Clear placeholder if first message
  if (messagesDiv.children.length === 1 && messagesDiv.children[0].style.textAlign === "center") {
    messagesDiv.innerHTML = "";
  }

  // Add user message
  messagesDiv.innerHTML += `
    <div style="align-self:flex-end;max-width:70%;padding:10px 14px;background:var(--accent);color:#fff;border-radius:var(--radius) var(--radius) 4px var(--radius);font-size:14px">
      ${escapeHtml(msg)}
    </div>`;

  input.value = "";
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";
  input.disabled = true;

  // Add loading indicator
  const loadingId = `loading-${Date.now()}`;
  messagesDiv.innerHTML += `
    <div id="${loadingId}" style="align-self:flex-start;max-width:70%;padding:10px 14px;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:var(--radius) var(--radius) var(--radius) 4px;font-size:14px;color:var(--text-muted)">
      <span style="animation:pulse 1s infinite">Thinking...</span>
    </div>`;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  try {
    const chatMode = document.getElementById("chat-mode") ? document.getElementById("chat-mode").value : "auto";
    const appId = document.getElementById("chat-app-selector") ? document.getElementById("chat-app-selector").value : "";
    
    const requestBody = { message: msg, mode: chatMode };
    if (appId) {
      requestBody.app_id = appId;
    }
    
    const data = await api("/chat", {
      method: "POST",
      body: JSON.stringify(requestBody),
    });

    // Remove loading indicator
    const loadingEl = document.getElementById(loadingId);
    if (loadingEl) loadingEl.remove();

    if (data.success) {
      let responseText = "(No response text)";
      const usedMode = data.mode || "unknown";

      if (usedMode === "llm") {
        // Direct LLM response
        responseText = data.content || "(Empty response)";
      } else {
        // PromptQL response
        const resp = data.response;
        if (resp && resp.assistant_actions) {
          const texts = resp.assistant_actions
            .filter(a => a.type === "text")
            .map(a => a.text);
          if (texts.length) responseText = texts.join("\n");
        } else if (typeof resp === "string") {
          responseText = resp;
        } else if (resp) {
          responseText = JSON.stringify(resp, null, 2);
        }
      }

      // Mode badge on the bubble
      const modeBadge = usedMode === "llm"
        ? `<span style="font-size:10px;background:var(--accent);color:#fff;padding:1px 6px;border-radius:8px;margin-right:6px">LLM</span>`
        : `<span style="font-size:10px;background:var(--info);color:#fff;padding:1px 6px;border-radius:8px;margin-right:6px">PromptQL</span>`;

      // Token usage for LLM
      let usageInfo = "";
      if (data.usage && data.usage.total_tokens) {
        usageInfo = `<div style="font-size:11px;color:var(--text-muted);margin-top:6px">Model: ${escapeHtml(data.model || "")} · Tokens: ${data.usage.total_tokens}</div>`;
      }

      messagesDiv.innerHTML += `
        <div style="align-self:flex-start;max-width:80%;padding:10px 14px;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:var(--radius) var(--radius) var(--radius) 4px;font-size:14px;color:var(--text-primary);white-space:pre-wrap;word-break:break-word">
          ${modeBadge}${escapeHtml(responseText)}${usageInfo}
        </div>`;
    } else {
      messagesDiv.innerHTML += `
        <div style="align-self:flex-start;max-width:80%;padding:10px 14px;background:var(--error-bg);border:1px solid var(--error-border);border-radius:var(--radius) var(--radius) var(--radius) 4px;font-size:14px;color:var(--error)">
          ⚠️ ${escapeHtml(data.error || "Unknown error")}${data.details ? "\n" + escapeHtml(data.details) : ""}
        </div>`;
    }
  } catch (e) {
    const loadingEl = document.getElementById(loadingId);
    if (loadingEl) loadingEl.remove();
    messagesDiv.innerHTML += `
      <div style="align-self:flex-start;max-width:80%;padding:10px 14px;background:var(--error-bg);border:1px solid var(--error-border);border-radius:var(--radius) var(--radius) var(--radius) 4px;font-size:14px;color:var(--error)">
        ⚠️ ${escapeHtml(e.message)}
      </div>`;
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send ➤";
    input.disabled = false;
    input.focus();
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }
}

export function clearChat() {
  document.getElementById("chat-messages").innerHTML = `
    <div style="text-align:center;color:var(--text-muted);font-size:13px;padding:32px">
      Send a message to chat. Mode: Auto (LLM if configured, else PromptQL)
    </div>`;
}
