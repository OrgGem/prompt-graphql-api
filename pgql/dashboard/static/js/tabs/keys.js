// pgql/dashboard/static/js/tabs/keys.js
// API Keys tab — provider management

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";
import { loadLLMConfig } from "./llm-config.js";

// Provider presets with defaults
export const PROVIDER_PRESETS = {
  openai:    { baseUrl: "https://api.openai.com",           model: "gpt-4o-mini",       needsKey: true,  showExtra: false },
  anthropic: { baseUrl: "https://api.anthropic.com",        model: "claude-3-haiku-20240307", needsKey: true,  showExtra: false },
  google:    { baseUrl: "https://generativelanguage.googleapis.com", model: "gemini-1.5-flash", needsKey: true, showExtra: false },
  groq:      { baseUrl: "https://api.groq.com/openai",     model: "llama-3.1-70b-versatile", needsKey: true, showExtra: false },
  mistral:   { baseUrl: "https://api.mistral.ai",          model: "mistral-small-latest", needsKey: true, showExtra: false },
  together:  { baseUrl: "https://api.together.xyz",        model: "meta-llama/Llama-3-70b-chat-hf", needsKey: true, showExtra: false },
  ollama:    { baseUrl: "http://localhost:11434",           model: "llama3",            needsKey: false, showExtra: true },
  lmstudio:  { baseUrl: "http://localhost:1234",            model: "local-model",       needsKey: false, showExtra: true },
  custom:    { baseUrl: "",                                 model: "",                  needsKey: true,  showExtra: true },
};

export function onProviderChange() {
  const sel = document.getElementById("new-key-provider");
  const provider = sel.value;
  const preset = PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.custom;
  const customPanel = document.getElementById("custom-provider-fields");
  const nameGroup = document.getElementById("custom-name-group");
  const hintEl = document.getElementById("base-url-hint");
  const keyInput = document.getElementById("new-key-value");

  // Show/hide the extended fields panel
  const showExtended = preset.showExtra || provider === "custom";
  customPanel.style.display = showExtended ? "block" : "none";

  // Show "Provider Name" only for truly custom
  nameGroup.style.display = provider === "custom" ? "block" : "none";

  // Pre-fill values
  if (showExtended) {
    document.getElementById("new-key-base-url").value = preset.baseUrl;
    document.getElementById("new-key-model").value = preset.model;
    document.getElementById("new-key-temperature").value = "0.7";
    document.getElementById("new-key-max-tokens").value = "4096";
  }

  // Update key placeholder
  if (!preset.needsKey) {
    keyInput.placeholder = "Optional — leave empty for local models";
  } else {
    keyInput.placeholder = "sk-...";
  }

  // Base URL hint
  if (hintEl) {
    const hints = {
      ollama: "Default: http://localhost:11434 — make sure Ollama is running",
      lmstudio: "Default: http://localhost:1234 — make sure LM Studio server is started",
      custom: "Enter the base URL of your OpenAI-compatible API endpoint",
    };
    hintEl.textContent = hints[provider] || "";
  }
}

export async function loadKeys() {
  try {
    const data = await api("/config/keys");
    const container = document.getElementById("keys-grid");
    container.innerHTML = "";

    for (const [provider, masked] of Object.entries(data.keys || {})) {
      // Try to get extra info for this provider
      const extraInfo = data.provider_details?.[provider] || {};
      const detailHtml = extraInfo.base_url
        ? `<div style="font-size:11px;color:var(--text-muted);margin-top:4px">${escapeHtml(extraInfo.base_url)}${extraInfo.model ? " · " + escapeHtml(extraInfo.model) : ""}</div>`
        : "";

      container.innerHTML += `
                <div class="key-card">
                    <div class="provider">🔑 ${escapeHtml(provider)}</div>
                    <div class="masked">${escapeHtml(masked || "Not set")}</div>
                    ${detailHtml}
                    <div class="actions" style="margin-top:8px">
                        <button class="btn btn-outline btn-sm" onclick="useAsLLM('${escapeHtml(provider)}')" title="Set as active LLM for chat">⚡ Use for Chat</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteKey('${escapeHtml(provider)}')">Remove</button>
                    </div>
                </div>`;
    }

    if (Object.keys(data.keys || {}).length === 0) {
      container.innerHTML =
        '<p style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:32px">No API keys configured yet</p>';
    }
  } catch (e) {
    showToast("Failed to load keys: " + e.message, "error");
  }
}

export async function addKey() {
  const providerSel = document.getElementById("new-key-provider").value;
  const apiKey = document.getElementById("new-key-value").value.trim();
  const preset = PROVIDER_PRESETS[providerSel] || PROVIDER_PRESETS.custom;

  // Determine the actual provider name
  let provider = providerSel;
  if (providerSel === "custom") {
    const customName = document.getElementById("new-key-custom-name").value.trim();
    if (!customName) return showToast("Provider name is required for custom providers", "error");
    provider = customName;
  }

  // For non-local providers, API key is required
  if (preset.needsKey && !apiKey) {
    return showToast("API key is required", "error");
  }

  // Collect extended params
  const showExtended = preset.showExtra || providerSel === "custom";
  const payload = { provider, api_key: apiKey || "none" };

  if (showExtended) {
    payload.base_url = document.getElementById("new-key-base-url").value.trim();
    payload.model = document.getElementById("new-key-model").value.trim();
    payload.temperature = document.getElementById("new-key-temperature").value.trim();
    payload.max_tokens = document.getElementById("new-key-max-tokens").value.trim();
  } else {
    // Use pre-known defaults from preset
    payload.base_url = preset.baseUrl;
    payload.model = preset.model;
  }

  try {
    await api("/config/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(`Added ${provider} provider`, "success");

    // Reset form
    document.getElementById("new-key-provider").value = "openai";
    document.getElementById("new-key-value").value = "";
    onProviderChange();
    loadKeys();
  } catch (e) {
    showToast(`Failed: ${e.message}`, "error");
  }
}

export async function useAsLLM(provider) {
  try {
    await api(`/config/keys/${provider}/activate`, { method: "POST" });
    showToast(`${provider} set as active LLM for chat`, "success");
    loadLLMConfig();
  } catch (e) {
    showToast(`Failed: ${e.message}`, "error");
  }
}

export async function deleteKey(provider) {
  if (!confirm(`Remove ${provider} API key?`)) return;
  try {
    await api(`/config/keys/${provider}`, { method: "DELETE" });
    showToast(`Removed ${provider}`, "success");
    loadKeys();
  } catch (e) {
    showToast(`Failed: ${e.message}`, "error");
  }
}
