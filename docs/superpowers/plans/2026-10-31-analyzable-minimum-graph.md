# Automatic Comparison Minimum Graphs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically select each product's maximum-median-gap user pair and render one red/yellow/green minimum spanning tree per analyzable product group.

**Architecture:** A pure JavaScript grouping module selects valid points and stable user pairs from the current filter. The geometry module keeps time-cluster ellipsoids but computes one global Prim tree across the full pair, and the existing Three.js renderer draws each group's geometry with the shared comparison conclusion.

**Tech Stack:** Browser ES modules, Three.js, Node.js `node:test`, Python `unittest` / pytest static regression tests.

## Global Constraints

- Only finite, non-negative `normalized_price_cents` values participate.
- Pairing uses the same product, two different users, and maximum median-price gap; ties use observation count then stable user-name ordering.
- Each non-coincident `N`-point group produces exactly `N−1` tree edges; no cluster-center edges remain.
- Colors must come from `comparePriceGroups`; do not introduce another threshold set.
- Do not modify input arrays or point objects.
- Every completed task requires its own Git commit; never add the untracked `algo-observer-plugin/` directory.

---

### Task 1: Automatic Analyzable Product Groups

**Files:**
- Modify: `api/app/static/js/space-comparison.js`
- Test: `tests/js/space-comparison.test.mjs`

**Interfaces:**
- Consumes: Observation point objects with `observation_id`, `product_key`, `product_name`, `user_pseudonym`, `normalized_price_cents`, and `fetch_ts`.
- Produces: `buildAnalyzableComparisonGroups(points)` returning `[{productKey, productName, userA, userB, pointsA, pointsB, points}]`; A is the low-median side and `points` is `[...pointsA, ...pointsB]`.

- [ ] **Step 1: Write failing grouping tests**

Append tests that construct three users with median prices 100, 110, and 130, assert that the 100/130 pair is selected, and assert that a second product is grouped independently. Add cases for invalid prices, a one-user product, median ties resolved by count then user name, deterministic time/ID point ordering, and an unchanged JSON snapshot of the input.

```js
import { buildAnalyzableComparisonGroups } from '../../api/app/static/js/space-comparison.js';

const analyzedPoint = (id, product, user, price, time = '2026-10-01T00:00:00Z') => ({
  observation_id: id, product_key: product, product_name: product,
  user_pseudonym: user, normalized_price_cents: price, fetch_ts: time,
});

test('groups select the maximum median gap user pair per product', () => {
  const input = [
    analyzedPoint('a1', 'p1', 'A', 10000), analyzedPoint('a2', 'p1', 'A', 10000),
    analyzedPoint('b1', 'p1', 'B', 11000), analyzedPoint('c1', 'p1', 'C', 13000),
    analyzedPoint('z1', 'p2', 'A', 20000), analyzedPoint('z2', 'p2', 'B', 20000),
  ];
  const snapshot = JSON.stringify(input);
  const groups = buildAnalyzableComparisonGroups(input);
  assert.deepEqual(groups.map(group => [group.productKey, group.userA, group.userB]), [
    ['p1', 'A', 'C'], ['p2', 'A', 'B'],
  ]);
  assert.equal(groups[0].points.length, 3);
  assert.equal(JSON.stringify(input), snapshot);
});

test('invalid prices and one-user products are not analyzable', () => {
  assert.deepEqual(buildAnalyzableComparisonGroups([
    analyzedPoint('bad', 'p1', 'A', NaN), analyzedPoint('negative', 'p1', 'B', -1),
    analyzedPoint('only', 'p2', 'A', 10000),
  ]), []);
});
```

- [ ] **Step 2: Run the tests to verify the new import fails**

Run: `node --test tests/js/space-comparison.test.mjs`
Expected: FAIL with `buildAnalyzableComparisonGroups` not exported.

- [ ] **Step 3: Implement deterministic median pairing**

Add a median helper, group valid points by product and user, sort users by median/count/name, choose the low and high users, sort each side by parsed time then observation ID, and return product-key-sorted descriptors. Do not alter the existing `buildComparisonPairs` export.

