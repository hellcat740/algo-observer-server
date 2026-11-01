import { M as MSG, e as errMsg, S as STORAGE_KEYS, D as DEFAULT_API_KEY, a as DEFAULT_API_ENDPOINT, m as maskText, b as MAX_LOCAL_RECORDS, n as normalizeEndpoint } from "../assets/utils-CUEHBwO0.js";
const PLATFORM_CODE_MAP = {
  yangkeduo: "pinduoduo",
  pinduoduo: "pinduoduo",
  taobao: "taobao",
  tmall: "tmall",
  jd: "jd"
};
function isPeakHour(collectedAt) {
  const d = new Date(collectedAt);
  if (Number.isNaN(d.getTime())) return null;
  const h = d.getHours();
  return h >= 11 && h <= 13 || h >= 19 && h <= 23;
}
function snapshotToText(outerHTML) {
  return outerHTML.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, " ").trim().slice(0, 500);
}
function pickDomPriceText(record) {
  const snap = record.domSnapshots.find((s) => s.field === "price") ?? record.domSnapshots.find((s) => s.field === "finalPrice");
  if (!snap) return null;
  const text = snapshotToText(snap.outerHTML);
  return text || null;
}
function yuanToCents(yuan) {
  if (yuan === null || yuan === void 0) return null;
  return Math.round(yuan * 100);
}
function mapObservationToBackend(record, extVersion) {
  const couponType = record.price.couponType;
  const couponAmount = record.price.couponAmount;
  return {
    platform_code: PLATFORM_CODE_MAP[record.platform] ?? record.platform,
    product_id: record.productId,
    sku_id: record.skuId ?? null,
    selected_options: Array.isArray(record.selectedOptions) ? record.selectedOptions : [],
    product_name: record.productName,
    seller_id: record.shopId ?? record.shopName,
    // 优先真实店铺 ID；取不到回退店铺名（后端 schema 已冻结，seller_id 语义为「卖家标识」）
    product_url: record.productUrl,
    display_price_cents: yuanToCents(record.price.original),
    // 插件侧换算为整数分（见 yuanToCents 注释）
    actual_pay_price_cents: yuanToCents(record.price.final),
    currency: record.price.currency,
    discount_coupon_amount_cents: yuanToCents(couponAmount),
    promo_type: couponType,
    promo_label: couponType !== null && couponAmount !== null ? `${couponType}（减${couponAmount}元）` : couponType,
    is_login: record.userContext.isLoggedIn,
    membership_level: record.userContext.memberLevel,
    is_new_user: record.userContext.isNewUser,
    register_days: null,
    // 插件无法获取注册天数
    user_agent: record.device.userAgent,
    platform: record.device.platform,
    language: record.device.language,
    device_memory: record.device.deviceMemory,
    hardware_concurrency: record.device.hardwareConcurrency,
    screen_resolution: record.device.screenResolution,
    device_price_score_estimate: record.device.devicePriceIndex,
    ip_city: record.network.city,
    shipping_city: record.shipping.shipFromCityNormalized ?? record.shipping.shipFromCity,
    peak_hour: isPeakHour(record.collectedAt),
    stock_hint: null,
    // 插件未采集库存提示
    fetch_ts: record.collectedAt,
    dom_price_text: pickDomPriceText(record),
    source_code_version: extVersion,
    anonymous_id: record.anonymousUserId
  };
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if ((message == null ? void 0 : message.type) === MSG.START_COLLECTION) {
    void handleStartCollection(message.payload ?? {}, sender).then(sendResponse);
    return true;
  }
  if ((message == null ? void 0 : message.type) === MSG.AUTO_COLLECT) {
    void handleAutoCollect(message.payload ?? {}, sender).then(sendResponse);
    return true;
  }
  if ((message == null ? void 0 : message.type) === MSG.TEST_CONNECTION) {
    void handleTestConnection().then(sendResponse);
    return true;
  }
  if ((message == null ? void 0 : message.type) === MSG.RETRY_FAILED) {
    void handleRetryFailed().then(sendResponse);
    return true;
  }
  return false;
});
async function handleTestConnection() {
  const settings = await getSettings();
  let healthUrl;
  try {
    healthUrl = `${new URL(settings.apiEndpoint).origin}/health`;
  } catch {
    return { ok: false, detail: `API 端点格式无效：${settings.apiEndpoint}` };
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 3e3);
  try {
    const resp = await fetch(healthUrl, { signal: ctrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return { ok: true, detail: "已连通（数据库正常）" };
  } catch (e) {
    return { ok: false, detail: `无法连接 ${healthUrl}：${errMsg(e)}` };
  } finally {
    clearTimeout(timer);
  }
}
async function handleStartCollection(payload, sender) {
  const settings = await getSettings();
  if (!settings.consent && !payload.onceOnly) {
    return { ok: false, error: "no_consent：尚未获得采集授权" };
  }
  const tab = sender.tab ?? await getActiveTab();
  if (!(tab == null ? void 0 : tab.id)) return { ok: false, error: "未找到目标标签页" };
  return collectAndUpload(tab, "manual", settings);
}
const AUTO_COLLECT_DEDUP_MS = 10 * 60 * 1e3;
async function handleAutoCollect(payload, sender) {
  const settings = await getSettings();
  if (!settings.consent || !settings.autoCollect) {
    return { ok: false, error: "auto_collect_disabled：未授权或自动采集开关未打开" };
  }
  const tab = sender.tab;
  if (!(tab == null ? void 0 : tab.id)) return { ok: false, error: "未找到来源标签页" };
  const productId = typeof (payload == null ? void 0 : payload.productId) === "string" ? payload.productId : null;
  const variantKey = typeof (payload == null ? void 0 : payload.variantKey) === "string" ? payload.variantKey : productId;
  if (variantKey && await isRecentlyAutoCollected(variantKey)) {
    return { ok: false, error: "duplicate：该商品规格 10 分钟内已自动采集过" };
  }
  const result = await collectAndUpload(tab, "auto", settings);
  if (result.ok && variantKey) await markAutoCollected(variantKey);
  return result;
}
async function isRecentlyAutoCollected(productId) {
  const res = await chrome.storage.local.get(STORAGE_KEYS.LAST_AUTO_COLLECT);
  const map = res[STORAGE_KEYS.LAST_AUTO_COLLECT];
  if (!map || typeof map !== "object") return false;
  const ts = map[productId];
  return typeof ts === "number" && Date.now() - ts < AUTO_COLLECT_DEDUP_MS;
}
async function markAutoCollected(productId) {
  const res = await chrome.storage.local.get(STORAGE_KEYS.LAST_AUTO_COLLECT);
  const raw = res[STORAGE_KEYS.LAST_AUTO_COLLECT];
  const map = raw && typeof raw === "object" ? { ...raw } : {};
  map[productId] = Date.now();
  const trimmed = Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 200);
  await chrome.storage.local.set({ [STORAGE_KEYS.LAST_AUTO_COLLECT]: Object.fromEntries(trimmed) });
}
async function handleRetryFailed() {
  const settings = await getSettings();
  const res = await chrome.storage.local.get(STORAGE_KEYS.OBSERVATIONS);
  const list = Array.isArray(res[STORAGE_KEYS.OBSERVATIONS]) ? res[STORAGE_KEYS.OBSERVATIONS] : [];
  const failedIndexes = list.map((r, i) => r.uploadStatus === "failed" ? i : -1).filter((i) => i >= 0);
  let succeeded = 0;
  let failed = 0;
  let changed = false;
  for (const i of failedIndexes) {
    const record = list[i];
    const payload = mapObservationToBackend(record, chrome.runtime.getManifest().version);
    if (payload.display_price_cents === null) {
      list[i] = {
        ...record,
        uploadStatus: "skipped_no_price",
        uploadError: "未抓取到价格，已取消上报。页面可能未加载完成或选择器失效，请刷新重试"
      };
      failed++;
      changed = true;
      continue;
    }
    const upload = await uploadObservation(settings, payload);
    if (upload.status === "success") {
      const updated = {
        ...record,
        uploadStatus: "success",
        observationId: upload.observationId ?? record.observationId
      };
      delete updated.uploadError;
      if (upload.warnings && upload.warnings.length > 0) updated.uploadWarnings = upload.warnings;
      list[i] = updated;
      succeeded++;
    } else {
      list[i] = { ...record, uploadStatus: "failed", uploadError: upload.error };
      failed++;
    }
    changed = true;
  }
  if (changed) {
    await chrome.storage.local.set({ [STORAGE_KEYS.OBSERVATIONS]: list });
  }
  return { retried: failedIndexes.length, succeeded, failed };
}
async function collectAndUpload(tab, trigger, settings) {
  var _a;
  let page;
  try {
    const resp = await chrome.tabs.sendMessage(tab.id, { type: MSG.EXTRACT_PAGE_DATA });
    if (!(resp == null ? void 0 : resp.ok)) return { ok: false, error: (resp == null ? void 0 : resp.error) ?? "页面数据提取失败" };
    page = resp.data;
  } catch (e) {
    return { ok: false, error: `无法与页面通信（请确认当前是受支持平台的商品详情页，且页面已加载完成）：${errMsg(e)}` };
  }
  let screenshotDataUrl = null;
  let screenshotError;
  try {
    screenshotDataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  } catch (e) {
    screenshotError = errMsg(e);
  }
  const network = await lookupIpCity();
  const anonymousUserId = await ensureAnonymousUserId();
  const record = {
    recordId: crypto.randomUUID(),
    anonymousUserId,
    collectedAt: (/* @__PURE__ */ new Date()).toISOString(),
    platform: page.platform,
    productId: page.productId,
    skuId: page.skuId ?? null,
    selectedOptions: Array.isArray(page.selectedOptions) ? page.selectedOptions : [],
    productName: page.productName,
    shopName: page.shopName,
    shopId: page.shopId,
    productUrl: page.productUrl,
    price: page.price,
    userContext: {
      isLoggedIn: page.userContext.isLoggedIn,
      memberLevel: page.userContext.memberLevel,
      isNewUser: page.userContext.isNewUser,
      userMarkerMasked: page.userContext.userMarker,
      // 暂存原文，sanitize 时按设置打码
      evidence: page.userContext.evidence
    },
    device: page.device,
    network,
    shipping: page.shipping,
    screenshotDataUrl,
    screenshotError,
    domSnapshots: page.domSnapshots,
    extractionMeta: page.extractionMeta,
    uploadStatus: "pending",
    observationId: null
  };
  const safe = sanitizeRecord(record, settings);
  const backendPayload = mapObservationToBackend(safe, chrome.runtime.getManifest().version);
  if (backendPayload.display_price_cents === null) {
    safe.uploadStatus = "skipped_no_price";
    safe.uploadError = "未抓取到价格，已取消上报。页面可能未加载完成或选择器失效，请刷新重试";
  } else {
    const upload = await uploadObservation(settings, backendPayload);
    safe.uploadStatus = upload.status;
    if (upload.observationId !== void 0) safe.observationId = upload.observationId;
    if (upload.error) safe.uploadError = upload.error;
    if (upload.warnings && upload.warnings.length > 0) safe.uploadWarnings = upload.warnings;
  }
  await persistRecord(safe);
  const result = {
    ok: true,
    recordId: safe.recordId,
    platform: safe.platform,
    uploadStatus: safe.uploadStatus,
    uploadError: safe.uploadError,
    observationId: safe.observationId,
    warningCount: ((_a = safe.uploadWarnings) == null ? void 0 : _a.length) ?? 0,
    collectedAt: safe.collectedAt
  };
  await chrome.storage.local.set({ [STORAGE_KEYS.LAST_RESULT]: result });
  return result;
}
async function getSettings() {
  const res = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.AUTO_COLLECT,
    STORAGE_KEYS.API_ENDPOINT,
    STORAGE_KEYS.API_KEY,
    STORAGE_KEYS.MASK_SHOP,
    STORAGE_KEYS.MASK_USER
  ]);
  return {
    consent: res[STORAGE_KEYS.CONSENT] === true,
    autoCollect: res[STORAGE_KEYS.AUTO_COLLECT] === true,
    // 默认关闭
    apiEndpoint: normalizeEndpoint(res[STORAGE_KEYS.API_ENDPOINT]),
    apiKey: typeof res[STORAGE_KEYS.API_KEY] === "string" && res[STORAGE_KEYS.API_KEY] ? res[STORAGE_KEYS.API_KEY] : DEFAULT_API_KEY,
    maskShopName: res[STORAGE_KEYS.MASK_SHOP] !== false,
    // 默认开启脱敏
    maskUserMarker: res[STORAGE_KEYS.MASK_USER] !== false
    // 默认开启脱敏
  };
}
async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}
async function ensureAnonymousUserId() {
  const res = await chrome.storage.local.get(STORAGE_KEYS.ANON_ID);
  if (typeof res[STORAGE_KEYS.ANON_ID] === "string" && res[STORAGE_KEYS.ANON_ID]) {
    return res[STORAGE_KEYS.ANON_ID];
  }
  const id = crypto.randomUUID();
  await chrome.storage.local.set({ [STORAGE_KEYS.ANON_ID]: id });
  return id;
}
async function lookupIpCity() {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5e3);
  try {
    const resp = await fetch("https://ipapi.co/json/", { signal: ctrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const j = await resp.json();
    const str = (v) => typeof v === "string" && v ? v : null;
    return {
      ip: str(j.ip),
      city: str(j.city),
      region: str(j.region),
      country: str(j.country) ?? str(j.country_name),
      source: "ipapi.co"
    };
  } catch (e) {
    return {
      ip: null,
      city: null,
      region: null,
      country: null,
      source: `ipapi.co 查询失败（已降级为 null）：${errMsg(e)}`
    };
  } finally {
    clearTimeout(timer);
  }
}
function sanitizeRecord(r, s) {
  const safe = {
    recordId: r.recordId,
    anonymousUserId: r.anonymousUserId,
    collectedAt: r.collectedAt,
    platform: r.platform,
    productId: r.productId,
    skuId: r.skuId ?? null,
    selectedOptions: Array.isArray(r.selectedOptions) ? r.selectedOptions : [],
    productName: r.productName,
    shopName: r.shopName && s.maskShopName ? maskText(r.shopName) : r.shopName,
    shopId: r.shopId,
    productUrl: r.productUrl,
    price: {
      original: r.price.original,
      final: r.price.final,
      currency: r.price.currency,
      couponAmount: r.price.couponAmount,
      couponType: r.price.couponType
    },
    userContext: {
      isLoggedIn: r.userContext.isLoggedIn,
      memberLevel: r.userContext.memberLevel,
      isNewUser: r.userContext.isNewUser,
      userMarkerMasked: r.userContext.userMarkerMasked && s.maskUserMarker ? maskText(r.userContext.userMarkerMasked) : r.userContext.userMarkerMasked,
      evidence: r.userContext.evidence
    },
    device: {
      userAgent: r.device.userAgent,
      screenResolution: r.device.screenResolution,
      deviceMemory: r.device.deviceMemory,
      hardwareConcurrency: r.device.hardwareConcurrency,
      platform: r.device.platform,
      language: r.device.language,
      devicePriceIndex: r.device.devicePriceIndex
    },
    network: {
      ip: r.network.ip,
      city: r.network.city,
      region: r.network.region,
      country: r.network.country,
      source: r.network.source
    },
    shipping: {
      shipFromCity: r.shipping.shipFromCity,
      shipFromCityNormalized: r.shipping.shipFromCityNormalized ?? null
    },
    screenshotDataUrl: r.screenshotDataUrl,
    domSnapshots: r.domSnapshots.map((d) => ({ field: d.field, outerHTML: d.outerHTML })),
    uploadStatus: r.uploadStatus,
    observationId: r.observationId
  };
  if (r.extractionMeta) safe.extractionMeta = { ...r.extractionMeta };
  if (r.screenshotError) safe.screenshotError = r.screenshotError;
  return safe;
}
async function uploadObservation(settings, payload) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 1e4);
  try {
    const resp = await fetch(settings.apiEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // 本地 FastAPI 后端鉴权头（默认 dev-key-123，可在 options 页修改）
        "X-API-Key": settings.apiKey
      },
      body: JSON.stringify(payload),
      signal: ctrl.signal
    });
    if (!resp.ok) {
      let detail = "";
      try {
        const errBody = await resp.json();
        if (errBody && errBody.detail !== void 0) {
          detail = typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail);
        }
      } catch {
      }
      throw new Error(`HTTP ${resp.status}${detail ? `：${detail}` : ""}`);
    }
    const body = await resp.json().catch(() => ({}));
    const warnings = Array.isArray(body.warnings) ? body.warnings.map((w) => String(w)) : [];
    return {
      status: "success",
      observationId: body.observation_id ?? body.observationId ?? body.id ?? null,
      warnings
    };
  } catch (e) {
    return { status: "failed", error: translateUploadError(e, settings.apiEndpoint) };
  } finally {
    clearTimeout(timer);
  }
}
function translateUploadError(e, endpoint) {
  const msg = errMsg(e);
  let origin = endpoint;
  try {
    origin = new URL(endpoint).origin;
  } catch {
  }
  if (e instanceof TypeError || /failed to fetch|networkerror/i.test(msg)) {
    return `无法连接 ${origin}（后端未启动或网络不通），请先双击 启动本地服务.bat 启动后端`;
  }
  if (e instanceof DOMException && e.name === "AbortError" || /abort/i.test(msg)) {
    return `连接后端超时（10 秒无响应），请确认后端正常运行：${endpoint}`;
  }
  return msg;
}
async function persistRecord(record) {
  const key = STORAGE_KEYS.OBSERVATIONS;
  const res = await chrome.storage.local.get(key);
  const list = Array.isArray(res[key]) ? res[key] : [];
  list.unshift(record);
  while (list.length > MAX_LOCAL_RECORDS) list.pop();
  try {
    await chrome.storage.local.set({ [key]: list });
    return;
  } catch {
    list[0] = {
      ...record,
      screenshotDataUrl: null,
      screenshotError: `${record.screenshotError ? `${record.screenshotError}；` : ""}本地留存因配额限制未保存截图`
    };
  }
  while (list.length > 0) {
    try {
      await chrome.storage.local.set({ [key]: list });
      return;
    } catch {
      list.pop();
    }
  }
}
