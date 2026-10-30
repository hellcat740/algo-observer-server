# Semantic Observation Space Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/space` around fixed XY category anchors, Z collection time, user-colored observations, navigable unbounded grids, and a dashboard-shared two-stage price comparison rule.

**Architecture:** Pure JavaScript modules own category layout, user colors, comparison classification, and comparison-pair generation; Three.js only renders their results. The existing space API adds the fixed taxonomy without changing legacy statistics, while `lab.html` and `/space` share the same comparison module.

**Tech Stack:** FastAPI, native browser ES modules, Three.js r170, Node `node:test`, Python pytest / unittest.

## Global Constraints

- XY is the category plane; Z is collection time and the camera up axis.
- Red requires absolute mean difference `>= 10` yuan, relative difference `> 20%` against the low-price side, and at least 3 valid prices on both sides.
- Yellow covers severe thresholds with insufficient samples, attention thresholds (`>= 5` yuan and `>= 5%`) below red, or exactly one attention threshold; green requires both attention thresholds to miss.
- Keep legacy backend median statistics, `PRICE_GAP`, gap filters, platform replication, all existing APIs and core workflows unchanged unless explicitly listed.
- No framework, CDN, external embedding service, new dependency, or subagent.
- Every code task follows test-first and ends with a focused commit; never add the untracked `algo-observer-plugin/` directory.

---

### Task 1: Shared comparison rule

**Files:**
- Create: `api/app/static/js/comparison-rule.js`
- Create: `tests/js/comparison-rule.test.mjs`

**Interfaces:**
- Produces: `comparePriceGroups(groupA, groupB)` where each group is `{name: string, prices: number[]}` in yuan.
- Produces: `{low, high, diff, diffPct, smallSample, conclusion, reason, thresholds}`; `conclusion` is `red | yellow | green | nodata`.
- Produces: `COMPARISON_THRESHOLDS = {attentionAbsolute: 5, severeAbsolute: 10, attentionPercent: 5, severePercent: 20, minimumSamples: 3}`.

- [ ] **Step 1: Write failing boundary tests**

Use `node:test` and `assert/strict`. Test three identical prices per side, plus these exact cases:

```js
assert.equal(comparePriceGroups(
  {name: 'A', prices: [100, 100, 100]},
  {name: 'B', prices: [125, 125, 125]},
).conclusion, 'red');
assert.equal(comparePriceGroups(
  {name: 'A', prices: [100, 100, 100]},
  {name: 'B', prices: [120, 120, 120]},
).conclusion, 'yellow'); // exactly 20% is not severe
assert.equal(comparePriceGroups(
  {name: 'A', prices: [1, 1, 1]},
  {name: 'B', prices: [2, 2, 2]},
).conclusion, 'yellow'); // high percentage, insufficient absolute difference
assert.equal(comparePriceGroups(
  {name: 'A', prices: [100, 100, 100]},
  {name: 'B', prices: [104, 104, 104]},
).conclusion, 'green');
assert.equal(comparePriceGroups(
  {name: 'A', prices: [100, 100]},
  {name: 'B', prices: [125, 125, 125]},
).conclusion, 'yellow');
```

Also test input ordering is normalized to low/high, invalid prices are excluded, empty sides return `nodata`, zero low-side averages do not leak `Infinity` into `reason`, and exactly 10 yuan with more than 20% is red.

- [ ] **Step 2: Run tests and confirm the module is missing**

Run: `node --test tests/js/comparison-rule.test.mjs`  
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `comparison-rule.js`.

- [ ] **Step 3: Implement the pure rule**

Export the constants and a single pure function. Filter to finite, non-negative prices, calculate arithmetic means, orient low/high, calculate `diff = high.mean - low.mean`, and calculate `diffPct` as zero when both means are zero and `Infinity` only when the low mean is zero and the high mean is positive. Apply this exact decision order:

```js
const severe = diff >= 10 && diffPct > 20;
const attention = diff >= 5 && diffPct >= 5;
const attentionHitCount = Number(diff >= 5) + Number(diffPct >= 5);
const conclusion = severe && !smallSample ? 'red'
  : severe || attention || attentionHitCount === 1 ? 'yellow'
  : 'green';
```

Return human-readable Chinese reasons that explicitly mention insufficient samples, exact severe thresholds, attention thresholds, single-threshold hits, or both misses. Do not read the DOM or format HTML.

- [ ] **Step 4: Run the tests and syntax check**

