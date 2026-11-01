(function() {
  "use strict";
  const MSG = {
    START_COLLECTION: "START_COLLECTION",
    EXTRACT_PAGE_DATA: "EXTRACT_PAGE_DATA",
    TEST_CONNECTION: "TEST_CONNECTION",
    AUTO_COLLECT: "AUTO_COLLECT",
    RETRY_FAILED: "RETRY_FAILED"
  };
  const STORAGE_KEYS = {
    CONSENT: "consent",
    AUTO_COLLECT: "autoCollect"
  };
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
        title: [
          ".sku-title-text",
          ".sku-title-name",
          "#name h1",
          // 京东商品名
          ".sku-name",
          "#itemInfo #name h1",
          ".itemInfo-wrap .sku-name",
          'h1[class*="sku"]'
        ],
        shopName: [
          ".top-shop-info .top-name-tag",
          ".top-shop-info",
          "#shopId",
          // 店铺链接节点
          ".pop-shop-name",
          ".shopName",
          '[class*="shop-name"]',
          ".crumb-wrap .contact .name"
        ],
        price: [
          ".product-price--main",
          ".p-price .price",
          // 京东价
          "#price .price",
          ".summary-price .price",
          "span.price",
          '[class*="priceJ"]'
        ],
        finalPrice: [
          '[class*="finalPrice"]',
          ".summary-price .p-price .price",
          '[class*="couponPrice"]',
          ".p-price .price",
          '[class*="FinalPrice"]'
        ],
        coupon: [
          ".quan-item",
          // 优惠券领取区
          "#coupon .quan",
          '[class*="coupon"]',
          ".youhui .quan-item",
          '[class*="Coupon"]'
        ],
        originalPrice: [
          "#page_maprice",
          // 京东划线价
          ".p-price del",
          '[class*="originPrice"]',
          "del.price",
          ".origin-price"
        ],
        shippingCity: [
          ".logistics-address-main",
          "#store-prompt",
          // 配送至/发货地（部分页面需展开配送面板才渲染）
          '[class*="sendAddress"]',
          "#summary .dd",
          '[class*="address"]',
          ".summary .dd"
        ],
        userMarker: [
          "#ttbar-login .nickname",
          // 顶栏昵称
          ".nickname",
          '[class*="userInfo"]',
          ".user-info",
          '[class*="userNick"]'
        ]
      },
      loginCookieNames: ["pin", "pt_pin", "pt_key"]
    },
    {
      id: "amazon",
      name: "亚马逊",
      hostPatterns: [/(^|\.)amazon\.com$/],
      productIdPatterns: [/\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:[/?]|$)/i],
      selectors: {
        title: ["#productTitle"],
        shopName: ["#sellerProfileTriggerId", "#merchant-info"],
        price: [
          "#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen",
          "#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen",
          "#corePrice_feature_div .a-price .a-offscreen"
        ],
        finalPrice: [
          "#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen",
          "#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen",
          "#corePrice_feature_div .a-price .a-offscreen"
        ],
        coupon: ["#promoPriceBlockMessage_feature_div", "#couponText"],
        originalPrice: [
          "#corePrice_feature_div .a-price.a-text-price .a-offscreen",
          "#corePriceDisplay_desktop_feature_div .a-price.a-text-price .a-offscreen"
        ],
        shippingCity: ["#nav-global-location-popover-link"],
        userMarker: ["#nav-link-accountList"]
      },
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
  const PRICE_MIN = 0.01;
  const PRICE_MAX = 1e7;
  const SALE_PRICE_KEYS = ["priceText", "promotePrice", "currentPrice", "salePrice", "price"];
  const ORIG_PRICE_KEYS = ["origPrice", "originalPrice", "reservePrice", "marketPrice", "strPrice"];
  const FINAL_PRICE_KEYS = ["finalPrice", "couponPrice", "promotePrice", "handPrice"];
  const SHIPPING_KEYS = ["deliveryAddress", "areaName", "sendAddress", "shipFrom", "deliveryCity"];
  const SHOP_NAME_KEYS = ["shopName", "shopNick", "mallName", "sellerNick"];
  const SHOP_ID_KEYS = ["shopId", "shop_id", "sellerId", "seller_id"];
  const OPTION_RULES = {
    taobao: {
      groups: ['[class*="skuItem--"]', ".J_Prop"],
      labels: ['[class*="ItemLabel--"]', '[class*="label--"]', ".tb-property-type"],
      selected: ['[class*="isSelected--"]', ".selected"]
    },
    tmall: {
      groups: ['[class*="skuItem--"]', ".J_Prop"],
      labels: ['[class*="ItemLabel--"]', '[class*="label--"]', ".tb-property-type"],
      selected: ['[class*="isSelected--"]', ".selected"]
    },
    jd: {
      groups: ["#choose-attrs .sku-choose", ".sku-choose", ".specification-group", '[class*="skuItem--"]'],
      labels: [".dt", ".specification-group-label", '[class*="label--"]'],
      selected: [".selected", ".specification-item-sku--selected", '[class*="isSelected--"]']
    },
    amazon: {
      groups: ['[id^="inline-twister-row-"]', '#twister [id^="variation_"]', '#twister [id$="_name"]', "#twister_feature_div"],
      labels: ['[id^="inline-twister-dim-title-"] .a-color-secondary', ".a-form-label", ".a-row .a-size-base"],
      selected: ['[id^="inline-twister-expanded-dimension-text-"]', ".a-button-selected", ".a-selected", "li.selected", '[aria-checked="true"]', "select option:checked"]
    }
  };
  function cleanOptionText(value) {
    return (value ?? "").replace(/\s+/g, " ").trim().slice(0, 200);
  }
  function extractSelectedOptions(rule) {
    const config = OPTION_RULES[rule.id];
    if (!config) return [];
    const groups = [];
    const seenGroups = /* @__PURE__ */ new Set();
    for (const selector of config.groups) {
      for (const group of document.querySelectorAll(selector)) {
        if (!seenGroups.has(group)) {
          seenGroups.add(group);
          groups.push(group);
        }
      }
    }
    const options = [];
    for (const group of groups) {
      let name = "";
      for (const selector of config.labels) {
        const label = group.querySelector(selector);
        name = cleanOptionText(label == null ? void 0 : label.textContent).replace(/[：:]\s*$/, "");
        if (name) break;
      }
      const selected = [];
      const seenValues = /* @__PURE__ */ new Set();
      for (const selector of config.selected) {
        for (const el of group.querySelectorAll(selector)) {
          const value = cleanOptionText(el.textContent);
          if (!value || value === name || seenValues.has(value)) continue;
          seenValues.add(value);
          selected.push(value);
        }
      }
      if (selected.length > 0) options.push({ name: name || "规格", value: selected.join(" / ") });
    }
    return options.slice(0, 20);
  }
  function extractSkuId(rule, url, productId) {
    if (rule.id === "jd" || rule.id === "amazon") return productId;
    const match = url.match(/[?&]skuId=([^&#]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }
  function extractPageData() {
    const rule = findPlatformRule(window.location.hostname);
    if (!rule) return null;
    const productId = extractProductId(rule, window.location.href);
    if (!productId) return null;
    const scriptText = collectInlineScriptText();
    const title = pickFirst(rule.selectors.title);
    const couponNode = pickFirst(rule.selectors.coupon);
    const shopNode = pickFirst(rule.selectors.shopName);
    let shopName = shopNode ? { value: cleanShopName(shopNode.text), source: "dom" } : { value: null, source: null };
    if (shopName.value === null) {
      const v = pickJsonString(scriptText, SHOP_NAME_KEYS);
      if (v !== null) shopName = { value: v, source: "json" };
    }
    const shopId = pickShopId(scriptText);
    const isTaoFamily = rule.id === "taobao" || rule.id === "tmall";
    const sale = pickPrice(
      rule.selectors.price,
      scriptText,
      SALE_PRICE_KEYS,
      isTaoFamily ? pickUnitTextPrice : void 0
    );
    const sub = pickPrice(rule.selectors.originalPrice, scriptText, ORIG_PRICE_KEYS);
    let original;
    let finalP;
    if (sub.value !== null) {
      original = sub;
      finalP = sale.value !== null ? sale : pickPrice(rule.selectors.finalPrice, scriptText, FINAL_PRICE_KEYS);
    } else {
      original = sale;
      finalP = pickPrice(rule.selectors.finalPrice, scriptText, FINAL_PRICE_KEYS);
    }
    if (original.value !== null && finalP.value !== null && finalP.value > original.value) {
      [original, finalP] = [finalP, original];
    }
    const coupon = couponNode ? parseCoupon(couponNode.text) : { amount: null, type: null };
    const shipNode = pickFirst(rule.selectors.shippingCity);
    let shipRaw = shipNode ? { value: shipNode.text, source: "dom" } : { value: null, source: null };
    if (shipRaw.value === null) {
      const v = pickJsonString(scriptText, SHIPPING_KEYS);
      if (v !== null) shipRaw = { value: v, source: "json" };
    }
    const shipNormalized = shipRaw.value !== null ? normalizeShippingCity(shipRaw.value) : null;
    const markerNode = pickFirst(rule.selectors.userMarker);
    const price = {
      original: original.value,
      final: finalP.value,
      currency: rule.id === "amazon" ? "USD" : "CNY",
      couponAmount: coupon.amount,
      couponType: coupon.type
    };
    const extractionMeta = {
      price: sale.source,
      originalPrice: original.source,
      finalPrice: finalP.source,
      shippingCity: shipRaw.source,
      shopName: shopName.source,
      shopId: shopId.source
    };
    const domSnapshots = [];
    const snapshotTargets = [
      ["title", title],
      ["price", sale.domNode],
      ["finalPrice", finalP.domNode],
      ["originalPrice", original.domNode],
      ["shopName", shopNode],
      ["shippingCity", shipNode]
    ];
    for (const [field, node] of snapshotTargets) {
      const snap = node ? snapshotNode(field, node.el) : null;
      if (snap) domSnapshots.push(snap);
    }
    domSnapshots.push({ field: "extractionMeta", outerHTML: JSON.stringify(extractionMeta) });
    return {
      platform: rule.id,
      productId,
      skuId: extractSkuId(rule, window.location.href, productId),
      selectedOptions: extractSelectedOptions(rule),
      productName: (title == null ? void 0 : title.text) ?? null,
      shopName: shopName.value,
      shopId: shopId.value,
      productUrl: window.location.href,
      price,
      userContext: inferUserContext(rule, (markerNode == null ? void 0 : markerNode.text) ?? null),
      device: collectDeviceInfo(),
      shipping: { shipFromCity: shipRaw.value, shipFromCityNormalized: shipNormalized },
      extractionMeta,
      domSnapshots
    };
  }
  function pickFirst(selectors) {
    var _a;
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        const text = ((_a = el == null ? void 0 : el.textContent) == null ? void 0 : _a.replace(/\s+/g, " ").trim()) ?? "";
        if (el && text) return { text, el };
      } catch {
      }
    }
    return null;
  }
  function collectInlineScriptText() {
    const parts = [];
    let total = 0;
    const scripts = document.querySelectorAll("script:not([src])");
    for (const s of scripts) {
      const t = s.textContent ?? "";
      if (!t) continue;
      parts.push(t);
      total += t.length;
      if (total >= 2e6) break;
    }
    return parts.join("\n");
  }
  function pickPrice(domSelectors, scriptText, jsonKeys, extraDom) {
    const node = pickFirst(domSelectors);
    if (node) {
      const n = parsePriceNumber(node.text);
      if (n !== null && n >= PRICE_MIN && n <= PRICE_MAX) {
        return { value: n, source: "dom", domNode: node };
      }
    }
    if (extraDom) {
      const e = extraDom();
      if (e) return e;
    }
    const j = pickJsonPrice(scriptText, jsonKeys);
    if (j !== null) return { value: j, source: "json", domNode: node };
    return { value: null, source: null, domNode: node };
  }
  function pickUnitTextPrice() {
    const blocks = document.querySelectorAll('div[class*="block2--"]');
    for (const b of blocks) {
      if (b.closest('[class*="ItemHeadFixed--"]')) continue;
      const unit = b.querySelector('span[class*="unit--"]');
      const numEl = b.querySelector('span[class*="text--"]');
      if (!unit || !numEl) continue;
      const unitText = (unit.textContent ?? "").trim();
      if (!/^[¥￥]$/.test(unitText)) continue;
      const numText = (numEl.textContent ?? "").trim();
      const n = parsePriceNumber(numText);
      if (n !== null && n >= PRICE_MIN && n <= PRICE_MAX) {
        return { value: n, source: "dom", domNode: { text: `${unitText}${numText}`, el: b } };
      }
    }
    return null;
  }
  function pickJsonPrice(text, keys) {
    if (!text) return null;
    for (const key of keys) {
      const re = new RegExp(`"${key}"\\s*:\\s*"?(-?\\d+(?:\\.\\d+)?)"?`);
      const m = re.exec(text);
      if (!m) continue;
      const n = Number(m[1]);
      if (Number.isFinite(n) && n >= PRICE_MIN && n <= PRICE_MAX) return n;
    }
    return null;
  }
  function pickJsonString(text, keys, maxLen = 80) {
    if (!text) return null;
    for (const key of keys) {
      const re = new RegExp(`"${key}"\\s*:\\s*"([^"]{1,${maxLen}})"`);
      const m = re.exec(text);
      if (m && m[1].trim()) return m[1].trim();
    }
    return null;
  }
  function pickShopId(scriptText) {
    var _a, _b;
    const attrEl = document.querySelector("[data-shopid],[data-sellerid]");
    const attr = ((_a = attrEl == null ? void 0 : attrEl.getAttribute("data-shopid")) == null ? void 0 : _a.trim()) ?? ((_b = attrEl == null ? void 0 : attrEl.getAttribute("data-sellerid")) == null ? void 0 : _b.trim()) ?? null;
    if (attr && /^\d{3,}$/.test(attr)) return { value: attr, source: "dom" };
    const links = document.querySelectorAll('a[href*="shop"]');
    for (const a of links) {
      const href = a.getAttribute("href") ?? "";
      const m = href.match(/[?&](?:shopId|shop_id|sellerId|seller_id)=(\d{3,})/);
      if (m) return { value: m[1], source: "dom" };
    }
    const v = pickJsonString(scriptText, SHOP_ID_KEYS, 40);
    if (v !== null && /^\d{3,}$/.test(v)) return { value: v, source: "json" };
    return { value: null, source: null };
  }
  function cleanShopName(text) {
    const m = text.match(/^[^\d]{2,}(?=\d)/);
    return m ? m[0].trim() : text;
  }
  const MUNICIPALITIES = ["北京", "上海", "天津", "重庆"];
  const PROVINCES = [
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "内蒙古",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
    "香港",
    "澳门"
  ];
  function normalizeShippingCity(raw) {
    const segs = raw.split("至").map((s) => s.replace(/\s+/g, ""));
    let t = segs[0];
    if (!t || t === "配送" || t === "发货" || t === "快递") t = segs[1] ?? "";
    if (!t) return null;
    for (const m of MUNICIPALITIES) {
      if (t.includes(m)) return m;
    }
    for (const p of PROVINCES) {
      const idx = t.indexOf(p);
      if (idx === -1) continue;
      const rest = t.slice(idx + p.length).replace(/^(特别行政区|壮族自治区|回族自治区|维吾尔自治区|自治区|省|市)/, "");
      const cm2 = rest.match(/^([一-龥]{1,4}?)(?:市|区|县|盟|地区|自治州|$)/);
      if (cm2 && cm2[1]) return cm2[1];
      return p;
    }
    const cm = t.match(/([一-龥]{2,4})市/);
    if (cm) return cm[1];
    return null;
  }
  function parsePriceNumber(text) {
    const t = text.replace(/,/g, "");
    const afterSymbol = t.match(/[¥￥]\s*(\d+(?:\.\d{1,2})?)/);
    const m = afterSymbol ?? t.match(/(\d+(?:\.\d{1,2})?)/);
    if (!m) return null;
    const n = Number(m[1]);
    return Number.isFinite(n) ? n : null;
  }
  function parseCoupon(text) {
    const t = text.trim();
    if (!t) return { amount: null, type: null };
    for (const st of ["百亿补贴", "平台补贴", "政府补贴"]) {
      const idx = t.indexOf(st);
      if (idx === -1) continue;
      const before = t.slice(0, idx).match(/[¥￥]\s*(\d+(?:\.\d+)?)\s*$/);
      const after = t.slice(idx + st.length).match(/^(?:已?抵|立?省|减)?\s*[¥￥]?\s*(\d+(?:\.\d+)?)/);
      const amount = (before == null ? void 0 : before[1]) ?? (after == null ? void 0 : after[1]);
      return { amount: amount ? Number(amount) : null, type: st === "百亿补贴" ? "百亿补贴" : "平台补贴" };
    }
    let type = null;
    if (/满.*减/.test(t)) type = "满减券";
    else if (/折/.test(t)) type = "折扣券";
    else if (/券|优惠/.test(t)) type = "通用券";
    const m = t.match(/减\s*(\d+(?:\.\d+)?)/) ?? t.match(/(\d+(?:\.\d+)?)\s*元/);
    return { amount: m ? Number(m[1]) : null, type };
  }
  function inferUserContext(rule, markerText) {
    const cookieKeys = new Set(
      document.cookie.split(";").map((kv) => kv.split("=")[0].trim()).filter(Boolean)
    );
    const hitCookie = rule.loginCookieNames.find((name) => cookieKeys.has(name)) ?? null;
    const evidence = [];
    let isLoggedIn = null;
    if (hitCookie) {
      isLoggedIn = true;
      evidence.push(`存在登录态 cookie 键名「${hitCookie}」（仅判断存在性，未读取值）`);
    }
    const marker = (markerText == null ? void 0 : markerText.trim()) || null;
    if (marker) {
      if (/请登录|立即登录|^登录$|注册|Hello, sign in/i.test(marker)) {
        if (isLoggedIn === null) isLoggedIn = false;
        evidence.push("页面用户节点展示「登录/注册」入口，推断未登录");
      } else {
        if (isLoggedIn === null) isLoggedIn = true;
        evidence.push(`页面展示用户标识「${maskText(marker)}」`);
      }
    }
    if (isLoggedIn === null) {
      evidence.push("未找到可靠登录态证据，按未知处理");
    }
    let memberLevel = null;
    const levelMatch = marker == null ? void 0 : marker.match(/(88VIP|PLUS|Prime|超级会员|钻石会员|黄金会员|VIP\d{0,2}|会员)/i);
    if (levelMatch) memberLevel = levelMatch[1];
    return {
      isLoggedIn,
      memberLevel,
      isNewUser: null,
      // 页面无法可靠判断是否新用户，保持 null
      userMarker: marker,
      evidence: `${evidence.join("；")}；isNewUser 页面无可靠判断依据，记为 null`
    };
  }
  function collectDeviceInfo() {
    const nav = navigator;
    const memory = typeof nav.deviceMemory === "number" ? nav.deviceMemory : null;
    const cores = typeof navigator.hardwareConcurrency === "number" ? navigator.hardwareConcurrency : null;
    const pixels = window.screen.width * window.screen.height;
    return {
      userAgent: navigator.userAgent,
      screenResolution: `${window.screen.width}x${window.screen.height}`,
      deviceMemory: memory,
      hardwareConcurrency: cores,
      platform: navigator.platform,
      language: navigator.language,
      devicePriceIndex: estimateDevicePriceIndex(memory, cores, pixels)
    };
  }
  function estimateDevicePriceIndex(memory, cores, pixels) {
    const memScore = memory === null ? 0.5 : Math.min(memory / 16, 1);
    const cpuScore = cores === null ? 0.5 : Math.min(cores / 8, 1);
    const screenScore = Math.min(pixels / (2560 * 1440), 1);
    return Math.round((memScore * 0.4 + cpuScore * 0.3 + screenScore * 0.3) * 100);
  }
  function snapshotNode(field, el) {
    const clone = el.cloneNode(true);
    clone.querySelectorAll("script,style").forEach((n) => n.remove());
    const html = (clone.outerHTML ?? "").slice(0, 2e3);
    return html ? { field, outerHTML: html } : null;
  }
  const BANNER_HOST_ID = "__algo_obs_banner_host__";
  const TOAST_HOST_ID = "__algo_obs_toast_host__";
  const triggeredProductIds = /* @__PURE__ */ new Set();
  (function init() {
    detectAndAct();
    watchSpaNavigation();
  })();
  function detectAndAct() {
    const rule = findPlatformRule(window.location.hostname);
    if (!rule) return;
    const productId = extractProductId(rule, window.location.href);
    if (!productId) return;
    chrome.storage.local.get([STORAGE_KEYS.CONSENT, STORAGE_KEYS.AUTO_COLLECT], (res) => {
      const consent = res[STORAGE_KEYS.CONSENT] === true;
      const autoCollect = res[STORAGE_KEYS.AUTO_COLLECT] === true;
      if (!consent) {
        injectBanner();
        return;
      }
      const skuId = extractSkuId(rule, window.location.href, productId);
      const options = extractSelectedOptions(rule);
      const variantKey = `${productId}:${skuId ?? ""}:${JSON.stringify(options)}`;
      if (autoCollect && !triggeredProductIds.has(variantKey)) {
        triggeredProductIds.add(variantKey);
        void triggerAutoCollect(productId, variantKey);
      }
    });
  }
  async function triggerAutoCollect(productId, variantKey) {
    try {
      if (document.readyState !== "complete") {
        await new Promise((resolve) => {
          const timer = window.setTimeout(resolve, 3e3);
          window.addEventListener(
            "load",
            () => {
              window.clearTimeout(timer);
              resolve();
            },
            { once: true }
          );
        });
      }
      const payload = { productId, variantKey };
      const result = await chrome.runtime.sendMessage({
        type: MSG.AUTO_COLLECT,
        payload
      });
      if (result == null ? void 0 : result.ok) {
        showToast("✅ 已自动采集本页观测数据");
      }
    } catch {
    }
  }
  let detectTimer = null;
  function scheduleDetect() {
    if (detectTimer !== null) window.clearTimeout(detectTimer);
    detectTimer = window.setTimeout(() => detectAndAct(), 2e3);
  }
  function watchSpaNavigation() {
    const wrap = (orig) => function(...args) {
      orig.apply(this, args);
      scheduleDetect();
    };
    history.pushState = wrap(history.pushState);
    history.replaceState = wrap(history.replaceState);
    window.addEventListener("popstate", () => scheduleDetect());
    let lastUrl = window.location.href;
    window.setInterval(() => {
      if (window.location.href !== lastUrl) {
        lastUrl = window.location.href;
        scheduleDetect();
      }
    }, 1500);
  }
  async function extractWithPriceWait() {
    const FULL_PRICE_SELECTOR = '[class*="highlightPrice--"], [class*="subPrice--"]';
    const rule = findPlatformRule(window.location.hostname);
    const isTaoFamily = (rule == null ? void 0 : rule.id) === "taobao" || (rule == null ? void 0 : rule.id) === "tmall";
    const MAX_TRIES = isTaoFamily ? 20 : 16;
    let data = extractPageData();
    for (let i = 0; i < MAX_TRIES && data !== null; i++) {
      if (isTaoFamily) {
        if (document.querySelector(FULL_PRICE_SELECTOR)) return data;
      } else if (data.price.original !== null || data.price.final !== null) {
        return data;
      }
      await new Promise((r) => window.setTimeout(r, 500));
      data = extractPageData();
    }
    return data;
  }
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if ((message == null ? void 0 : message.type) !== MSG.EXTRACT_PAGE_DATA) return false;
    void (async () => {
      try {
        const data = await extractWithPriceWait();
        if (!data) {
          sendResponse({ ok: false, error: "当前页未识别为受支持的商品详情页" });
        } else {
          sendResponse({ ok: true, data });
        }
      } catch (e) {
        sendResponse({ ok: false, error: `页面数据提取异常：${errMsg(e)}` });
      }
    })();
    return true;
  });
  function showToast(text) {
    var _a;
    (_a = document.getElementById(TOAST_HOST_ID)) == null ? void 0 : _a.remove();
    const host = document.createElement("div");
    host.id = TOAST_HOST_ID;
    host.style.cssText = "position:fixed;top:12px;right:12px;z-index:2147483647;";
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
    <style>
      .toast { padding:8px 14px; background:#166534; color:#fff; border-radius:8px;
               box-shadow:0 2px 10px rgba(0,0,0,.3);
               font:13px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }
    </style>
    <div class="toast">${escapeHtml(text)}</div>`;
    (document.body ?? document.documentElement).appendChild(host);
    window.setTimeout(() => host.remove(), 3e3);
  }
  function injectBanner() {
    if (document.getElementById(BANNER_HOST_ID)) return;
    const host = document.createElement("div");
    host.id = BANNER_HOST_ID;
    host.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483647;";
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
    <style>
      .bar { display:flex; align-items:center; gap:8px; padding:8px 14px; flex-wrap:wrap;
             background:#1e293b; color:#f8fafc; box-shadow:0 2px 8px rgba(0,0,0,.25);
             font:13px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }
      .txt { flex:1; min-width:220px; }
      button { border:none; border-radius:6px; padding:5px 12px; font-size:13px; cursor:pointer; }
      button:disabled { opacity:.6; cursor:default; }
      .agree { background:#4f46e5; color:#fff; }
      .once { background:#0ea5e9; color:#fff; }
      .dismiss { background:transparent; color:#94a3b8; }
      .ok { color:#4ade80; }
      .err { color:#f87171; }
    </style>
    <div class="bar">
      <span class="txt">🔍 算法歧视众包观测：是否为本页面贡献一条算法比价观测数据？仅采集页面公开价格信息，不含账号密码与 cookie 值。</span>
      <button class="agree" data-act="consent">同意并采集</button>
      <button class="once" data-act="once">仅本次采集</button>
      <button class="dismiss" data-act="dismiss">忽略</button>
    </div>`;
    (document.body ?? document.documentElement).appendChild(host);
    shadow.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        const act = btn.dataset.act ?? "";
        void onBannerAction(shadow, act);
      });
    });
  }
  async function onBannerAction(shadow, act) {
    const host = document.getElementById(BANNER_HOST_ID);
    if (act === "dismiss") {
      host == null ? void 0 : host.remove();
      return;
    }
    if (act === "consent") {
      await chrome.storage.local.set({ [STORAGE_KEYS.CONSENT]: true });
    }
    const bar = shadow.querySelector(".bar");
    const txt = shadow.querySelector(".txt");
    bar == null ? void 0 : bar.querySelectorAll("button").forEach((b) => {
      b.disabled = true;
    });
    if (txt) txt.textContent = "正在采集本页观测数据…";
    const payload = { onceOnly: act === "once" };
    try {
      const result = await chrome.runtime.sendMessage({
        type: MSG.START_COLLECTION,
        payload
      });
      if (txt) {
        txt.innerHTML = result.ok ? `<span class="ok">✓ 已采集（${formatUploadStatus(result)}），感谢参与！</span>` : `<span class="err">✗ 采集失败：${escapeHtml(result.error ?? "未知错误")}</span>`;
      }
    } catch (e) {
      if (txt) txt.innerHTML = `<span class="err">✗ 采集失败：${escapeHtml(errMsg(e))}</span>`;
    }
    window.setTimeout(() => host == null ? void 0 : host.remove(), 4e3);
  }
  function formatUploadStatus(result) {
    if (result.uploadStatus === "success") {
      const n = result.warningCount ?? 0;
      return n > 0 ? `已上报（${n} 条清洗提示）` : "已上报";
    }
    return "已存本地，待重试";
  }
})();
