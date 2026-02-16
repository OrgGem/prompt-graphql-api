// pgql/dashboard/static/js/tabs/style.js
// Theme customization — colors, fonts, branding

import { api } from "../api.js";
import { showToast } from "../utils.js";

// CSS variable mapping: theme JSON key → CSS custom property
const COLOR_MAP = {
  accent:         "--accent",
  accent_hover:   "--accent-hover",
  accent_light:   "--accent-light",
  bg_primary:     "--bg-primary",
  bg_secondary:   "--bg-secondary",
  bg_card:        "--bg-card",
  bg_input:       "--bg-input",
  bg_sidebar:     "--bg-sidebar",
  text_primary:   "--text-primary",
  text_secondary: "--text-secondary",
  text_muted:     "--text-muted",
  success:        "--success",
  warning:        "--warning",
  error:          "--error",
  info:           "--info",
};

// Friendly labels for the color pickers
const COLOR_LABELS = {
  accent:         "🎨 Accent",
  accent_hover:   "🎨 Accent Hover",
  accent_light:   "🎨 Accent Light",
  bg_primary:     "📐 Background",
  bg_secondary:   "📐 Surface",
  bg_card:        "📐 Card",
  bg_input:       "📐 Input",
  bg_sidebar:     "📐 Sidebar",
  text_primary:   "✏️ Text Primary",
  text_secondary: "✏️ Text Secondary",
  text_muted:     "✏️ Text Muted",
  success:        "✅ Success",
  warning:        "⚠️ Warning",
  error:          "❌ Error",
  info:           "ℹ️ Info",
};

// Current theme state
let _currentTheme = null;

/**
 * Apply theme colors + font to the live page via CSS variables.
 */