Run: `node --test tests/js/comparison-rule.test.mjs`  
Expected: all comparison tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/static/js/comparison-rule.js tests/js/comparison-rule.test.mjs
git commit -m "feat: add shared mixed price comparison rule"
```

### Task 2: Stable category layout, taxonomy response, and user colors

**Files:**
- Create: `api/app/static/js/space-layout.js`
- Create: `tests/js/space-layout.test.mjs`
- Modify: `api/app/space_api.py`
- Modify: `api/app/static/js/space-mock.js`
- Modify: `tests/test_space_page.py`
- Modify: `tests/test_space_computation.py`

**Interfaces:**
- Consumes: backend `CATEGORY_TAXONOMY` and existing observation points.
- Produces: `buildSemanticLayout(points, taxonomy)` returning `{positions: Map, categories: Array, anchors: Map}`; positions are `[x, y, z]` with time in Z.
- Produces: `userColor(pseudonym)` returning a stable CSS hex color.
- Produces: API top-level `category_taxonomy` with the original dictionary shape.

- [ ] **Step 1: Write failing layout and taxonomy tests**

Test two L1 anchors are at least 80 units apart, L2 offsets use only `-16, 0, 16`, every name offset is at most 4 units, repeated products share XY, and changing the filtered input does not change a layout rebuilt from the same complete set. Test earliest/latest times map to Z `0/100`, a single timestamp maps to Z `50`, and invalid timestamps map to Z `0`.

Test 90% core cylinders use fixed anchors, non-empty minimum radius/height, and no geometry for empty categories. Test `userColor('u_a')` is stable and unknown users use gray. Add a Python API assertion that `category_taxonomy['手机数码']` contains `手机`, and update the mock test to require the same taxonomy shape.

- [ ] **Step 2: Run tests and confirm failure**

Run: `node --test tests/js/space-layout.test.mjs`  
Expected: FAIL because `space-layout.js` does not exist.  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py -q`  
Expected: the new taxonomy assertion FAILS.

- [ ] **Step 3: Implement taxonomy passthrough**

Import `CATEGORY_TAXONOMY` in `space_api.py` and add `"category_taxonomy": CATEGORY_TAXONOMY` to the `/points` return object. Mirror the complete taxonomy in the canned mock response; do not alter `statistics`, `edges`, or point fields.

- [ ] **Step 4: Implement the deterministic layout**

Use four-column L1 grids with 80-unit spacing centered around XY zero and three-column L2 grids with offsets `-16/0/16`. Select the latest non-empty product name per `product_key`; normalize whitespace and case, add word tokens where `Intl.Segmenter` exists, and add character 2-/3-grams. Hash features with fixed FNV-1a salts, project to two signed sums, normalize, and clamp the resulting XY offset to radius 4. Missing names use offset `[0,0]`.

Compute time from the complete point set. Compute L1/L2 cylinder descriptors from the nearest `ceil(n * 0.9)` XY distances around their fixed anchors, with radius margin 1, minimum radius 2, base Z 0, and minimum height 2. Return one descriptor per non-empty observed category, not per empty taxonomy entry. Export `userColor` using the existing palette and stable hash, with `#9b938b` for missing pseudonyms.

- [ ] **Step 5: Run focused tests**

Run: `node --test tests/js/space-layout.test.mjs`  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py tests/test_space_computation.py -q`  
Expected: all focused tests PASS and legacy space statistics remain unchanged.

- [ ] **Step 6: Commit**

```bash
git add api/app/space_api.py api/app/static/js/space-layout.js api/app/static/js/space-mock.js tests/js/space-layout.test.mjs tests/test_space_page.py tests/test_space_computation.py
git commit -m "feat: add stable semantic category layout"
```

### Task 3: Semantic scene foundation and navigation

**Files:**
- Create: `api/app/static/js/space-navigation.js`
- Create: `tests/js/space-navigation.test.mjs`
- Modify: `api/app/static/js/space-core.js`
- Modify: `api/app/static/js/space.html`
- Modify: `api/app/static/js/space.js`
- Modify: `tests/test_observation_space_theme.py`
- Modify: `tests/test_space_page.py`

**Interfaces:**
- Consumes: `buildSemanticLayout(points, taxonomy)` and `userColor`.
- Produces: `movementVector(keys, forward, right, speed, deltaSeconds)` returning an XY translation for camera and OrbitControls target.
- Produces: a scene with no `AxesHelper`, no fixed `GridHelper`, no coordinate-mode or color-dimension controls.

- [ ] **Step 1: Write failing navigation and page-contract tests**

Test neutral movement is `[0,0]`, W follows the normalized forward XY projection, D follows right XY, diagonal movement is normalized, delta time scales movement, and degenerate forward/right vectors return zero. Update page tests to require `buildSemanticLayout`, `userColor`, WASD handling, and `comparison-rule.js`; reject `businessCoordinates`, `featureProjection`, `coordinateMode`, `colorDimension`, and `AxesHelper`.

- [ ] **Step 2: Run tests and confirm failure**

Run: `node --test tests/js/space-navigation.test.mjs`  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py tests/test_observation_space_theme.py -q`  
Expected: new module and page-contract assertions FAIL.

