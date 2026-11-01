import "../assets/modulepreload-polyfill-DaKOjhqt.js";
import { S as STORAGE_KEYS, c as escapeHtml } from "../assets/utils-CUEHBwO0.js";
const PLATFORM_NAMES = {
  taobao: "淘宝",
  tmall: "天猫",
  jd: "京东",
  pinduoduo: "拼多多",
  amazon: "亚马逊"
};
const platformName = (id) => PLATFORM_NAMES[id] ?? id;
function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`缺少节点 #${id}`);
  return el;
}
function avgBy(records, keyFn) {
  var _a;
  const groups = /* @__PURE__ */ new Map();
  for (const r of records) {
    const key = keyFn(r);
    const price = (_a = r.price) == null ? void 0 : _a.final;
    if (!key || price === null || price === void 0) continue;
    const g = groups.get(key) ?? { sum: 0, count: 0 };
    g.sum += price;
    g.count += 1;
    groups.set(key, g);
  }
  return [...groups.entries()].map(([label, g]) => ({ label, value: g.sum / g.count, count: g.count })).sort((a, b) => b.value - a.value);
}
function renderHBar(container, data, unit) {
  if (data.length === 0) {
    container.innerHTML = '<div class="sub">暂无可统计数据</div>';
    return;
  }
  const rowH = 32;
  const labelW = 110;
  const barMaxW = 520;
  const valW = 140;
  const max = Math.max(...data.map((d) => d.value), 1);
  const height = data.length * rowH;
  const rows = data.map((d, i) => {
    const w = Math.max(2, d.value / max * barMaxW);
    const y = i * rowH;
    return `
      <text x="0" y="${y + 19}" font-size="12" fill="#374151">${escapeHtml(d.label)}</text>
      <rect x="${labelW}" y="${y + 6}" width="${w}" height="18" rx="4" fill="#6366f1"></rect>
      <text x="${labelW + w + 8}" y="${y + 19}" font-size="12" fill="#111827">${unit}${d.value.toFixed(2)}（${d.count} 条）</text>`;
  }).join("");
  container.innerHTML = `<svg width="${labelW + barMaxW + valW}" height="${height}" viewBox="0 0 ${labelW + barMaxW + valW} ${height}" role="img">${rows}</svg>`;
}
function renderHistogram(container, values) {
  if (values.length === 0) {
    container.innerHTML = '<div class="sub">暂无可统计数据（需要同时取到原价与到手价）</div>';
    return;
  }
  const BIN = 8;
  const max = Math.max(...values, 1);
  const step = max / BIN;
  const bins = new Array(BIN).fill(0);
  for (const v of values) {
    const idx = Math.min(BIN - 1, Math.floor(v / step));
    bins[idx] += 1;
  }
  const W = 640;
  const H = 200;
  const padL = 34;
  const padB = 40;
  const padT = 10;
  const chartW = W - padL;
  const chartH = H - padB - padT;
  const maxCount = Math.max(...bins, 1);
  const bw = chartW / BIN;
  const bars = bins.map((c, i) => {
    const h = c / maxCount * chartH;
    const x = padL + i * bw;
    const y = padT + chartH - h;
    const lo = (i * step).toFixed(0);
    const hi = ((i + 1) * step).toFixed(0);
    return `
      <rect x="${x + 3}" y="${y}" width="${bw - 6}" height="${c > 0 ? Math.max(h, 2) : 0}" rx="3" fill="#0ea5e9"></rect>
      <text x="${x + bw / 2}" y="${y - 4}" font-size="11" text-anchor="middle" fill="#111827">${c > 0 ? c : ""}</text>
      <text x="${x + bw / 2}" y="${H - 24}" font-size="10" text-anchor="middle" fill="#6b7280">${lo}-${hi}</text>`;
  }).join("");
  container.innerHTML = `
    <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img">
      ${bars}
      <text x="${padL}" y="${H - 6}" font-size="11" fill="#6b7280">优惠金额区间（元）</text>
      <text x="4" y="${padT + 10}" font-size="11" fill="#6b7280">条数</text>
    </svg>`;
}
function renderCards(records) {
  const total = records.length;
  const success = records.filter((r) => r.uploadStatus === "success").length;
  const platforms = new Set(records.map((r) => r.platform)).size;
  const cities = new Set(records.map((r) => {
    var _a;
    return (_a = r.network) == null ? void 0 : _a.city;
  }).filter(Boolean)).size;
  $("cards").innerHTML = [
    { num: total, label: "总采集数" },
    { num: success, label: "上报成功数" },
    { num: platforms, label: "覆盖平台数" },
    { num: cities, label: "覆盖城市数" }
  ].map((c) => `<div class="card"><div class="num">${c.num}</div><div class="label">${c.label}</div></div>`).join("");
}
function renderTable(records) {
  const rows = records.slice(0, 50).map((r) => {
    var _a, _b, _c;
    const rawName = r.productName ?? "-";
    const name = rawName.length > 24 ? `${rawName.slice(0, 24)}…` : rawName;
    const price = ((_a = r.price) == null ? void 0 : _a.final) !== null && ((_b = r.price) == null ? void 0 : _b.final) !== void 0 ? `${r.price.currency === "USD" ? "$" : "¥"}${r.price.final.toFixed(2)}` : "-";
    const city = ((_c = r.network) == null ? void 0 : _c.city) ?? "-";
    const pill = r.uploadStatus === "success" ? '<span class="pill ok">已上报</span>' : r.uploadStatus === "failed" ? '<span class="pill fail">上报失败</span>' : r.uploadStatus === "skipped_no_price" ? '<span class="pill pending">无价格未上报</span>' : '<span class="pill pending">待上报</span>';
    return `<tr>
      <td>${escapeHtml(new Date(r.collectedAt).toLocaleString("zh-CN"))}</td>
      <td>${escapeHtml(platformName(r.platform))}</td>
      <td title="${escapeHtml(rawName)}">${escapeHtml(name)}</td>
      <td>${price}</td>
      <td>${escapeHtml(city)}</td>
      <td>${pill}</td>
    </tr>`;
  }).join("");
  $("detail-table").innerHTML = `<table>
    <thead><tr><th>时间</th><th>平台</th><th>商品</th><th>到手价</th><th>城市</th><th>上报状态</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>${records.length > 50 ? `<div class="sub">仅展示最近 50 条，共 ${records.length} 条</div>` : ""}`;
}
async function main() {
  const res = await chrome.storage.local.get(STORAGE_KEYS.OBSERVATIONS);
  const records = Array.isArray(res[STORAGE_KEYS.OBSERVATIONS]) ? res[STORAGE_KEYS.OBSERVATIONS] : [];
  const has = records.length > 0;
  $("empty").hidden = has;
  $("content").hidden = !has;
  if (!has) return;
  renderCards(records);
  renderHBar($("chart-platform"), avgBy(records, (r) => platformName(r.platform)), "¥");
  renderHBar($("chart-city"), avgBy(records, (r) => {
    var _a;
    return ((_a = r.network) == null ? void 0 : _a.city) ?? null;
  }).slice(0, 12), "¥");
  const discounts = records.map(
    (r) => {
      var _a, _b, _c, _d;
      return ((_a = r.price) == null ? void 0 : _a.original) !== null && ((_b = r.price) == null ? void 0 : _b.original) !== void 0 && ((_c = r.price) == null ? void 0 : _c.final) !== null && ((_d = r.price) == null ? void 0 : _d.final) !== void 0 ? r.price.original - r.price.final : null;
    }
  ).filter((v) => v !== null && v >= 0);
  renderHistogram($("chart-discount"), discounts);
  renderTable(records);
}
void main();