function applyThemeToPage(theme) {
  const root = document.documentElement;

  // Apply colors
  if (theme.colors) {
    for (const [key, cssVar] of Object.entries(COLOR_MAP)) {
      const val = theme.colors[key];
      if (val) root.style.setProperty(cssVar, val);
    }
  }

  // Apply font
  if (theme.font) {
    // Load Google Font dynamically
    const fontLink = document.getElementById("theme-font-link");
    const fontUrl = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(theme.font)}:wght@300;400;500;600;700&display=swap`;
    if (fontLink) {
      fontLink.href = fontUrl;
    } else {
      const link = document.createElement("link");
      link.id = "theme-font-link";
      link.rel = "stylesheet";
      link.href = fontUrl;
      document.head.appendChild(link);
    }
    root.style.setProperty("font-family", `"${theme.font}", system-ui, -apple-system, sans-serif`);
    document.body.style.fontFamily = `"${theme.font}", system-ui, -apple-system, sans-serif`;
  }

  // Apply branding
  const logoIcon = document.querySelector(".logo-icon");
  const logoTitle = document.querySelector(".sidebar-logo h1");
  if (theme.logo_base64 && logoIcon) {
    logoIcon.innerHTML = `<img src="${theme.logo_base64}" alt="Logo" style="width:28px;height:28px;border-radius:6px;object-fit:cover">`;
  } else if (theme.logo_text && logoIcon) {
    logoIcon.textContent = theme.logo_text;
  }
  if (theme.app_name && logoTitle) {
    logoTitle.textContent = theme.app_name;
  }
}

/**
 * Load theme from API and render the editor.
 */
export async function loadStyle() {
  try {
    const data = await api("/config/theme");
    _currentTheme = data.theme;
    const defaults = data.defaults;
    const fonts = data.available_fonts || [];

    // Apply theme to page
    applyThemeToPage(_currentTheme);

    // Render color pickers
    const colorsGrid = document.getElementById("style-colors-grid");
    if (colorsGrid) {
      colorsGrid.innerHTML = Object.entries(COLOR_LABELS).map(([key, label]) => {
        const value = _currentTheme.colors[key] || defaults.colors[key] || "#000000";
        return `
          <div class="style-color-item">
            <label>${label}</label>
            <div style="display:flex;align-items:center;gap:8px">
              <input type="color" id="color-${key}" value="${value}"
                     onchange="previewColor('${key}', this.value)"
                     style="width:40px;height:32px;border:1px solid var(--border-color);border-radius:var(--radius-sm);cursor:pointer;padding:2px">
              <input type="text" id="color-text-${key}" value="${value}"
                     onchange="previewColor('${key}', this.value)"
                     style="width:80px;font-family:monospace;font-size:12px;padding:4px 8px;border:1px solid var(--border-color);border-radius:var(--radius-sm);background:var(--bg-input);color:var(--text-primary)">
            </div>
          </div>
        `;
      }).join("");
    }

    // Render font selector
    const fontSelect = document.getElementById("style-font-select");
    if (fontSelect) {
      fontSelect.innerHTML = fonts.map(f =>
        `<option value="${f}" ${f === _currentTheme.font ? "selected" : ""}>${f}</option>`
      ).join("");
    }

    // Render branding fields
    const appNameInput = document.getElementById("style-app-name");
    if (appNameInput) appNameInput.value = _currentTheme.app_name || "";

    const logoTextInput = document.getElementById("style-logo-text");
    if (logoTextInput) logoTextInput.value = _currentTheme.logo_text || "";

    // Render logo preview
    const logoPreview = document.getElementById("style-logo-preview");
    if (logoPreview) {
      if (_currentTheme.logo_base64) {
        logoPreview.innerHTML = `<img src="${_currentTheme.logo_base64}" alt="Logo" style="width:64px;height:64px;border-radius:10px;object-fit:cover;border:2px solid var(--border-color)">`;
      } else {
        logoPreview.innerHTML = `<div style="width:64px;height:64px;border-radius:10px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:22px">${_currentTheme.logo_text || "PQ"}</div>`;
      }
    }

    // Render favicon preview
    const faviconPreview = document.getElementById("style-favicon-preview");
    if (faviconPreview) {
      if (_currentTheme.favicon_base64) {
        faviconPreview.innerHTML = `<img src="${_currentTheme.favicon_base64}" alt="Favicon" style="width:28px;height:28px;object-fit:contain">`;
      } else {
        faviconPreview.innerHTML = `<svg viewBox="0 0 32 32" width="28" height="28"><rect width="32" height="32" rx="8" fill="var(--accent)"/><text x="16" y="22" font-family="system-ui" font-size="16" font-weight="700" fill="#fff" text-anchor="middle">PQ</text></svg>`;
      }
    }

  } catch (e) {
    console.error("Failed to load theme:", e);
    showToast("Failed to load theme", "error");
  }
}

/**
 * Live preview a color change.
 */
export function previewColor(key, value) {
  // Sync color picker and text input
  const picker = document.getElementById(`color-${key}`);
  const text = document.getElementById(`color-text-${key}`);
  if (picker && picker.value !== value) picker.value = value;
  if (text && text.value !== value) text.value = value;

  // Apply to page immediately
  const cssVar = COLOR_MAP[key];
  if (cssVar) {
    document.documentElement.style.setProperty(cssVar, value);
  }
}

/**
 * Preview font change.
 */
export function previewFont() {
  const fontSelect = document.getElementById("style-font-select");
  if (!fontSelect) return;
  const font = fontSelect.value;
  // Load font
  let link = document.getElementById("theme-font-link");
  const fontUrl = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(font)}:wght@300;400;500;600;700&display=swap`;
  if (!link) {
    link = document.createElement("link");
    link.id = "theme-font-link";
    link.rel = "stylesheet";
    document.head.appendChild(link);
  }
  link.href = fontUrl;
  document.documentElement.style.setProperty("font-family", `"${font}", system-ui, sans-serif`);
  document.body.style.fontFamily = `"${font}", system-ui, sans-serif`;
}

/**
 * Handle logo file upload → base64.
 */
export function uploadLogo() {
  const input = document.getElementById("style-logo-upload");
  if (!input || !input.files.length) return;

  const file = input.files[0];
  if (file.size > 200 * 1024) {
    showToast("Logo file too large (max 200KB)", "error");
    return;
  }
  if (!file.type.startsWith("image/")) {
    showToast("Please select an image file", "error");
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target.result;
    // Preview immediately
    const preview = document.getElementById("style-logo-preview");
    if (preview) {
      preview.innerHTML = `<img src="${base64}" alt="Logo" style="width:64px;height:64px;border-radius:10px;object-fit:cover;border:2px solid var(--border-color)">`;
    }
    // Update sidebar live
    const logoIcon = document.querySelector(".logo-icon");
    if (logoIcon) {
      logoIcon.innerHTML = `<img src="${base64}" alt="Logo" style="width:28px;height:28px;border-radius:6px;object-fit:cover">`;
    }
    // Store for save
    if (_currentTheme) _currentTheme.logo_base64 = base64;
  };
  reader.readAsDataURL(file);
}

