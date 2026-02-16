// pgql/dashboard/static/js/tabs/rules.js
// Rules tab — rate limiting and cache management

import { api } from "../api.js";
import { showToast } from "../utils.js";

export async function loadRules() {
  try {
    const [rl, cache] = await Promise.all([
      api("/config/rate-limit"),
      api("/config/cache"),
    ]);

    document.getElementById("rl-rate").value = rl.rate;
    document.getElementById("rl-per").value = rl.per_seconds;
    document.getElementById("rl-desc").textContent = rl.description;

    document.getElementById("cache-hits").textContent = cache.hits ?? 0;
    document.getElementById("cache-misses").textContent = cache.misses ?? 0;
    document.getElementById("cache-size").textContent = cache.size ?? 0;
  } catch (e) {
    showToast("Failed to load rules: " + e.message, "error");
  }
}

export async function updateRateLimit() {
  const rate = parseInt(document.getElementById("rl-rate").value);
  const per = parseInt(document.getElementById("rl-per").value);
  if (isNaN(rate) || isNaN(per)) return showToast("Invalid values", "error");

  try {
    await api("/config/rate-limit", {
      method: "PUT",
      body: JSON.stringify({ rate, per }),
    });
    showToast("Rate limit updated", "success");
    loadRules();
  } catch (e) {
    showToast(`Failed: ${e.message}`, "error");
  }
}

export async function clearCache() {
  try {
    await api("/config/cache/clear", { method: "POST" });
    showToast("Cache cleared", "success");
    loadRules();
  } catch (e) {
    showToast(`Failed: ${e.message}`, "error");
  }
}
