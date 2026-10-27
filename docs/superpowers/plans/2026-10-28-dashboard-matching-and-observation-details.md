# Dashboard Matching and Observation Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit comparison candidates to products collected by the current anonymous user and make each personal observation expandable into a safe detailed view.

**Architecture:** Add a user-scoped product aggregation route beside the existing pool routes, then point both comparison workflows at it. Reuse the existing platform filter on pooled observations and the fields already returned by `/api/my/observations`; no database migration or plugin package change is required.

**Tech Stack:** FastAPI, SQLAlchemy, vanilla JavaScript/HTML/CSS, Python unittest, FastAPI TestClient.

## Global Constraints

- Match products by `platform_code + product_id`, never by product ID alone.
- Preserve existing anonymization, analysis algorithms, identity synchronization, and pagination behavior.
- Empty values render as `—`; dynamic text and URLs must be escaped.
- Plugin content changes require a manifest semantic-version bump; this dashboard-only change does not modify the plugin.
- Run `../repo/.venv/Scripts/python -m unittest discover tests -v` before delivery.

---

### Task 1: Current-user product scope API

**Files:**
- Modify: `api/app/pool_api.py`
- Create: `tests/test_dashboard_comparison_scope.py`

**Interfaces:**
- Produces: `GET /api/pool/my-products?keyword=&platform_code=&limit=100` with `X-User-Id`.
- Returns: `{products: [{product_id, product_name, platform_code, n, latest_fetch_ts}]}`.
- Consumes: existing `require_user`, `get_db`, `Observation`, and pool observation filtering.

- [ ] **Step 1: Write failing API tests**

Create tests using an isolated SQLite database and `TestClient(app)`. Insert observations for user A, user B, two platforms sharing product ID `SHARED`, and another product. Assert user A receives only user A products, one row per platform/product pair, correct counts, keyword/platform filtering, and 401/403 without identity. Assert pooled observations with both filters do not mix platforms.

```python
response = client.get('/api/pool/my-products', headers={'X-User-Id': USER_A})
self.assertEqual(response.status_code, 200)
self.assertEqual({(p['platform_code'], p['product_id']) for p in response.json()['products']},
                 {('jd', 'SHARED'), ('amazon', 'SHARED'), ('jd', 'ONLY-A')})
response = client.get('/api/pool/observations?product_id=SHARED&platform_code=jd',
                      headers={'X-User-Id': USER_A})
self.assertTrue(all(o['platform_code'] == 'jd' for o in response.json()['items']))
```

- [ ] **Step 2: Run tests to verify the new route fails**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_dashboard_comparison_scope -v`
Expected: 404 for `/api/pool/my-products`; existing platform-filter test passes.

- [ ] **Step 3: Implement the scoped aggregation**

Add a `/my-products` route that filters `Observation.user_ref == user_id`, groups by platform/product/name, counts observations, and orders by count descending. Do not apply the global route's `count >= 2` condition.

```python
@router.get('/my-products')
def my_pool_products(keyword: Optional[str] = Query(default=None),
                     platform_code: Optional[str] = Query(default=None),
                     limit: int = Query(default=100, ge=1, le=POOL_PRODUCTS_MAX),
                     user_id: str = Depends(require_user), db=Depends(get_db)):
    query = db.query(Observation.product_id, Observation.product_name,
                     Observation.platform_code, func.count().label('n'),
                     func.max(Observation.fetch_ts).label('latest_fetch_ts'))
    query = query.filter(Observation.user_ref == user_id)
    query = query.group_by(Observation.product_id, Observation.product_name,
                           Observation.platform_code)
    # Apply optional keyword/platform filters, limit, and serialize dates as ISO strings.
```

Move `from sqlalchemy import func` to module scope so both product routes share it.

- [ ] **Step 4: Run API tests and commit**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_dashboard_comparison_scope -v`
Expected: all scoped API tests pass.

```bash
git add api/app/pool_api.py tests/test_dashboard_comparison_scope.py
git commit -m "feat: scope comparison products to current user"
```

---

### Task 2: Restrict both comparison workflows

**Files:**
- Modify: `api/app/static/lab.html`
- Test: `tests/test_dashboard_comparison_scope.py`

**Interfaces:**
- Consumes: `/api/pool/my-products` and `/api/pool/observations` from Task 1.
- Produces: search and automatic analysis limited to current-user products; exact platform/product observation requests.

