// pgql/dashboard/static/js/tabs/llm-config.js
// LLM Configuration — select provider from LLM Providers tab

import { api } from "../api.js";
import { showToast, escapeHtml } from "../utils.js";

let availableProviders = [];

export async function loadLLMConfig() {
  try {
    // Load current LLM config
    const data = await api("/config");
    const llm = data.llm_config || {};
    const badge = document.getElementById("llm-status-badge");

    // Load available providers from keys endpoint
    const keysData = await api("/config/keys");
    // Backend returns {keys: {provider: maskedKey}, provider_details: {provider: {base_url, model}}}
    // Transform to array for the selector
    const keysDict = keysData.keys || {};
    const detailsDict = keysData.provider_details || {};
    availableProviders = Object.keys(keysDict).map(provider => ({
      id: provider,
      provider: provider,
      masked_key: keysDict[provider],
      base_url: detailsDict[provider]?.base_url || "",
      model: detailsDict[provider]?.model || "",
    }));

    // Populate provider selector
    const selector = document.getElementById("llm-provider-selector");
    if (selector) {
      selector.innerHTML = '<option value="">— No LLM (PromptQL only) —</option>';
      
      for (const provider of availableProviders) {
        const providerLabel = `${provider.provider} — ${provider.model || "default"}`;
        const isSelected = llm.llm_provider_id === provider.id;
        selector.innerHTML += `<option value="${escapeHtml(provider.id)}" ${isSelected ? "selected" : ""}>${escapeHtml(providerLabel)}</option>`;
      }
    }

    // Show details if provider is selected
    if (llm.llm_provider_id) {
      const provider = availableProviders.find(p => p.id === llm.llm_provider_id);
      if (provider) {
        showProviderDetails(provider);
        badge.className = "badge success";
        badge.textContent = `Using: ${provider.provider} — ${provider.model || "default"}`;
      } else {
        badge.className = "badge warning";
        badge.textContent = "Provider not found";
      }
    } else {
      hideProviderDetails();
      badge.className = "badge info";
      badge.textContent = "No LLM configured";
    }

    // Update chat mode badge
    const chatBadge = document.getElementById("chat-mode-badge");
    if (chatBadge) {
      if (llm.llm_provider_id) {
        const provider = availableProviders.find(p => p.id === llm.llm_provider_id);
        chatBadge.textContent = provider ? `LLM: ${provider.model || provider.provider}` : "LLM";
      } else if (data.configured) {
        chatBadge.textContent = "PromptQL";
      } else {
        chatBadge.textContent = "Not configured";
      }
    }
  } catch (e) {
    console.error("Failed to load LLM config:", e);
  }
}

function showProviderDetails(provider) {
  const detailsDiv = document.getElementById("llm-provider-details");
  if (!detailsDiv) return;

  document.getElementById("llm-detail-provider").textContent = provider.provider || "—";
  document.getElementById("llm-detail-base-url").textContent = provider.base_url || "—";
  document.getElementById("llm-detail-model").textContent = provider.model || "—";
  detailsDiv.style.display = "block";
}

function hideProviderDetails() {
  const detailsDiv = document.getElementById("llm-provider-details");
  if (detailsDiv) detailsDiv.style.display = "none";
}

export function onLLMProviderChange() {
  const selector = document.getElementById("llm-provider-selector");
  if (!selector) return;

  const providerId = selector.value;
  if (providerId) {
    const provider = availableProviders.find(p => p.id === providerId);
    if (provider) {
      showProviderDetails(provider);
    }
  } else {
    hideProviderDetails();
  }
}

export async function saveLLMConfig() {
  try {
    const selector = document.getElementById("llm-provider-selector");
    const providerId = selector ? selector.value : "";

    const payload = {
      llm_provider_id: providerId || null,
    };

    await api("/config/llm", {
      method: "PUT",
      body: JSON.stringify(payload),
    });

    showToast(providerId ? "LLM provider configured" : "LLM disabled", "success");
    loadLLMConfig();
  } catch (e) {
    showToast("Failed to save LLM config: " + e.message, "error");
  }
}