```js
function median(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function buildAnalyzableComparisonGroups(points) {
  const products = new Map();
  for (const point of points || []) {
    if (!point?.product_key || !point?.user_pseudonym
      || !Number.isFinite(point.normalized_price_cents)
      || point.normalized_price_cents < 0) continue;
    if (!products.has(point.product_key)) products.set(point.product_key, new Map());
    const users = products.get(point.product_key);
    if (!users.has(point.user_pseudonym)) users.set(point.user_pseudonym, []);
    users.get(point.user_pseudonym).push(point);
  }
  const groups = [];
  for (const [productKey, users] of products) {
    const summaries = [...users].map(([user, userPoints]) => ({
      user, points: userPoints, median: median(userPoints.map(point => point.normalized_price_cents)),
    }));
    if (summaries.length < 2) continue;
    const byLow = summaries.slice().sort((a, b) => a.median - b.median
      || b.points.length - a.points.length || a.user.localeCompare(b.user));
    const low = byLow[0];
    const high = summaries.slice().filter(item => item.user !== low.user).sort((a, b) => b.median - a.median
      || b.points.length - a.points.length || a.user.localeCompare(b.user))[0];
    const byTime = (a, b) => Date.parse(a.fetch_ts) - Date.parse(b.fetch_ts)
      || String(a.observation_id).localeCompare(String(b.observation_id));
    const pointsA = low.points.slice().sort(byTime);
    const pointsB = high.points.slice().sort(byTime);
    groups.push({
      productKey, productName: pointsA[0]?.product_name || pointsB[0]?.product_name || productKey,
      userA: low.user, userB: high.user, pointsA, pointsB, points: [...pointsA, ...pointsB],
    });
  }
  return groups.sort((a, b) => a.productKey.localeCompare(b.productKey));
}
```

- [ ] **Step 4: Run grouping and shared-rule tests**

Run: `node --test tests/js/space-comparison.test.mjs tests/js/comparison-rule.test.mjs`
Expected: all tests PASS.

- [ ] **Step 5: Commit the grouping unit**

```bash
git add api/app/static/js/space-comparison.js tests/js/space-comparison.test.mjs
git commit -m "feat: select analyzable comparison groups automatically"
```

---

### Task 2: One Minimum Tree Across Each Complete Group

**Files:**
- Modify: `api/app/static/js/space-volumes.js`
- Test: `tests/js/space-volumes.test.mjs`

**Interfaces:**
- Consumes: `buildComparisonGeometry(points, positionFor, thresholdHours = 24)` and points from Task 1.
- Produces: `{clusters, treeLines}`; `clusters` retain 24-hour ellipsoids, while `treeLines` is one global minimum tree and the old `lines` property is removed.

- [ ] **Step 1: Replace per-cluster expectations with global-tree tests**

Use four points split into two time clusters. Assert two clusters, three total tree edges, no `lines` property, and connectivity across every observation. Retain tests for invalid coordinates, single points, 2D Z=0, zero-length edges, and stable output.

```js
test('comparison geometry builds one minimum tree across all time clusters', () => {
  const points = [
    {observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'},
    {observation_id: 'b', fetch_ts: '2026-10-01T12:00:00Z'},
    {observation_id: 'c', fetch_ts: '2026-10-03T00:00:00Z'},
    {observation_id: 'd', fetch_ts: '2026-10-03T12:00:00Z'},
  ];
  const positions = {a: [0, 0, 0], b: [3, 0, 0], c: [3, 4, 0], d: [10, 4, 0]};
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.equal(geometry.clusters.length, 2);
  assert.equal(geometry.treeLines.length, 3);
  assert.equal(Object.hasOwn(geometry, 'lines'), false);
  assert.deepEqual(geometry.treeLines, [
    {from: [0, 0, 0], to: [3, 0, 0]},
    {from: [3, 0, 0], to: [3, 4, 0]},
    {from: [3, 4, 0], to: [10, 4, 0]},
  ]);
});
```

- [ ] **Step 2: Run the geometry tests to verify failure**

Run: `node --test tests/js/space-volumes.test.mjs`
Expected: FAIL because edges are still computed per cluster and `lines` still exists.

- [ ] **Step 3: Move the minimum-tree call outside the cluster mapping**

Keep cluster generation unchanged except for removing its per-cluster `treeLines`. Build a single `positioned` array from all time-sorted valid points and call the existing deterministic `minimumTree(positioned)` once.

```js
const positioned = sorted.map(item => ({point: item.point, position: positionFor(item.point)}))
  .filter(item => Array.isArray(item.position) && item.position.length >= 3
    && item.position.every(Number.isFinite));
const treeLines = minimumTree(positioned);
return {clusters, treeLines};
```

Also change each cluster return to `{key, center, radii, count}` and delete `const lines = clusters.slice(1)...` plus `clusters.flatMap(...)`.

- [ ] **Step 4: Run all JavaScript geometry tests**

Run: `node --test tests/js/space-volumes.test.mjs tests/js/space-layout.test.mjs tests/js/space-navigation.test.mjs`
Expected: all tests PASS.

- [ ] **Step 5: Commit the global-tree unit**

```bash
git add api/app/static/js/space-volumes.js tests/js/space-volumes.test.mjs
git commit -m "feat: build one minimum tree per comparison group"
```

---

### Task 3: Automatic Multi-Group Three.js Rendering

**Files:**
- Modify: `api/app/static/js/space.js`
- Modify: `api/app/static/space.html`
- Test: `tests/test_unified_theme.py`
- Test: `tests/test_observation_space_theme.py`

