(function () {
  "use strict";

  const SITE_KEY = "obs_user_id";
  const PLUGIN_KEY = "anonymousUserId";
  const UUID_RE = /^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$/;

  async function restoreDashboardIdentity() {
    try {
      const stored = await chrome.storage.local.get(PLUGIN_KEY);
      const pluginUid = stored[PLUGIN_KEY];
      if (typeof pluginUid !== "string" || !UUID_RE.test(pluginUid)) return;
      const normalizedUid = pluginUid.toLowerCase();
      // 每次刷新都以插件身份为准；已经一致时不写存储也不刷新，避免循环。
      if (localStorage.getItem(SITE_KEY) === normalizedUid) return;
      localStorage.setItem(SITE_KEY, normalizedUid);
      // 看板脚本可能已在异步读取插件存储期间启动，刷新确保所有请求使用同一身份。
      location.reload();
    } catch {
      // 站点存储不可用时保留原有看板流程，避免刷新循环。
    }
  }

  void restoreDashboardIdentity();
})();
