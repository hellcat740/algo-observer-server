import "../assets/modulepreload-polyfill-DaKOjhqt.js";
import { S as STORAGE_KEYS, M as MSG, e as errMsg, a as DEFAULT_API_ENDPOINT, c as escapeHtml, n as normalizeEndpoint } from "../assets/utils-CUEHBwO0.js";
const PLATFORM_RULES = [
  {
    id: "taobao",
    name: "淘宝",
    hostPatterns: [/(^|\.)taobao\.com$/],
    productIdPatterns: [/[?&]id=(\d{5,})/],
    selectors: {
      title: [
        'span[class*="mainTitle--"]',
        // 2025 版商品主标题内层 span（实测类名 mainTitle--哈希，文本干净）
        '[class*="MainTitle--"]',
        // 2025 版主标题容器（注意区别于 tabDetailItemTitle 评价页签）
        "#J_Title .tb-main-title",
        // 旧版详情页标题
        'h1[class*="main-title"]',
        // 新版详情页标题
        ".tb-item-info .tb-main-title",
        "#J_Title h3",
        'h1[class*="title"]'
      ],
      shopName: [
        'span[class*="shopName--"]',
        // 2025 版店铺名内层 span（带 title 属性，文本干净）
        ".tb-shop-name",
        '[class*="ShopName--"]',
        // 新版 CSS Modules 店铺名类名
        '[class*="shopName"]',
        '[class*="ShopName"]',
        ".tb-seller-info .shop-name",
        ".shop-name"
      ],
      price: [
        // 2025 版到手价/售价高亮容器（文本如「平台加补后￥3188.55」）
        // 注意：宽松选择器 [class*="Price--"] / span[class*="priceText"] 已移除——
        // 实测会抓到无关数字（如「48」），价格只允许来自明确容器；
        // 简化渲染（状态A）的 unit--+text-- 组合由 extract.ts 的 pickUnitTextPrice 处理。
        '[class*="highlightPrice--"]',
        ".tb-rmb-num",
        // 经典价格节点
        "#J_PromoPriceNum .tb-rmb-num",
        ".tb-property .tb-rmb-num"
      ],
      finalPrice: [
        '[class*="finalPrice"]',
        // 券后到手价（页面直接展示时）
        '[class*="FinalPrice"]',
        '[class*="couponPrice"]',
        ".tb-promo-price .tb-rmb-num",
        ".price-final"
      ],
      coupon: [
        '[class*="couponInfoArea--"]',
        // 2025 版优惠信息区（「已享受:官方立减38元…」）
        ".tb-coupon",
        '[class*="coupon"]',
        '[class*="Coupon--"]',
        ".coupon-amount",
        "#J_Coupon"
      ],
      originalPrice: [
        '[class*="subPrice--"]',
        // 2025 版原价容器（文本如「优惠前￥3799」；无优惠时该节点不存在）
        "#J_StrPrice .tb-rmb-num",
        // 划线价
        ".tb-cancel-price",
        '[class*="originPrice"]',
        'del[class*="price"]',
        ".origin-price"
      ],
      shippingCity: [
        '[class*="deliveryAddrWrap--"]',
        // 2025 版发货地容器（「浙江嘉兴 至 北京市 海淀区」）
        "#J-From",
        ".tb-location",
        '[class*="deliveryAddress"]',
        '[class*="deliver"]',
        ".tb-deliver-to"
      ],
      userMarker: [
        "#J_SiteNavLogin .site-nav-login-info-nick",
        // 顶部导航昵称
        ".site-nav-user",
        '[class*="nickname"]',
        '[class*="userNick"]',
        ".member-info"
      ]
    },
    loginCookieNames: ["unb", "_nk_"]
  },
  {
    id: "tmall",
    name: "天猫",
    hostPatterns: [/(^|\.)tmall\.com$/],
    productIdPatterns: [/[?&]id=(\d{5,})/],
    selectors: {
      title: [
        'span[class*="mainTitle--"]',
        // 2025 版商品主标题内层 span（实测类名 mainTitle--哈希，文本干净）
        '[class*="MainTitle--"]',
        // 2025 版主标题容器（注意区别于 tabDetailItemTitle 评价页签）
        ".tb-detail-hd h1",
        // 天猫详情页标题
        "#J_DetailMeta .tb-detail-hd h1",
        'h1[class*="main-title"]',
        '[class*="ItemTitle--"]',
        'h1[class*="title"]'
      ],
      shopName: [
        'span[class*="shopName--"]',
        // 2025 版店铺名内层 span（带 title 属性，文本干净）
        "#shopExtra .slogo-shopname",
        // 天猫店铺招牌
        ".slogo-shopname",
        '[class*="ShopName--"]',
        // 新版 CSS Modules 店铺名类名
        '[class*="shopName"]',
        ".shopLink",
        '[class*="ShopName"]'
      ],
      price: [
        // 2025 版到手价/售价高亮容器（淘宝天猫同版式）
        // 宽松选择器 [class*="Price--"] / span[class*="priceText"] 已移除（实测抓到无关数字）；
        // 简化渲染（状态A）的 unit--+text-- 组合由 extract.ts 的 pickUnitTextPrice 处理。
        '[class*="highlightPrice--"]',
        ".tm-price",
        // 天猫价
        ".tm-promo-price .tm-price",
        ".tb-rmb-num"
      ],
      finalPrice: [
        '[class*="finalPrice"]',
        '[class*="FinalPrice"]',
        '[class*="couponPrice"]',
        ".tm-promo-price .tm-price",
        ".price-final"
      ],
      coupon: [
        '[class*="couponInfoArea--"]',
        // 2025 版优惠信息区（「已享受:官方立减38元…」）
        ".tm-coupon",
        '[class*="coupon"]',
        '[class*="Coupon--"]',
        ".coupon-amount",
        ".tm-shop-coupon"
      ],
      originalPrice: [
        '[class*="subPrice--"]',
        // 2025 版原价容器（无优惠时该节点不存在）
        ".tm-yprice",
        // 天猫原价（划线价）
        ".tm-price-panel .tm-yprice",
        '[class*="originPrice"]',
        'del[class*="price"]',
        ".origin-price"
      ],
      shippingCity: [
        '[class*="deliveryAddrWrap--"]',
        // 2025 版发货地容器（「重庆 至 北京市 海淀区」）
        "#J-From",
        ".tm-location",
        '[class*="deliveryAddress"]',
        '[class*="deliver"]',
        '[class*="delivery"]'
      ],
      userMarker: [
        "#J_SiteNavLogin .site-nav-login-info-nick",
        ".site-nav-user",
        '[class*="nickname"]',
        '[class*="userNick"]',
        ".member-info"
      ]
    },
    loginCookieNames: ["unb", "_nk_"]
  },
  {
    id: "jd",
    name: "京东",
    hostPatterns: [/(^|\.)jd\.com$/],
    productIdPatterns: [
      /item\.jd\.com\/(\d+)\.html/,
      // 京东商品页：item.jd.com/<sku>.html
      /[?&]skuId=(\d+)/
    ],
    selectors: {
      title: [".sku-title-text", ".sku-title-name", "#name h1", ".sku-name", "#itemInfo #name h1", ".itemInfo-wrap .sku-name", 'h1[class*="sku"]'],
      shopName: [".top-shop-info .top-name-tag", ".top-shop-info", "#shopId", ".pop-shop-name", ".shopName", '[class*="shop-name"]', ".crumb-wrap .contact .name"],
      price: [".product-price--main", ".p-price .price", "#price .price", ".summary-price .price", "span.price", '[class*="priceJ"]'],
      finalPrice: ['[class*="finalPrice"]', ".summary-price .p-price .price", '[class*="couponPrice"]', ".p-price .price", '[class*="FinalPrice"]'],
      coupon: [".quan-item", "#coupon .quan", '[class*="coupon"]', ".youhui .quan-item", '[class*="Coupon"]'],
      originalPrice: ["#page_maprice", ".p-price del", '[class*="originPrice"]', "del.price", ".origin-price"],
      shippingCity: [".logistics-address-main", "#store-prompt", '[class*="sendAddress"]', "#summary .dd", '[class*="address"]', ".summary .dd"],
      userMarker: ["#ttbar-login .nickname", ".nickname", '[class*="userInfo"]', ".user-info", '[class*="userNick"]']
    },
    loginCookieNames: ["pin", "pt_pin", "pt_key"]
  },
  {
    id: "amazon",
    name: "亚马逊",
    hostPatterns: [/(^|\.)amazon\.com$/],
    productIdPatterns: [/\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:[/?]|$)/i],
    selectors: {},
    loginCookieNames: ["session-id", "session-token"]
  },
  {
    id: "pinduoduo",
    name: "拼多多",
    // 拼多多网页版（mobile.yangkeduo.com）页面结构改版频繁，
    // 以下选择器可能随改版失效，需要定期核对更新。
    hostPatterns: [/(^|\.)yangkeduo\.com$/],
    productIdPatterns: [
      /[?&]goods_id=(\d+)/,
      // 商品页参数 goods_id
      /[?&]goodsId=(\d+)/
    ],
    selectors: {
      title: [
        '[class*="goods-name"]',
        '[class*="goodsName"]',
        ".goods-name",
        'h1[class*="title"]',
        "h1"
      ],
      shopName: [
        '[class*="mall-name"]',
        // 拼多多店铺常称「店铺/商场」
        '[class*="mallName"]',
        '[class*="shopName"]',
        ".mall-name",
        '[class*="shop-name"]'
      ],
      price: [
        '[class*="goods-price"]',
        '[class*="goodsPrice"]',
        ".goods-price",
        '[class*="price"]',
        ".price"
      ],
      finalPrice: [
        '[class*="finalPrice"]',
        '[class*="goodsPrice"]',
        '[class*="couponPrice"]',
        ".goods-price",
        '[class*="price"]'
      ],
      coupon: [
        '[class*="coupon"]',
        '[class*="Coupon"]',
        ".coupon-amount",
        '[class*="discount"]',
        '[class*="quan"]'
      ],
      originalPrice: [
        '[class*="originPrice"]',
        '[class*="market-price"]',
        'del[class*="price"]',
        ".origin-price",
        "del"
      ],
      shippingCity: [
        '[class*="delivery"]',
        '[class*="deliver"]',
        '[class*="address"]',
        '[class*="shipping"]',
        '[class*="from"]'
      ],
      userMarker: [
        '[class*="user-name"]',
        '[class*="nickName"]',
        '[class*="userName"]',
        '[class*="avatar"]',
        '[class*="user-info"]'
      ]
    },
    loginCookieNames: ["pdd_user_id", "pdd_user_token"]
  }
];
function findPlatformRule(hostname) {
  for (const rule of PLATFORM_RULES) {
    if (rule.hostPatterns.some((re) => re.test(hostname))) return rule;
  }
  return null;
}
function extractProductId(rule, url) {
  for (const re of rule.productIdPatterns) {
    const m = url.match(re);
    if (m && m[1]) return m[1];
  }
  return null;
}
function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`缺少节点 #${id}`);
  return el;
}
async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}
function describePage(url) {
  if (!url) return "无法读取当前页地址";
  try {
    const u = new URL(url);
    const rule = findPlatformRule(u.hostname);
    if (!rule) return "非受支持平台（支持：淘宝 / 天猫 / 京东 / 拼多多 / 亚马逊）";
    const pid = extractProductId(rule, u.href);
    if (!pid) return `已识别平台「${rule.name}」，但当前不是商品详情页`;
    return `${rule.name} 商品页（商品 ID：${pid}）`;
  } catch {
    return "无法解析当前页地址";
  }
}
function renderConsent(consent) {
  $("consent-status").innerHTML = consent ? '<span class="badge ok">已授权参与</span>' : '<span class="badge no">未授权</span>';
  $("consent-panel").hidden = consent;
}
function renderAuto(consent, autoCollect) {
  const ck = $("ck-auto");
  ck.checked = autoCollect;
  ck.disabled = !consent;
  $("auto-row").classList.toggle("off", !consent);
  $("auto-hint").textContent = consent ? "进入商品详情页时自动抓取并上报（同一商品 10 分钟内不重复采集）" : "需先同意授权后才能开启自动采集";
}
function formatUploadStatus(result) {
  if (result.uploadStatus === "success") {
    const n = result.warningCount ?? 0;
    return n > 0 ? `已上报（${n} 条清洗提示）` : "已上报";
  }
  if (result.uploadStatus === "failed") return "上报失败（已存本地）";
  if (result.uploadStatus === "skipped_no_price") return "未上报（未抓到价格）";
  return "待上报";
}
function truncateId(id) {
  if (!id) return "-";
  return id.length > 16 ? `${id.slice(0, 16)}…` : id;
}
function truncateEndpoint(endpoint) {
  return endpoint.length > 42 ? `${endpoint.slice(0, 42)}…` : endpoint;
}
function renderLast(result) {
  if (!result) return;
  $("last-card").hidden = false;
  const lines = [
    `时间：${result.collectedAt ? new Date(result.collectedAt).toLocaleString("zh-CN") : "-"}`,
    `状态：${formatUploadStatus(result)}`,
    `本地记录 ID：${truncateId(result.recordId)}`,
    `后端观测 ID：${truncateId(result.observationId)}`
  ];
  const n = result.warningCount ?? 0;
  if (result.uploadStatus === "success" && n > 0) {
    lines.push(`清洗提示：${n} 条（详见 report 页记录或后端日志）`);
  }
  if ((result.uploadStatus === "failed" || result.uploadStatus === "skipped_no_price") && result.uploadError) {
    lines.push(`上报错误：<span style="color:#991b1b">${escapeHtml(result.uploadError)}</span>`);
  }
  $("last-result").innerHTML = lines.join("<br>");
}
async function refreshRetryCount() {
  const res = await chrome.storage.local.get(STORAGE_KEYS.OBSERVATIONS);
  const list = Array.isArray(res[STORAGE_KEYS.OBSERVATIONS]) ? res[STORAGE_KEYS.OBSERVATIONS] : [];
  const n = list.filter((r) => r.uploadStatus === "failed").length;
  $("retry-card").hidden = n === 0;
  $("retry-count").textContent = String(n);
}
async function main() {
  const tab = await getActiveTab();
  $("page-status").textContent = describePage(tab == null ? void 0 : tab.url);
  const stored = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.AUTO_COLLECT,
    STORAGE_KEYS.LAST_RESULT,
    STORAGE_KEYS.API_ENDPOINT,
    STORAGE_KEYS.ANON_ID
  ]);
  let consent = stored[STORAGE_KEYS.CONSENT] === true;
  let autoCollect = stored[STORAGE_KEYS.AUTO_COLLECT] === true;
  renderConsent(consent);
  renderAuto(consent, autoCollect);
  renderLast(stored[STORAGE_KEYS.LAST_RESULT]);
  $("ck-auto").addEventListener("change", async () => {
    autoCollect = $("ck-auto").checked;
    await chrome.storage.local.set({ [STORAGE_KEYS.AUTO_COLLECT]: autoCollect });
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (STORAGE_KEYS.CONSENT in changes) {
      consent = changes[STORAGE_KEYS.CONSENT].newValue === true;
      renderConsent(consent);
      renderAuto(consent, autoCollect);
    }
    if (STORAGE_KEYS.AUTO_COLLECT in changes) {
      autoCollect = changes[STORAGE_KEYS.AUTO_COLLECT].newValue === true;
      renderAuto(consent, autoCollect);
    }
    if (STORAGE_KEYS.LAST_RESULT in changes) {
      renderLast(changes[STORAGE_KEYS.LAST_RESULT].newValue);
    }
    if (STORAGE_KEYS.OBSERVATIONS in changes) {
      void refreshRetryCount();
    }
  });
  void refreshRetryCount();
  $("btn-retry").addEventListener("click", async () => {
    const btn = $("btn-retry");
    const out = $("retry-result");
    btn.disabled = true;
    btn.textContent = "重试中…";
    try {
      const r = await chrome.runtime.sendMessage({ type: MSG.RETRY_FAILED });
      out.textContent = `重试 ${r.retried} 条：成功 ${r.succeeded} 失败 ${r.failed}`;
    } catch (e) {
      out.textContent = `重试失败：${errMsg(e)}`;
    } finally {
      btn.disabled = false;
      btn.textContent = "重试上报";
    }
    await refreshRetryCount();
  });
  const endpoint = normalizeEndpoint(stored[STORAGE_KEYS.API_ENDPOINT]);
  $("endpoint-display").textContent = truncateEndpoint(endpoint);
  let origin = "http://127.0.0.1:8000";
  try {
    origin = new URL(endpoint).origin;
  } catch {
  }
  $("link-console").href = `${origin}/`;
  const anonId = typeof stored[STORAGE_KEYS.ANON_ID] === "string" ? stored[STORAGE_KEYS.ANON_ID] : "";
  if (anonId) {
    $("link-board").href = `${origin}/me#${anonId}`;
    $("anon-short").textContent = anonId.slice(0, 8) + "…";
    $("link-copy-id").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(anonId);
        $("link-copy-id").textContent = "已复制 ✓";
      } catch {
        $("link-copy-id").textContent = anonId;
      }
    });
  } else {
    $("link-board").href = `${origin}/me`;
    $("anon-short").textContent = "尚未生成（采集一次后自动生成）";
    $("link-copy-id").style.display = "none";
  }
  $("btn-test-conn").addEventListener("click", async () => {
    const btn = $("btn-test-conn");
    const out = $("conn-result");
    btn.disabled = true;
    btn.textContent = "测试中…";
    out.style.display = "block";
    out.innerHTML = "";
    try {
      const res = await chrome.runtime.sendMessage({ type: MSG.TEST_CONNECTION });
      out.innerHTML = res.ok ? `<span style="color:#166534">● ${escapeHtml(res.detail)}</span>` : `<span style="color:#991b1b">● ${escapeHtml(res.detail)}</span><br /><span style="color:#6b7280">请先启动后端：cd backend &amp;&amp; uvicorn app.main:app --port 8000</span>`;
    } catch (e) {
      out.innerHTML = `<span style="color:#991b1b">● ${escapeHtml(errMsg(e))}</span>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "测试连接";
    }
  });
  $("btn-consent").addEventListener("click", async () => {
    await chrome.storage.local.set({ [STORAGE_KEYS.CONSENT]: true });
    consent = true;
    renderConsent(true);
    renderAuto(true, autoCollect);
  });
  $("btn-collect").addEventListener("click", async () => {
    if (!consent) {
      $("consent-panel").hidden = false;
      return;
    }
    const btn = $("btn-collect");
    const out = $("collect-result");
    btn.disabled = true;
    btn.textContent = "采集中…";
    out.style.display = "block";
    try {
      const result = await chrome.runtime.sendMessage({
        type: MSG.START_COLLECTION,
        payload: {}
      });
      if (result.ok) {
        if (result.uploadStatus === "skipped_no_price") {
          out.innerHTML = `<span style="color:#b45309">⚠ 未抓取到价格，已取消上报</span>${result.uploadError ? `<br /><span style="color:#991b1b">${escapeHtml(result.uploadError)}</span>` : ""}`;
        } else if (result.uploadStatus === "failed") {
          out.innerHTML = `<span style="color:#b45309">⚠ 已存本地，待重试</span>${result.uploadError ? `<br /><span style="color:#991b1b">${escapeHtml(result.uploadError)}</span>` : ""}`;
        } else {
          out.innerHTML = `<span style="color:#166534">✓ 采集完成（${formatUploadStatus(result)}）</span>`;
        }
        renderLast(result);
        void refreshRetryCount();
      } else {
        out.innerHTML = `<span style="color:#991b1b">✗ ${escapeHtml(errMsg(result.error ?? "采集失败"))}</span>`;
      }
    } catch (e) {
      out.innerHTML = `<span style="color:#991b1b">✗ ${errMsg(e)}</span>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "采集本页数据";
    }
  });
  $("link-report").addEventListener("click", () => {
    void chrome.tabs.create({ url: chrome.runtime.getURL("report/report.html") });
  });
  $("link-options").addEventListener("click", () => {
    void chrome.runtime.openOptionsPage();
  });
}
void main();