**Interfaces:**
- Consumes: Task 1 `buildAnalyzableComparisonGroups` and Task 2 `{clusters, treeLines}`.
- Produces: Automatic comparison rendering for all filtered groups, or only `state.selectedProduct` when set; no manual comparison-user controls remain.

- [ ] **Step 1: Write failing static integration tests**

Assert that `space.js` imports and calls `buildAnalyzableComparisonGroups`, renders `descriptor.treeLines`, does not reference `descriptor.lines` or `compareUserA`, and still calls `comparePriceGroups`. Assert that `space.html` describes automatic maximum-median-gap pairing and has no `compareUserA` / `compareUserB` controls.

```python
def test_space_automatically_renders_minimum_graphs_for_analyzable_groups():
    js = (STATIC / "js" / "space.js").read_text(encoding="utf-8")
    html = (STATIC / "space.html").read_text(encoding="utf-8")
    assert "buildAnalyzableComparisonGroups(state.filtered)" in js
    assert "descriptor.treeLines.forEach(line => addComparisonLink(line, color));" in js
    assert "descriptor.lines" not in js
    assert "comparePriceGroups" in js
    assert "compareUserA" not in js + html
    assert "compareUserB" not in js + html
    assert "中位价价差最大" in html
```

- [ ] **Step 2: Run static tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_unified_theme.py tests/test_observation_space_theme.py -q`
Expected: FAIL on manual controls and old cluster-center rendering.

- [ ] **Step 3: Integrate automatic grouping into the renderer**

Import `buildAnalyzableComparisonGroups`. In `renderComparison`, clear the group, select descriptors from `state.filtered`, optionally filter by `state.selectedProduct`, then for each descriptor calculate `comparePriceGroups`, build geometry, render ellipsoids and only `descriptor.treeLines`. Use the existing color map. Show one summary card per group with product name, low/high users, conclusion and edge count; frame all rendered cluster centers. Remove `comparisonSeries`, manual-user early returns, old price-series SVG, and `descriptor.lines` rendering.

```js
const groups = buildAnalyzableComparisonGroups(state.filtered)
  .filter(group => !state.selectedProduct || group.productKey === state.selectedProduct);
const centers = [];
const cards = [];
for (const group of groups) {
  const result = comparePriceGroups(
    {name: group.userA, prices: group.pointsA.map(point => point.normalized_price_cents / 100)},
    {name: group.userB, prices: group.pointsB.map(point => point.normalized_price_cents / 100)},
  );
  const descriptor = buildComparisonGeometry(group.points, comparisonPosition);
  const color = {red: 0xe46755, yellow: 0xeaae35, green: 0x72b5aa}[result.conclusion];
  for (const cluster of descriptor.clusters) {
    centers.push(cluster.center);
    for (const wireframe of [false, true]) {
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(1, 20, 14),
        new THREE.MeshBasicMaterial({
          color, transparent: true, opacity: wireframe ? 0.95 : 0.32,
          wireframe, side: THREE.DoubleSide, depthWrite: false,
        }),
      );
      mesh.position.set(...cluster.center);
      mesh.scale.set(...cluster.radii);
      mesh.renderOrder = wireframe ? 4 : 2;
      mesh.userData = {type: 'comparison-ellipsoid', radii: cluster.radii};
      comparisonGroup.add(mesh);
    }
  }
  descriptor.treeLines.forEach(line => addComparisonLink(line, color));
  cards.push(`<div class="stat-card"><strong>${esc(group.productName)}</strong><br>${esc(group.userA)} ↔ ${esc(group.userB)}<br><small>${descriptor.treeLines.length} 条最小树连线</small></div>`);
}
if (centers.length) frameCamera(centers);
updateComparisonVisuals();
$('comparison').innerHTML = cards.join('') || '当前筛选下暂无可分析商品组。';
```

Update `renderUserLegend` to bold users found in automatic groups, remove `compareUserA` / `compareUserB` population, and replace the HTML controls with text explaining automatic maximum-median-gap pairing.

- [ ] **Step 4: Run the complete automated suites**

Run: `node --test tests/js/*.test.mjs`
Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all JavaScript and Python tests PASS.

- [ ] **Step 5: Verify the actual browser scene**

Run the preview with `npm run dev -- --host 127.0.0.1 --port 7100`, open `/space`, load the ten-product demonstration data, and verify red/yellow/green trees, automatic user pairs, product-click isolation, comparison-layer toggle, and 2D/3D switching. Stop the development server before delivery.

- [ ] **Step 6: Commit the integrated feature**

```bash
git add api/app/static/js/space.js api/app/static/space.html tests/test_unified_theme.py tests/test_observation_space_theme.py docs/superpowers/plans/2026-10-31-analyzable-minimum-graph.md
git commit -m "feat: render automatic analyzable minimum graphs"
```
