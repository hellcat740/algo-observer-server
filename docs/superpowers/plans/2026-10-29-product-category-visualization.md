# Product Category and High-Dimensional Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cached DeepSeek product classification and complete, currency-safe observation points behind an authenticated high-dimensional visualization page without changing existing observation fields.

**Architecture:** A product-category service deduplicates products, validates model output, and persists a separate cache table. A visualization service joins observations to those classifications and the existing exchange-rate cache at read time. A new authenticated API and standalone SVG page expose the resulting points.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, urllib, SQLite/PostgreSQL, unittest, native HTML/CSS/JavaScript/SVG.

## Global Constraints

- Do not alter existing observation fields, integer-cent storage, original-currency persistence, UTC semantics, or anonymous identity rules.
- Model input is limited to `product_name`, `seller_id`, `product_url`, and `platform_code`.
- Never write the supplied DeepSeek secret to source, tests, documentation, browser code, or logs.
- Default model configuration is `DEEPSEEK_MODEL=v4.1flash`; all classification network calls are server-side and mocked in tests.
- `user_pseudonym` is exactly `"u_" + sha256(user_ref)[:10]`; raw `user_ref` is absent from visualization responses.
- Only CNY and USD→CNY can produce `normalized_price_cents`; unsupported currencies and unavailable rates produce `None`.
- The plugin remains version 1.1.0 because no extension file changes.
- Every task ends with a Git commit; run the complete suite before delivery.

---

### Task 1: Product Identity, Cache Model, and DeepSeek Classification

**Files:**
- Modify: `api/app/models.py`
- Create: `api/app/product_categories.py`
- Test: `tests/test_product_categories.py`

**Interfaces:**
- Consumes: existing `Base`, SQLAlchemy sessions, and Observation product fields.
- Produces: `ProductCategoryCache`, `product_key(product)`, `cache_key(product)`, `deduplicate_products(observations)`, and `classify_products(db, observations, caller=None) -> tuple[dict[str, dict], list[str]]`. The returned dictionary is keyed by `cache_key` and values contain the required classification JSON fields plus `cache_key`, `platform_code`, `product_name`, and `product_url` for server-side joins.

- [ ] **Step 1: Write failing identity, deduplication, and call-count tests**

Create `tests/test_product_categories.py` with an in-memory SQLite session and two observations sharing the same product identity. Assert that `product_key` is stable across a name change, `cache_key` changes, duplicate observations produce one product, and one fake caller is invoked for duplicate observations.

```python
class ProductCategoryTest(unittest.TestCase):
    def test_deduplicates_observations_before_model_call(self):
        products = deduplicate_products([self.observation, self.observation])
        self.assertEqual(len(products), 1)
        caller = FakeCaller(valid_classification(self.observation))
        results, warnings = classify_products(self.db, [self.observation, self.observation], caller=caller)
        self.assertEqual(caller.calls, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(warnings, [])
```

- [ ] **Step 2: Run the tests and verify the initial failure**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_product_categories -v`
Expected: FAIL because `app.product_categories` does not exist.

- [ ] **Step 3: Add the isolated cache model**

Add a `ProductCategoryCache(Base)` model with table name `product_category_cache`, a 64-character `cache_key` primary key, product identity/input columns, three category columns, `confidence`, `evidence`, `needs_human_review`, `model_name`, `created_at`, and `updated_at`. Do not add columns to `Observation`.

- [ ] **Step 4: Implement stable keys and allow-listed model input**

Use canonical JSON so separators cannot create ambiguous keys:

```python
def _digest(values):
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def product_key(product):
    return _digest([product.platform_code, product.product_id, product.seller_id or ""])

def cache_key(product):
    return _digest([product.platform_code, product.product_id, product.seller_id or "", product.product_name])
