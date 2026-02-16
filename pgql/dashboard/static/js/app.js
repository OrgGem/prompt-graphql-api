// pgql/dashboard/static/js/app.js
// Entry point — ES Module that imports all tab modules and wires navigation

// --- Core imports ---
import { logout } from "./api.js";
import { showToast, togglePasswordVisibility } from "./utils.js";

// --- Tab imports ---
import { loadOverview, updateConfigBadge } from "./tabs/overview.js";
import { loadConfig, updateConfig, generateApiKey } from "./tabs/config.js";
import { loadLLMConfig, saveLLMConfig, onLLMProviderChange } from "./tabs/llm-config.js";
import { loadKeys, addKey, deleteKey, useAsLLM, onProviderChange } from "./tabs/keys.js";
import { loadMonitoring } from "./tabs/monitoring.js";
import { loadRules, updateRateLimit, clearCache } from "./tabs/rules.js";
import { loadChat, sendChat, clearChat } from "./tabs/chat.js";
import {
  loadApps, reloadSchema, loadSchemaCache, toggleAllTables,
  createApp, editApp, closeEditModal, saveAppEdit,
  deleteApp, regenerateAppKey, toggleApp, copyAppKey,
} from "./tabs/apps.js";
import {
  loadStyle, saveTheme, resetTheme, previewColor, previewFont,
  uploadLogo, removeLogo, uploadFavicon, removeFavicon, initTheme,
} from "./tabs/style.js";

// --- State ---
let currentTab = "overview";
let refreshInterval = null;

// --- Expose functions to HTML onclick handlers ---
// (ES Modules don't pollute global scope, so we bind explicitly)
window.switchTab = switchTab;
window.refreshData = refreshData;
window.logout = logout;

// Config tab
window.loadConfig = loadConfig;
window.updateConfig = updateConfig;
window.generateApiKey = generateApiKey;
window.togglePasswordVisibility = togglePasswordVisibility;

// LLM Config
window.saveLLMConfig = saveLLMConfig;
window.onLLMProviderChange = onLLMProviderChange;

// Monitoring tab
window.loadMonitoring = loadMonitoring;

// API Keys tab
window.addKey = addKey;
window.deleteKey = deleteKey;
window.useAsLLM = useAsLLM;
window.onProviderChange = onProviderChange;

// Rules tab
window.updateRateLimit = updateRateLimit;
window.clearCache = clearCache;

// Chat tab
window.sendChat = sendChat;
window.clearChat = clearChat;

// Apps tab
window.loadApps = loadApps;
window.reloadSchema = reloadSchema;
window.toggleAllTables = toggleAllTables;
window.createApp = createApp;
window.editApp = editApp;
window.closeEditModal = closeEditModal;
window.saveAppEdit = saveAppEdit;
window.deleteApp = deleteApp;
window.regenerateAppKey = regenerateAppKey;
window.toggleApp = toggleApp;
window.copyAppKey = copyAppKey;

// API Docs tab switcher
window.showApiDoc = function(lang) {
  document.querySelectorAll('.api-doc-content').forEach(d => d.style.display = 'none');
  document.querySelectorAll('.api-doc-tab').forEach(b => b.classList.remove('active'));
  const content = document.getElementById(`api-doc-${lang}`);
  const btn = document.querySelector(`.api-doc-tab[data-lang="${lang}"]`);
  if (content) content.style.display = 'block';
  if (btn) btn.classList.add('active');
};

// Style tab
window.loadStyle = loadStyle;
window.saveTheme = saveTheme;
window.resetTheme = resetTheme;
window.previewColor = previewColor;
window.previewFont = previewFont;
window.uploadLogo = uploadLogo;
window.removeLogo = removeLogo;
window.uploadFavicon = uploadFavicon;
window.removeFavicon = removeFavicon;

// --- Init ---
document.addEventListener("DOMContentLoaded", () => {
  initTheme();  // Apply saved theme before anything renders
  initNavigation();
  loadOverview();
  startAutoRefresh();
});

// --- Navigation ---
function initNavigation() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      const tab = item.dataset.tab;
      switchTab(tab);
    });
  });
}

function switchTab(tab) {
  currentTab = tab;
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.remove("active"));
  document.querySelector(`[data-tab="${tab}"]`).classList.add("active");
  document
    .querySelectorAll(".tab-content")
    .forEach((c) => c.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");

  const loaders = {
    overview: loadOverview,
    config: () => { loadConfig(); loadLLMConfig(); },
    keys: loadKeys,
    monitoring: loadMonitoring,
    rules: loadRules,
    apps: () => { loadApps(); loadSchemaCache(); },
    chat: () => { loadChat(); loadLLMConfig(); },
    style: loadStyle,
  };
  if (loaders[tab]) loaders[tab]();
}

// --- Auto Refresh ---
function startAutoRefresh(interval = 10000) {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    if (currentTab === "overview") loadOverview();
    if (currentTab === "monitoring") loadMonitoring();
  }, interval);
}

// --- Refresh handler ---
function refreshData() {
  const loaders = {
    overview: loadOverview,
    config: loadConfig,
    keys: loadKeys,
    monitoring: loadMonitoring,
    rules: loadRules,
    apps: loadApps,
    chat: loadChat,
    style: loadStyle,
  };
  if (loaders[currentTab]) loaders[currentTab]();
  updateConfigBadge();
  showToast("Refreshed", "success");
}
