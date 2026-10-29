# Three-Dimensional Observation Space Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an administrator-linked `/space` experience with non-blocking cached classification, deterministic observation relationships, statistical context, local Three.js 3D/2D interaction, filtering, playback, comparison, mock mode, and CSV export.

**Architecture:** Reuse existing observation-point and exchange-rate code. Compute enrichments, statistics, and edges in a focused backend module; serve cached points immediately while a background task classifies missing products. Keep the Three.js scene in a standalone static module and vendor all runtime assets.

**Tech Stack:** FastAPI, SQLAlchemy, NumPy/SciPy, unittest, Three.js 0.170.0, OrbitControls, native ES modules, HTML/CSS/JavaScript.

## Global Constraints

- Never modify Observation rows, integer-cent units, original currencies, UTC semantics, or identity rules.
- Never expose raw `user_ref`, full User-Agent, admin credentials, or DeepSeek credentials.
- The points request must not synchronously call the classification model.
- No runtime CDN; use local Three.js 0.170.0 and matching OrbitControls.
- Points use `THREE.Points + BufferGeometry`; lines use `THREE.LineSegments`; picking uses `THREE.Raycaster`.
- Small groups (`n<3`) are descriptive only; price-gap formula is `abs(a-b)/max(a,b)` with normalized prices only.
- Maximum 1,000 returned edges and 20,000 returned observations, with explicit truncation metadata.
- The plugin remains version 1.1.0.

---

### Task 1: Observation Enrichment, Statistics, and Relationship Edges

**Files:**
- Create: `api/app/space.py`
- Test: `tests/test_space_computation.py`

**Interfaces:**
- Produces `enrich_points(points, observations) -> list[dict]`, `compute_price_statistics(points) -> list[dict]`, `build_edges(points, statistics, enabled=None, time_threshold_hours=24, limit=1000) -> tuple[list[dict], int, bool]`, and `platform_replication(points, statistics) -> dict`.

- [ ] **Step 1: Write failing relationship tests**

Create points with two products, two users, controlled timestamps, promotions, and normalized prices. Assert same-product, same-user, same-user-product, 24-hour-neighbor, promo-difference, and 5%-median-gap edges. Include EUR/null-normalized points and assert no `PRICE_GAP` is generated for them.

```python
edges, candidate_count, truncated = build_edges(points, statistics)
self.assertIn(("PRICE_GAP", "a1", "b1"), {(e["type"], e["source"], e["target"]) for e in edges})
self.assertFalse(any(e["type"] == "PRICE_GAP" and e["source"] == "eur1" for e in edges))
```

- [ ] **Step 2: Verify the module-missing failure**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_computation -v`
Expected: FAIL because `app.space` does not exist.

- [ ] **Step 3: Implement enrichment and deterministic statistics**

Copy points without mutating inputs. Add `discount_coupon_amount_cents` from matching observations, per-product `sample_size`, per-product normalized-median `price_deviation`, and default `price_gap_direction=None`. Group normalized prices by `product_key` and non-null pseudonym. For every user pair calculate sample sizes, medians, difference percentage, `suspected`, and `status="DESCRIPTIVE_SMALL_SAMPLE"` when either group has fewer than 3. Otherwise run `scipy.stats.mannwhitneyu` and `ttest_ind(equal_var=False)` and set `status="TESTS_AVAILABLE"`.

- [ ] **Step 4: Implement edge construction and caps**

Evaluate pairs in input order. `TIME_NEIGHBOR` uses absolute UTC time difference and the configurable threshold. `PRICE_GAP` connects cross-user point pairs only for statistics where `suspected=True`; unsupported currencies never enter those statistics. Stop at `limit`, return the pre-truncation candidate count and a truncation flag. Test exactly 1,000 edges and `truncated=True` for 1,001 candidates.

- [ ] **Step 5: Implement platform replication and test statistical thresholds**

Mark platform-level suspected only when at least two distinct products on that platform have suspected group comparisons. Verify `n=2` groups have null test p-values and `n=3` groups have finite MWU/Welch fields.

- [ ] **Step 6: Run tests and commit**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_computation -v`
Expected: all computation tests PASS.

```bash
git add api/app/space.py tests/test_space_computation.py
git commit -m "feat: compute observation relationships for space"
```

---

### Task 2: Cached-Only Points API and Background Classification

**Files:**
- Modify: `api/app/product_categories.py`
- Create: `api/app/space_api.py`
- Modify: `api/app/main.py`
- Test: `tests/test_space_api.py`

**Interfaces:**
- Consumes: Task 1 computation functions and existing `build_visualization_point`, `latest_rate`, and cache model.
- Produces `get_cached_classifications(db, observations) -> dict`, `GET /api/space/points`, and `GET /api/space/classification-status`.

- [ ] **Step 1: Write failing non-blocking API tests**

Use an isolated SQLite dependency override. Seed observations without classification cache and patch the model caller to raise if invoked synchronously. Assert authenticated response is immediate and contains empty category fields, no raw UUID, a classification task status, and no model-generated relation. Test unauthenticated 401 and cached-category responses.