- [ ] **Step 3: Implement pure navigation and remove old coordinate logic**

Implement `movementVector` with no DOM dependency. In `space-core.js`, retain only `filterPoints`, CSV escaping, and `toCSV`; remove the two old coordinate exports. In `space.html`, remove the two obsolete selects, set the fixed research copy to XY category / Z time, show WASD instructions, and add a visible-user legend container plus a checked `ACTIVE_COMPARISON` layer checkbox.

- [ ] **Step 4: Rebuild the scene foundation**

In `space.js`, set `camera.up.set(0,0,1)` and use a Z-up default camera. Build layout once in `setData`, store it in `state.layout`, and render filtered points from the cached position map. Flatten only Z in 2D. Color every point with `userColor`, update the visible-user legend, and keep point selection, dimming, borders, table, filters, playback, existing relations, CSV, mock loading, and admin fetch behavior.

Add three shader-based orthogonal grids centered on `controls.target`, with neutral lines, distance fade, target snapping, and no colored axes. Register WASD key state only outside editable controls and only in 3D; translate camera and target together in the animation loop and clear keys on blur, hidden visibility, and view changes. Limit pixel ratio to 2 and stop motion work while the document is hidden.

- [ ] **Step 5: Run focused tests and syntax checks**

Run: `node --test tests/js/space-navigation.test.mjs tests/js/space-layout.test.mjs`  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py tests/test_observation_space_theme.py -q`  
Run: `node --check api/app/static/js/space.js`  
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/static/js/space-core.js api/app/static/js/space-navigation.js api/app/static/js/space.js api/app/static/space.html tests/js/space-navigation.test.mjs tests/test_observation_space_theme.py tests/test_space_page.py
git commit -m "feat: rebuild semantic space navigation and point encoding"
```

### Task 4: Category volumes and origin labels

**Files:**
- Create: `api/app/static/js/space-volumes.js`
- Create: `tests/js/space-volumes.test.mjs`
- Modify: `api/app/static/js/space.js`
- Modify: `tests/test_space_page.py`

**Interfaces:**
- Consumes: `state.layout.categories` descriptors from Task 2.
- Produces: `categoryOpacity(level, distance)` and `comparisonCircleGeometry(points, cameraRight)` pure geometry helpers.
- Produces: Z-aligned dark cylinders and labels anchored at Z 0.

- [ ] **Step 1: Write failing visual-math tests**

Test opacity is bounded and decreases as camera distance decreases, with L1 far/near limits `0.14/0.015` and L2 `0.11/0.01`. Test comparison circle center/radius includes every supplied point after projection onto the plane formed by Z and normalized camera-right XY, with a minimum radius for coincident points.

- [ ] **Step 2: Run tests and confirm failure**

Run: `node --test tests/js/space-volumes.test.mjs`  
Expected: FAIL because `space-volumes.js` does not exist.

- [ ] **Step 3: Implement pure visual math**

Export clamped distance interpolation for category opacity and a circle descriptor `{center, radius, horizontal}` from 3D points. Use bounding-box center, project points onto normalized XY camera-right and Z, and use the maximum projected distance plus margin 1 and minimum radius 2.

- [ ] **Step 4: Render category volumes and labels**

Create open-ended `CylinderGeometry` rotated from its default Y axis to Z, using transparent double-sided materials with `depthWrite:false`. Render cylinders before points, update opacity from camera distance, and only show categories with visible points. Generate local Canvas textures for L1/L2 names, anchor labels at category XY and Z 0, clamp their screen size, prioritize L1 at distance, and keep the selected product's L2 label. Dispose textures, materials, and geometry on rebuild.

- [ ] **Step 5: Run focused tests**

Run: `node --test tests/js/space-volumes.test.mjs tests/js/space-layout.test.mjs`  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py -q`  
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/static/js/space-volumes.js api/app/static/js/space.js tests/js/space-volumes.test.mjs tests/test_space_page.py
git commit -m "feat: add semantic category volumes and labels"
```

### Task 5: Current comparison geometry and dashboard synchronization

**Files:**
- Create: `api/app/static/js/space-comparison.js`
- Create: `tests/js/space-comparison.test.mjs`
- Modify: `api/app/static/js/space.js`
- Modify: `api/app/static/lab.html`
- Modify: `tests/test_space_page.py`
- Modify: `tests/test_observation_space_theme.py`

**Interfaces:**
- Consumes: `comparePriceGroups`, filtered points, selected product, selected users, cached layout positions, and `comparisonCircleGeometry`.
- Produces: `buildComparisonPairs(pointsA, pointsB, limit=1000)` returning `{pairs, candidateCount, truncated}` with stable observation-ID ordering.
- Produces: one shared conclusion driving space lines, circle, panel, and `lab.html` badges/reasons/saved summaries.