```

Build the request user content from exactly:

```python
{
    "product_name": product.product_name,
    "seller_id": product.seller_id or "",
    "product_url": product.product_url,
    "platform_code": product.platform_code,
}
```

- [ ] **Step 5: Implement DeepSeek transport and strict response normalization**

Use `urllib.request.Request` against `{DEEPSEEK_BASE_URL}/chat/completions`, bearer `DEEPSEEK_API_KEY`, model `DEEPSEEK_MODEL`, `response_format={"type": "json_object"}`, and an 8-second timeout. Extract `choices[0].message.content` and parse JSON. Recompute identity fields from the input, validate the fixed L1/L2 taxonomy, finite confidence in `[0,1]`, an evidence substring of at most 40 characters, and force review below 0.75 or for the unknown category.

- [ ] **Step 6: Add cache and deterministic fallback tests**

Test cache hits make zero calls, missing configuration and malformed responses produce `其他／无法判断` with `needs_human_review=True`, transient failures are not cached, names shorter than four non-whitespace characters bypass the caller, and serialized request text contains none of `user_ref`, `ip_city`, `membership_level`, `is_login`, `platform`, or `is_new_user` as input keys.

- [ ] **Step 7: Run Task 1 tests**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_product_categories -v`
Expected: all Task 1 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add api/app/models.py api/app/product_categories.py tests/test_product_categories.py
git commit -m "feat: cache DeepSeek product classifications"
```

---

### Task 2: Complete Currency-Safe Visualization Points

**Files:**
- Create: `api/app/visualization.py`
- Test: `tests/test_visualization_points.py`

**Interfaces:**
- Consumes: Observation objects, classification dictionaries from `classify_products`, and exchange-rate dictionaries from `latest_rate`.
- Produces: `build_visualization_point(observation, classification, usd_rate=None) -> dict`, `build_visualization_points(observations, classifications, usd_rate=None) -> list[dict]`, and `user_pseudonym(user_ref) -> str | None`.

- [ ] **Step 1: Write failing point-contract tests**

Construct observations for CNY display price, USD actual-price fallback, stale USD rate, missing USD rate, and EUR. Assert all required fields exist and exact values include:

```python
self.assertEqual(cny["basis_price_cents"], 1000)
self.assertEqual(cny["price_basis"], "DISPLAY")
self.assertEqual(cny["normalized_price_cents"], 1000)
self.assertEqual(usd["price_basis"], "ACTUAL")
self.assertEqual(usd["normalized_price_cents"], 6480)
self.assertEqual(usd["exchange_rate"], 7.2)
self.assertTrue(stale["exchange_stale"])
self.assertIsNone(eur["normalized_price_cents"])
self.assertIsNone(missing_rate["normalized_price_cents"])
```

Use `Decimal(str(exchange_rate))` and `ROUND_HALF_UP` in the expected implementation.

- [ ] **Step 2: Run tests and verify module failure**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_visualization_points -v`
Expected: FAIL because `app.visualization` does not exist.

- [ ] **Step 3: Implement point construction**

Implement the complete field list from the specification. Select display price when it is not `None`, otherwise actual price. CNY uses rate 1; USD uses the supplied rate or null fields; other currencies never normalize. Convert `fetch_ts` to UTC ISO 8601 and calculate evidence flags from path presence only.

```python
def user_pseudonym(user_ref):
    if not user_ref:
        return None
    digest = hashlib.sha256(user_ref.encode("utf-8")).hexdigest()
    return "u_" + digest[:10]
```

- [ ] **Step 4: Add privacy and evidence tests**

Assert the pseudonym matches an independently calculated SHA-256 prefix, the serialized point does not contain the raw UUID or a `user_ref` key, missing user references remain null, and screenshot/DOM flags track empty versus non-empty paths.

- [ ] **Step 5: Run Task 2 tests**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_visualization_points -v`
Expected: all Task 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/visualization.py tests/test_visualization_points.py
git commit -m "feat: build normalized visualization points"
```

---

### Task 3: Authenticated Visualization API

**Files:**
- Modify: `api/app/analysis_api.py`
- Modify: `api/app/main.py`
- Test: `tests/test_visualization_api.py`

**Interfaces:**
- Consumes: `classify_products`, `build_visualization_points`, `latest_rate`, and `ExchangeRateUnavailable`.
- Produces: `GET /api/analysis/visualization-points` and `GET /visualization`; response keys are `points`, `classifications`, and `meta`.

- [ ] **Step 1: Write failing API tests**

Use the existing test database pattern and an admin key. Seed two observations for one product and assert that unauthenticated access is rejected, authenticated access returns one classification but two points, and no raw `user_ref` appears. Test platform, product, currency, and post-classification category filters.