/**
 * Remove custom logo.
 */
export function removeLogo() {
  if (_currentTheme) _currentTheme.logo_base64 = null;
  const preview = document.getElementById("style-logo-preview");
  const logoText = _currentTheme?.logo_text || "PQ";
  if (preview) {
    preview.innerHTML = `<div style="width:64px;height:64px;border-radius:10px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:22px">${logoText}</div>`;
  }
  const logoIcon = document.querySelector(".logo-icon");
  if (logoIcon) logoIcon.textContent = logoText;
}

/**
 * Save all theme settings to server.
 */
export async function saveTheme() {
  try {
    // Collect all color values
    const colors = {};
    for (const key of Object.keys(COLOR_MAP)) {
      const picker = document.getElementById(`color-${key}`);
      if (picker) colors[key] = picker.value;
    }

    const fontSelect = document.getElementById("style-font-select");
    const appNameInput = document.getElementById("style-app-name");
    const logoTextInput = document.getElementById("style-logo-text");

    const payload = {
      colors,
      font: fontSelect?.value || "Inter",
      app_name: appNameInput?.value?.trim() || "PromptQL",
      logo_text: logoTextInput?.value?.trim() || "PQ",
      logo_base64: _currentTheme?.logo_base64 || "",
      favicon_base64: _currentTheme?.favicon_base64 || "",
    };

    await api("/config/theme", {
      method: "PUT",
      body: JSON.stringify(payload),
    });

    showToast("Theme saved successfully!", "success");
  } catch (e) {
    console.error("Failed to save theme:", e);
    showToast("Failed to save theme: " + e.message, "error");
  }
}

/**
 * Reset theme to defaults.
 */
export async function resetTheme() {
  if (!confirm("Reset theme to defaults? This will remove all customizations.")) return;
  try {
    await api("/config/theme", { method: "DELETE" });
    // Remove inline CSS variable overrides
    const root = document.documentElement;
    for (const cssVar of Object.values(COLOR_MAP)) {
      root.style.removeProperty(cssVar);
    }
    root.style.removeProperty("font-family");
    document.body.style.fontFamily = "";
    // Remove custom font link
    const fontLink = document.getElementById("theme-font-link");
    if (fontLink) fontLink.remove();
    // Reload to apply defaults
    await loadStyle();
    showToast("Theme reset to defaults", "success");
  } catch (e) {
    showToast("Failed to reset theme: " + e.message, "error");
  }
}

// Apply theme on initial page load (before tab render)
export async function initTheme() {
  try {
    const data = await api("/config/theme");
    if (data.theme) applyThemeToPage(data.theme);
  } catch (e) {
    // Silently fail — use CSS defaults
    console.warn("Could not load theme on init:", e);
  }
}

/**
 * Upload favicon file → base64, preview + update browser tab.
 */
export function uploadFavicon() {
  const input = document.getElementById("style-favicon-upload");
  if (!input || !input.files.length) return;
  const file = input.files[0];
  if (file.size > 200 * 1024) {
    showToast("Favicon too large (max 200KB)", "error");
    return;
  }
  if (!file.type.startsWith("image/")) {
    showToast("Please select an image file", "error");
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target.result;
    if (_currentTheme) _currentTheme.favicon_base64 = base64;
    // Update preview
    const preview = document.getElementById("style-favicon-preview");
    if (preview) preview.innerHTML = `<img src="${base64}" alt="Favicon" style="width:28px;height:28px;object-fit:contain">`;
    // Update browser tab icon
    const link = document.getElementById("favicon-link");
    if (link) link.href = base64;
  };
  reader.readAsDataURL(file);
}

/**
 * Remove custom favicon.
 */
export function removeFavicon() {
  if (_currentTheme) _currentTheme.favicon_base64 = null;
  const preview = document.getElementById("style-favicon-preview");
  if (preview) {
    preview.innerHTML = `<svg viewBox="0 0 32 32" width="28" height="28"><rect width="32" height="32" rx="8" fill="var(--accent)"/><text x="16" y="22" font-family="system-ui" font-size="16" font-weight="700" fill="#fff" text-anchor="middle">PQ</text></svg>`;
  }
  // Reset browser tab icon to default
  const link = document.getElementById("favicon-link");
  if (link) link.href = "/api/config/theme/favicon";
}