- [ ] **Step 2: Verify 404 and missing-helper failures**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_api -v`
Expected: FAIL because `/api/space/points` and the cached-only helper do not exist.

- [ ] **Step 3: Add cache-only classification lookup**

Refactor cache loading out of `classify_products` into `get_cached_classifications`. Return row dictionaries keyed by `cache_key`, with no model calls. Keep existing classification tests green.

- [ ] **Step 4: Implement the points route**

Query newest observations with `limit` default/max 20,000 and return `total` separately. Build points with cached or empty classifications, retrieve USD/CNY once if needed, enrich, compute statistics/edges, and return meta. Attach a background job only for uncached products and only when no job is running.

- [ ] **Step 5: Implement task status and worker**

Protect a small process-local status dictionary with a lock. Worker creates a new `SessionLocal`, processes deduplicated products in chunks of at most 50, records counts and UTC timestamps, and always resets running state. Missing API key yields `not_configured`; model errors yield `error` without changing observations. Tests call the worker with a fake classifier and verify status transitions.

- [ ] **Step 6: Run API and existing category tests**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_api tests.test_product_categories -v`
Expected: all selected tests PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/product_categories.py api/app/space_api.py api/app/main.py tests/test_space_api.py
git commit -m "feat: serve non-blocking observation space data"
```

---

### Task 3: Local Three.js Runtime and Page Shell

**Files:**
- Create: `api/app/static/vendor/three.module.min.js`
- Create: `api/app/static/vendor/OrbitControls.js`
- Create: `api/app/static/vendor/README.md`
- Create: `api/app/static/space.html`
- Modify: `api/app/main.py`
- Test: `tests/test_space_page.py`

**Interfaces:**
- Produces `/space`, `/static/vendor/three.module.min.js`, and `/static/vendor/OrbitControls.js`; page imports `/static/js/space.js` as a module.

- [ ] **Step 1: Write failing route and asset tests**

Assert `/space` contains the required legal-boundary text, no admin-key input, no external CDN URL, and no raw `user_ref` label. Assert console navigation links to `/space`, both vendor files are non-empty, OrbitControls imports the bare `three` specifier, and the import map maps it to the local module.

- [ ] **Step 2: Verify failures**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_page -v`
Expected: FAIL because page and assets are absent.

- [ ] **Step 3: Vendor pinned runtime files**

Download Three.js 0.170.0 `three.module.min.js` and `examples/jsm/controls/OrbitControls.js` from the official unpkg package during development. Record package version and source URLs in `vendor/README.md`. Do not reference those URLs from runtime HTML/JavaScript.

- [ ] **Step 4: Build accessible page shell and routes**

Create filter toolbar, view/coordinate controls, canvas container, time slider/play controls, relation toggles, statistics/compare panels, point table, tooltip, export and mock buttons. Add the exact research-only notice. Mount `/static` with `StaticFiles`, register `/space`, and add the console sidebar link.

- [ ] **Step 5: Run shell tests and commit**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_page tests.test_vercel_entry -v`
Expected: selected tests PASS.

```bash
git add api/app/static/vendor api/app/static/space.html api/app/static/index.html api/app/main.py tests/test_space_page.py
git commit -m "feat: add local Three.js space shell"
```

---

### Task 4: Three.js Scene, Filters, Playback, Comparison, Mock, and CSV

**Files:**
- Create: `api/app/static/js/space.js`
- Create: `api/app/static/js/space-mock.js`
- Modify: `api/app/static/space.html`
- Test: `tests/test_space_page.py`

**Interfaces:**
- Consumes: `/api/space/points`, `/api/space/classification-status`, local Three.js modules.
- Produces: complete 3D/2D/table scene and client interactions.

- [ ] **Step 1: Add failing JavaScript contract tests**

Assert source contains `THREE.Points`, `THREE.BufferGeometry`, `THREE.LineSegments`, `THREE.Raycaster`, `OrbitControls`, `normalized_price_cents`, `PRICE_GAP`, `toCSV`, `play`, and `window.innerWidth`. Check module syntax with Node. Extract pure functions for business coordinates, deterministic feature projection, filtering, and CSV and run behavior tests.

- [ ] **Step 2: Implement scene and point shader**

Use one BufferGeometry for all points with position, color, size, alpha, and missing-normalization border attributes. Use one ShaderMaterial on THREE.Points for per-point size/opacity/border. Build one LineSegments object per enabled relation type. Raycast against Points for hover/click; OrbitControls supplies rotation, zoom, and right-drag pan.

- [ ] **Step 3: Implement coordinates and interactions**

Business coordinates normalize time, category level, and backend price deviation. Feature mode hashes numeric/categorical feature names into deterministic signed 3D projections. Support platform/category/pseudonym/city/promo/price-gap filters, search, two-user comparison, product highlighting, and color dimensions.

- [ ] **Step 4: Implement playback, table, CSV, and mock**

Filter by start/end and current playback time. Animate the slider with a stoppable timer. Render filtered raw points in the table and comparison sequences. Export escaped CSV with pseudonyms only. Mock is explicitly labeled and only loaded on user action when no real points are available.

- [ ] **Step 5: Run JavaScript and full page tests**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest tests.test_space_page -v`
Expected: all page tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/static/js/space.js api/app/static/js/space-mock.js api/app/static/space.html tests/test_space_page.py
git commit -m "feat: implement interactive three-dimensional observation space"
```

---

### Task 5: Documentation and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the administrator entry and operating behavior**

Document `/space`, cached-only first load, background classification status, local Three.js assets, mock labeling, relation cap, 20,000-point sampling, and research-only interpretation.

- [ ] **Step 2: Run complete regression**

Run: `"C:/Users/Guo/Documents/kimi/tasks/2026-10-28/01-50-57-bab03cf5/repo/.venv/Scripts/python" -m unittest discover -s tests -q`
Expected: all tests PASS without network or real credentials.

- [ ] **Step 3: Verify clean diff and commit**

Run: `git diff --check && git status --short`
Expected: only README before commit and clean worktree afterward.

```bash
git add README.md
git commit -m "docs: describe three-dimensional observation space"
```