- [ ] **Step 1: Add failing frontend contract tests**

Read `lab.html` as UTF-8 and assert both candidate requests use `/api/pool/my-products`, `fetchAndAnalyze` includes both encoded keys, and copy says “本机已采集商品”. Assert the file no longer contains `api('/api/pool/products?limit=100')`.

```python
self.assertEqual(text.count("api('/api/pool/my-products?limit=100"), 2)
self.assertIn("platform_code=' + encodeURIComponent(product.platform_code)", text)
self.assertIn("product_id=' + encodeURIComponent(product.product_id)", text)
self.assertNotIn("api('/api/pool/products?limit=100')", text)
```

- [ ] **Step 2: Run tests to verify frontend failure**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_dashboard_comparison_scope -v`
Expected: old global product endpoints and missing platform request parameter fail.

- [ ] **Step 3: Update requests and user-facing copy**

Replace both candidate endpoints with `/api/pool/my-products`. Build the analysis URL from both fields:

```javascript
return api('/api/pool/observations?platform_code=' + encodeURIComponent(product.platform_code) +
  '&product_id=' + encodeURIComponent(product.product_id) + '&limit=500')
```

Update automatic-mode copy to “本机已采集商品中观测数最多的前 10 个”，and distinguish “尚未采集商品” from “没有匹配的本机商品”. Add Amazon to the platform selector.

- [ ] **Step 4: Run tests and commit**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_dashboard_comparison_scope -v`
Expected: all API and frontend scope tests pass.

```bash
git add api/app/static/lab.html tests/test_dashboard_comparison_scope.py
git commit -m "feat: compare only locally collected products"
```

---

### Task 3: Expandable observation details

**Files:**
- Modify: `api/app/static/me.html`
- Create: `tests/test_observation_details.py`

**Interfaces:**
- Consumes: existing `ObservationOut` objects returned in `/api/my/observations` pages.
- Produces: `renderObservationDetails(o)`, `toggleObservation(index)`, accessible summary rows and independent detail rows.

- [ ] **Step 1: Add failing detail contract tests**

Assert the page contains a detail renderer and toggle handler, summary rows expose `data-obs-index`, `tabindex="0"`, `role="button"`, and `aria-expanded`, and details include observation ID, product URL, seller, promotion, membership, device, origin, and synchronization fields. Assert unsafe link schemes are rejected by an HTTP/HTTPS check.

```python
for marker in ('function renderObservationDetails(o)', 'function toggleObservation(index)',
               'data-obs-index', 'aria-expanded', 'observation_id', 'product_url',
               'seller_id', 'membership_level', 'hardware_concurrency', 'synced_at'):
    self.assertIn(marker, text)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_observation_details -v`
Expected: missing detail renderer and accessibility markers fail.

- [ ] **Step 3: Implement row expansion and safe formatting**

Cache `currentItems` on each successful page load. Render summary rows followed by hidden detail rows. `toggleObservation(index)` changes only the selected row's `hidden`, `aria-expanded`, and open class. Use the same handler for click and Enter/Space, preventing the keyboard event's default action.

Use `esc()` for every text/attribute, `fmtBool()` for booleans, and `fmtCents(value, o.currency)` for amounts. Render product links only when `new URL()` yields HTTP/HTTPS; otherwise show escaped plain text. Detail rows use `colspan="5"` and a responsive definition grid. Include all fields listed in the approved spec.

- [ ] **Step 4: Run focused and complete tests**

Run: `../repo/.venv/Scripts/python -m unittest tests.test_observation_details -v`
Expected: all detail tests pass.

Run: `../repo/.venv/Scripts/python -m unittest discover tests -v`
Expected: entire suite passes.

```bash
git add api/app/static/me.html tests/test_observation_details.py
git commit -m "feat: expand personal observation details"
```

---

### Task 4: Delivery verification

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Inspect the final diff and repository state**

Run: `git diff main~3 --check && git status --short`
Expected: no whitespace errors or unintended files.

- [ ] **Step 2: Verify routes and rendered pages**

Use API tests to confirm identity isolation and exact platform/product matching. Confirm the personal page still exposes the five summary columns and the comparison page retains local saved datasets.

- [ ] **Step 3: Merge and push**

Run the complete suite on the merged `main`, then push without force. Report the pushed commit and test count. Do not claim completion if either fails.
