# JD and Amazon Scraping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support reliable product extraction and ingestion for current JD detail pages and Amazon.com detail pages.

**Architecture:** Extend the existing selector-driven content script and mirror platform recognition in the popup. Reuse the existing background upload pipeline; add the Amazon platform code and currency-aware display at the server/UI boundary.

**Tech Stack:** Chrome Manifest V3, JavaScript, Node.js VM tests, Python unittest, FastAPI cleaning validation.

## Global Constraints

- Only product detail pages are collected; no CAPTCHA bypass and no Cookie values are read.
- Main-product price selectors must be scoped to the product price region.
- JD uses CNY and Amazon.com uses USD; missing optional fields remain `null`.
- Preserve existing Taobao, Tmall, Pinduoduo and dashboard identity behavior.

---

### Task 1: Product extraction and extension registration

**Files:**
- Create: `tests/test_platform_extraction.py`
- Modify: `api/app/static/plugin.zip` (`content/index.js`, `popup/popup.js`, `manifest.json`)

**Interfaces:**
- Consumes: Existing `EXTRACT_PAGE_DATA` message and extraction result shape.
- Produces: JD `platform="jd"` and Amazon `platform="amazon"` records; Amazon ASIN from `/dp/` and `/gp/product/`.

- [ ] **Step 1: Write failing extraction tests**

Create a Python unittest that runs the zipped `content/index.js` in Node VM with browser API fixtures. The JD fixture maps `.sku-title-text` to `京东商品`, `.product-price--main` to `¥2.50`, `.top-shop-info` to `轮趣官方旗舰店`, and `.logistics-address-main` to `北京海淀区`; the Amazon fixture maps `#productTitle` to `Gaming PC`, `#sellerProfileTriggerId` to `Olialia PC Direct`, `#corePrice_feature_div .a-price .a-offscreen` to `$1,199.99`, and `.a-price.a-text-price .a-offscreen` to `$2,669.00`.

Core assertions:

```python
self.assertEqual(jd["platform"], "jd")
self.assertEqual(jd["productId"], "10203477544097")
self.assertEqual(jd["productName"], "京东商品")
self.assertEqual(jd["price"]["original"], 2.5)
self.assertEqual(jd["price"]["currency"], "CNY")
self.assertEqual(amazon["platform"], "amazon")
self.assertEqual(amazon["productId"], "B0HF7H35WS")
self.assertEqual(amazon["shopName"], "Olialia PC Direct")
self.assertEqual(amazon["price"]["original"], 2669.0)
self.assertEqual(amazon["price"]["final"], 1199.99)
self.assertEqual(amazon["price"]["currency"], "USD")
```

Add manifest assertions for `*://*.amazon.com/*` in `host_permissions`, content-script matches, and web-accessible-resource matches.

