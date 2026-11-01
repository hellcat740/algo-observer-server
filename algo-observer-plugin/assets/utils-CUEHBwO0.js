const MSG = {
  START_COLLECTION: "START_COLLECTION",
  EXTRACT_PAGE_DATA: "EXTRACT_PAGE_DATA",
  TEST_CONNECTION: "TEST_CONNECTION",
  AUTO_COLLECT: "AUTO_COLLECT",
  RETRY_FAILED: "RETRY_FAILED"
};
const STORAGE_KEYS = {
  CONSENT: "consent",
  AUTO_COLLECT: "autoCollect",
  API_ENDPOINT: "apiEndpoint",
  API_KEY: "apiKey",
  MASK_SHOP: "maskShopName",
  MASK_USER: "maskUserMarker",
  OBSERVATIONS: "observations",
  ANON_ID: "anonymousUserId",
  LAST_RESULT: "lastCollectionResult",
  /** 自动采集跨页面去重：{ [productId]: 时间戳 } */
  LAST_AUTO_COLLECT: "lastAutoCollect"
};
const DEFAULT_API_ENDPOINT = "https://algodiscriminatingcheck.cn/api/observations";
/** 已下线旧服务器的 origin：老版本存储过的端点统一迁移到新默认端点 */
const LEGACY_ENDPOINT_ORIGINS = ["https://algo-observer-server.vercel.app"];
function normalizeEndpoint(value) {
  const v = typeof value === "string" && value ? value : DEFAULT_API_ENDPOINT;
  try {
    if (LEGACY_ENDPOINT_ORIGINS.includes(new URL(v).origin)) return DEFAULT_API_ENDPOINT;
  } catch { /* 非法 URL 交由上层校验，此处不吞其他逻辑 */ }
  return v;
}
const DEFAULT_API_KEY = "ing_76b1aafdb8aa410c73c28139";
const MAX_LOCAL_RECORDS = 500;
function errMsg(e) {
  return e instanceof Error ? e.message : String(e);
}
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function maskText(text) {
  const t = text.trim();
  if (!t) return t;
  return `${t[0]}*`;
}
export {
  DEFAULT_API_KEY as D,
  MSG as M,
  STORAGE_KEYS as S,
  DEFAULT_API_ENDPOINT as a,
  normalizeEndpoint as n,
  MAX_LOCAL_RECORDS as b,
  escapeHtml as c,
  errMsg as e,
  maskText as m
};