- [ ] **Step 2: Run API tests and verify 404**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_visualization_api -v`
Expected: FAIL with 404 for `/api/analysis/visualization-points` and `/visualization`.

- [ ] **Step 3: Implement the endpoint**

Add optional `platform_code`, `product_id`, `currency`, and `category_l1` query parameters. Query matching observations, deduplicate and classify products, obtain USD/CNY once only when USD observations exist, build points, then apply `category_l1`. Return classifications for the filtered point set and metadata containing `total`, `normalized_total`, `review_total`, `exchange_rate`, and `warnings`.

Catch only `ExchangeRateUnavailable` around rate retrieval; append a warning and pass `None` so original USD values remain visible. Do not return raw SQLAlchemy objects or raw user references.

- [ ] **Step 4: Add the page route**

Register a `FileResponse(STATIC_DIR / "visualization.html")` route in `main.py`. Keep API administrator authentication unchanged; the static page itself does not embed credentials.

- [ ] **Step 5: Run Task 3 tests**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_visualization_api -v`
Expected: all Task 3 tests PASS; the page route test is added with Task 4 if the file does not yet exist.

- [ ] **Step 6: Commit**

```bash
git add api/app/analysis_api.py api/app/main.py tests/test_visualization_api.py
git commit -m "feat: expose visualization observation points"
```

---

### Task 4: Standalone High-Dimensional Visualization Page

**Files:**
- Create: `api/app/static/visualization.html`
- Modify: `api/app/static/index.html`
- Modify: `api/app/static/analysis.html`
- Test: `tests/test_visualization_page.py`

**Interfaces:**
- Consumes: `/api/analysis/visualization-points` with `X-API-Key` and the same `obs_api_key` local-storage entry used by existing admin pages.
- Produces: filters, four-dimensional SVG scatter plot, classification summary, detailed tooltip, raw point table, and empty/error states.

- [ ] **Step 1: Write failing page-contract tests**

Assert that the new page exists, calls the endpoint, uses `normalized_price_cents` for chart eligibility, retains null-normalized points in the table, does not contain `DEEPSEEK_API_KEY`, and is linked from both existing admin analysis surfaces. Add a Node syntax check for the extracted script and a small DOM-free eligibility test:

```javascript
const chartable = points.filter(p => Number.isFinite(p.normalized_price_cents) && p.fetch_ts);
if (chartable.length !== 1) throw Error('null normalized price must not be plotted');
if (points.length !== 2) throw Error('raw points must remain available');
```

- [ ] **Step 2: Run page tests and verify failure**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_visualization_page -v`
Expected: FAIL because `visualization.html` and navigation links do not exist.

- [ ] **Step 3: Implement the page and navigation**

Build a responsive standalone page with an API-key input, platform/category/currency filters, summary cards, an SVG chart, tooltip, and table. Encode time on X, normalized CNY price on Y, L1 category with color, and platform with circle/square/triangle/diamond shapes. Display original currency amounts with their ISO code and normalized amounts with `¥`; never label unsupported original values as CNY.

Show warnings for stale/missing exchange rates and uncategorized review items. Escape all API-originated strings before inserting HTML. Use native browser APIs only.

- [ ] **Step 4: Run page and routing tests**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_visualization_page tests.test_visualization_api tests.test_vercel_entry -v`
Expected: all selected tests PASS, including `/visualization` through the Vercel rewrite if that route assertion is added.

- [ ] **Step 5: Commit**

```bash
git add api/app/static/visualization.html api/app/static/index.html api/app/static/analysis.html tests/test_visualization_page.py tests/test_visualization_api.py tests/test_vercel_entry.py
git commit -m "feat: add high-dimensional observation visualization"
```

---

### Task 5: Deployment Configuration and Full Regression

**Files:**
- Modify: `README.md`
- Modify: `DEPLOY.md`

**Interfaces:**
- Consumes: environment variables introduced in Task 1.
- Produces: operator instructions that configure classification without committing secrets.

- [ ] **Step 1: Document server configuration**

Add exact environment names and safe examples:

```text
DEEPSEEK_API_KEY=<set-in-local-or-hosting-secret-settings>
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=v4.1flash
```

Explain that missing keys produce review-required fallback classifications, the cache is the separate `product_category_cache` table, and changing a product name creates a new classification cache entry.

- [ ] **Step 2: Run the complete regression suite**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest discover -s tests -q`
Expected: all tests PASS with no external network dependency.

- [ ] **Step 3: Verify repository and secret hygiene**

Run: `git diff --check && git status --short`
Expected: no whitespace errors; only intended documentation changes remain before commit. Search changed files for the user-supplied token and confirm it is absent without printing the token.

- [ ] **Step 4: Commit**

```bash
git add README.md DEPLOY.md
git commit -m "docs: configure product classification service"
```