- [ ] **Step 1: Write failing pair and integration tests**

Test only cross-user points with finite normalized CNY prices participate, pair ordering is stable, 1001 candidates truncate to 1000 with `truncated=true`, and comparison statistics still use all points. Assert both `space.js` and `lab.html` import `comparison-rule.js`, and the dashboard contains no independent `diffPct >= 5` red/green decision.

- [ ] **Step 2: Run tests and confirm failure**

Run: `node --test tests/js/space-comparison.test.mjs`  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py tests/test_observation_space_theme.py -q`  
Expected: missing module and shared-import assertions FAIL.

- [ ] **Step 3: Implement comparison pair generation**

Filter invalid prices before generating pairs, sort both inputs by `observation_id`, generate deterministic cross-product pairs, stop at the limit, and return the pre-truncation candidate count. Do not mutate either input.

- [ ] **Step 4: Render the current comparison**

Resolve product and users using existing selection behavior. Use only currently filtered points from the selected product and two users; convert valid `normalized_price_cents` to yuan and call `comparePriceGroups`. Draw cross-user lines and the camera-updated circle in the shared red/yellow/green color, behind the points and with `depthWrite:false`. Respect `ACTIVE_COMPARISON`, show line truncation and excluded-price counts, and keep the existing price-series chart with user-matched colors. Rename the legacy panel heading to `全局中位数统计（后端研究口径）`.

- [ ] **Step 5: Synchronize the dashboard**

Load `comparison-rule.js` from the `lab.html` inline ES module while preserving its IIFE. Continue selecting the maximum-mean-difference user pair and calculating Welch statistics, but replace lines 336–366's independent conclusion logic with `comparePriceGroups(A, B)`. Map its low/high means back to the existing `r.pair`, use shared reasons in badges and notices, update the threshold copy to `关注 ≥5元且≥5%；严重 ≥10元且>20%，两侧各≥3`, and retain saved/exported fields with the new conclusion.

- [ ] **Step 6: Run all focused checks**

Run: `node --test tests/js/*.test.mjs`  
Run: `.venv\Scripts\python.exe -m pytest tests/test_space_page.py tests/test_space_computation.py tests/test_observation_space_theme.py -q`  
Run: `node --check api/app/static/js/space.js`  
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/static/js/space-comparison.js api/app/static/js/space.js api/app/static/lab.html tests/js/space-comparison.test.mjs tests/test_space_page.py tests/test_observation_space_theme.py
git commit -m "feat: synchronize spatial and dashboard comparisons"
```

### Task 6: Full regression and local visual verification

**Files:**
- Create: `docs/superpowers/verification/2026-10-31-semantic-observation-space.md`
- Modify only if a verified regression requires it: relevant implementation and test files from Tasks 1–5.

**Interfaces:**
- Consumes: the complete branch implementation and existing local preview command.
- Produces: recorded automated results, visual acceptance evidence, and any known limitations without changing unrelated behavior.

- [ ] **Step 1: Run the complete automated suite**

Run: `.venv\Scripts\python.exe -m pytest -q`  
Run: `node --test tests/js/*.test.mjs`  
Expected: all tests PASS; no skipped new comparison/layout tests.

- [ ] **Step 2: Start the temporary local preview**

Run: `npm run dev -- --host 127.0.0.1 --port 7100`  
Expected: Uvicorn serves the workspace application at `http://localhost:7100/space`. Stop this temporary server before the final response; Kimi Work owns the persistent preview lifecycle.

- [ ] **Step 3: Verify the mock scene**

Load clearly labeled mock data and verify wide L1 spacing, fixed L2 regions, product-time columns, three neutral grids, WASD plus OrbitControls, Z-aligned fading cylinders, Z-0 labels, stable user colors, point selection, filters, playback, legacy relations, 2D/table, and CSV. Confirm no RGB axes and no new browser console errors.

- [ ] **Step 4: Verify comparison parity**

For the same samples, verify `1→2` yuan is yellow, `100→120` is yellow, and `100→125` with three samples per side is red in both the space panel and dashboard. Verify lines/circle share the conclusion color, camera movement keeps the circle around its points, 1000-line truncation is explicit, and insufficient/invalid data produces no comparison geometry.

- [ ] **Step 5: Record evidence and commit**

Write the exact commands, test counts, browser checks, and unresolved limitations to the verification file. If any code fix was needed, add its regression test and rerun the full suite before committing.

```bash
git add docs/superpowers/verification/2026-10-31-semantic-observation-space.md
git commit -m "test: verify semantic observation space"
```
