import "../assets/modulepreload-polyfill-DaKOjhqt.js";
import { e as errMsg, S as STORAGE_KEYS, a as DEFAULT_API_ENDPOINT, D as DEFAULT_API_KEY, c as escapeHtml, n as normalizeEndpoint } from "../assets/utils-CUEHBwO0.js";
function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`缺少节点 #${id}`);
  return el;
}
const $input = (id) => $(id);
async function load() {
  const res = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.AUTO_COLLECT,
    STORAGE_KEYS.API_ENDPOINT,
    STORAGE_KEYS.API_KEY,
    STORAGE_KEYS.MASK_SHOP,
    STORAGE_KEYS.MASK_USER,
    STORAGE_KEYS.OBSERVATIONS
  ]);
  $input("ck-consent").checked = res[STORAGE_KEYS.CONSENT] === true;
  $input("ck-auto-collect").checked = res[STORAGE_KEYS.AUTO_COLLECT] === true;
  $input("inp-endpoint").value = normalizeEndpoint(res[STORAGE_KEYS.API_ENDPOINT]);
  $input("inp-apikey").value = typeof res[STORAGE_KEYS.API_KEY] === "string" && res[STORAGE_KEYS.API_KEY] ? res[STORAGE_KEYS.API_KEY] : DEFAULT_API_KEY;
  $input("ck-mask-shop").checked = res[STORAGE_KEYS.MASK_SHOP] !== false;
  $input("ck-mask-user").checked = res[STORAGE_KEYS.MASK_USER] !== false;
  renderHistory(
    Array.isArray(res[STORAGE_KEYS.OBSERVATIONS]) ? res[STORAGE_KEYS.OBSERVATIONS] : []
  );
}
async function save() {
  await chrome.storage.local.set({
    [STORAGE_KEYS.CONSENT]: $input("ck-consent").checked,
    [STORAGE_KEYS.AUTO_COLLECT]: $input("ck-auto-collect").checked,
    [STORAGE_KEYS.API_ENDPOINT]: $input("inp-endpoint").value.trim() || DEFAULT_API_ENDPOINT,
    [STORAGE_KEYS.API_KEY]: $input("inp-apikey").value.trim() || DEFAULT_API_KEY,
    [STORAGE_KEYS.MASK_SHOP]: $input("ck-mask-shop").checked,
    [STORAGE_KEYS.MASK_USER]: $input("ck-mask-user").checked
  });
  const hint = $("saved-hint");
  hint.textContent = "✓ 已保存";
  window.setTimeout(() => {
    hint.textContent = "";
  }, 2e3);
}
function renderHistory(list) {
  $("history-count").textContent = `本地共 ${list.length} 条观测记录（最多保留 500 条，溢出滚动删除最早记录）`;
  if (list.length === 0) {
    $("history-list").innerHTML = '<div class="muted">暂无记录</div>';
    return;
  }
  const rows = list.slice(0, 10).map((r) => {
    const time = new Date(r.collectedAt).toLocaleString("zh-CN");
    const status = r.uploadStatus === "success" ? "✅ 已上报" : r.uploadStatus === "failed" ? "⚠️ 上报失败" : r.uploadStatus === "skipped_no_price" ? "⏭️ 无价格未上报" : "⏳ 待上报";
    return `<div class="row">${escapeHtml(time)} · ${escapeHtml(r.platform)} · ${escapeHtml(
      r.productName ?? "(未取到商品名)"
    )} · ${status}</div>`;
  }).join("");
  $("history-list").innerHTML = rows + (list.length > 10 ? `<div class="muted">… 其余 ${list.length - 10} 条见「数据报告」页</div>` : "");
}
async function clearHistory() {
  if (!window.confirm("确定清空全部历史观测记录吗？该操作不可恢复。")) return;
  await chrome.storage.local.set({ [STORAGE_KEYS.OBSERVATIONS]: [] });
  renderHistory([]);
}
function main() {
  void load();
  $("btn-save").addEventListener("click", () => void save().catch((e) => window.alert(errMsg(e))));
  $("ck-consent").addEventListener("change", () => void save());
  $("ck-auto-collect").addEventListener("change", () => void save());
  $("btn-clear").addEventListener("click", () => void clearHistory());
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (STORAGE_KEYS.CONSENT in changes) {
      $input("ck-consent").checked = changes[STORAGE_KEYS.CONSENT].newValue === true;
    }
    if (STORAGE_KEYS.AUTO_COLLECT in changes) {
      $input("ck-auto-collect").checked = changes[STORAGE_KEYS.AUTO_COLLECT].newValue === true;
    }
  });
}
main();