- [ ] **Step 2: Run tests to verify they fail**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_platform_extraction -v`
Expected: JD title/price assertions fail and Amazon is not recognized; Amazon manifest entries are absent.

- [ ] **Step 3: Implement minimal rules and registration**

Prepend these current JD selectors while preserving legacy selectors:

```javascript
title: [".sku-title-text", ".sku-title-name", /* legacy selectors remain */],
shopName: [".top-shop-info", /* legacy selectors remain */],
price: [".product-price--main", /* legacy selectors remain */],
finalPrice: [".product-price--main", /* legacy selectors remain */],
shippingCity: [".logistics-address-main", /* legacy selectors remain */]
```

Add the Amazon rule to both content and popup:

```javascript
{
  id: "amazon",
  name: "亚马逊",
  hostPatterns: [/(^|\.)amazon\.com$/],
  productIdPatterns: [/\/dp\/([A-Z0-9]{10})/, /\/gp\/product\/([A-Z0-9]{10})/],
  selectors: {
    title: ["#productTitle"],
    shopName: ["#sellerProfileTriggerId", "#bylineInfo"],
    price: ["#corePrice_feature_div .a-price .a-offscreen", "#priceblock_dealprice", "#priceblock_ourprice"],
    finalPrice: ["#corePrice_feature_div .a-price .a-offscreen", "#priceblock_dealprice", "#priceblock_ourprice"],
    coupon: ["#couponText", ".coupon"],
    originalPrice: ["#corePrice_feature_div .a-price.a-text-price .a-offscreen", "#basisPrice .a-offscreen"],
    shippingCity: ["#nav-global-location-popover-link"],
    userMarker: ["#nav-link-accountList"]
  },
  loginCookieNames: ["session-id", "session-token", "x-main"]
}
```

Set currency with `currency: rule.id === "amazon" ? "USD" : "CNY"`; recognize `Hello, sign in` as logged out and `Prime` as membership. Add Amazon to popup support text and all three manifest match lists.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_platform_extraction tests.test_plugin_package -v`
Expected: all extraction and package tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_platform_extraction.py api/app/static/plugin.zip
git commit -m "feat: support JD and Amazon product extraction"
```

### Task 2: Amazon ingestion and display

**Files:**
- Create: `tests/test_amazon_ingestion.py`
- Modify: `api/app/cleaning.py`
- Modify: `api/app/static/me.html`
- Modify: `api/app/static/lab.html`
- Modify: `api/app/static/overview.html`
- Modify: `api/app/static/plugin.zip` (`report/report.js`)

**Interfaces:**
- Consumes: `platform_code="amazon"`, `currency="USD"`, integer cents from the extension background.
- Produces: accepted Amazon observations and correct Chinese platform labels/currency symbols.

- [ ] **Step 1: Write failing ingestion and display tests**

```python
payload = VALID_PAYLOAD.copy()
payload.update(platform_code="amazon", currency="USD")
cleaned, warnings = clean_observation(ObservationIn(**payload))
self.assertEqual(cleaned["platform_code"], "amazon")
self.assertEqual(cleaned["currency"], "USD")
```

Assert `me.html`, `lab.html`, and `overview.html` contain `amazon: '亚马逊'`; assert `me.html` formats USD with `$` and passes `o.currency` when rendering observations.

- [ ] **Step 2: Run tests to verify they fail**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_amazon_ingestion -v`
Expected: `CleanError` for Amazon and missing display mappings.

- [ ] **Step 3: Implement whitelist and display support**

Add `"amazon"` to `ALLOWED_PLATFORMS`. Add `amazon: '亚马逊'` to the three UI maps. Change dashboard formatting to:

```javascript
function fmtCents(c, currency) {
  if (c == null) return '—';
  var symbol = currency === 'USD' ? '$' : (currency === 'CNY' || !currency ? '¥' : currency + ' ');
  return symbol + (c / 100).toFixed(2);
}
```

Pass `o.currency` for display and actual-pay prices. Apply the same platform label and currency handling in the local report.

- [ ] **Step 4: Run all tests**

Run: `../repo/.venv/Scripts/python -m unittest discover tests -v`
Expected: all tests pass with zero failures/errors.

- [ ] **Step 5: Commit**

```bash
git add api/app/cleaning.py api/app/static/me.html api/app/static/lab.html api/app/static/overview.html api/app/static/plugin.zip tests/test_amazon_ingestion.py
git commit -m "feat: ingest and display Amazon observations"
```

### Task 3: Live-page verification

**Files:**
- Verify only; no production changes unless a verified mismatch requires a new failing test.

**Interfaces:**
- Consumes: committed extension rules and current logged-in JD/Amazon pages.

- [ ] **Step 1: Verify JD actual selectors**

On `https://item.jd.com/10203477544097.html`, confirm `.sku-title-text`, `.product-price--main`, `.top-shop-info`, and `.logistics-address-main` return the same product fields used by tests.

- [ ] **Step 2: Verify Amazon actual selectors**

On `https://www.amazon.com/dp/B0HF7H35WS`, confirm ASIN, `#productTitle`, `#sellerProfileTriggerId`, `#corePrice_feature_div .a-price .a-offscreen`, and USD prices match the fixture behavior.

- [ ] **Step 3: Re-run the full suite and inspect the final diff**

Run: `../repo/.venv/Scripts/python -m unittest discover tests -v && git status --short`
Expected: all tests pass; only intended committed artifacts are present.
