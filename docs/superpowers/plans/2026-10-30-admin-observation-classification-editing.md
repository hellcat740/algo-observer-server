# Admin Observation Classification and Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cached category display and manual classification to the admin observation list and allow validated editing of observation business fields.

**Architecture:** A dedicated admin categories endpoint joins current-page observations to the existing cache without model calls. A full-field PUT reuses ObservationIn and clean_observation while protecting identity/sync fields and maintaining anonymous-user counts. The existing console and detail drawer host category, classification, and edit controls.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, vanilla JavaScript, unittest, Node syntax checking.

## Global Constraints

- Button text is exactly `分类`; tooltip is exactly `后台分类未分类商品`.
- No model calls while listing observations or reading their categories.
- Observation ID, created_at, origin, and synced_at are immutable through the edit API.
- Boolean editors offer 是／否／未知; currency and platform use select controls.
- Preserve `/visualization` and `/space`; remove only the admin sidebar high-dimensional label.

### Task 1: Cached Categories and Observation Update API

**Files:**
- Modify: `api/app/main.py`
- Test: `tests/test_admin_observation_management.py`

**Interfaces:**
- Produces: `POST /api/observations/categories` accepting `{"observation_ids": [str]}` and returning `{"items": {observation_id: category_or_null}}`.
- Produces: `PUT /api/observations/{observation_id}` accepting ObservationIn fields and returning ObservationOut.

- [ ] **Step 1: Write failing API tests**

Use an isolated SQLite TestClient with two observations and one ProductCategoryCache. Test administrator authentication, category_l1/l2/l3 output, null for uncached observations, duplicate IDs, and zero `_call_model` calls. Test PUT changes every editable field, rejects invalid prices/platform with 422, returns 404 for missing IDs, requires admin, and preserves observation_id/created_at/origin/synced_at. Change user_ref from USER_A to USER_B and assert counts decrement/increment in the same commit.

```python
response = client.post("/api/observations/categories", json={"observation_ids": [oid]}, headers=ADMIN)
self.assertEqual(response.json()["items"][oid]["category_l1"], "手机数码")
response = client.put("/api/observations/" + oid, json=payload, headers=ADMIN)
self.assertEqual(response.status_code, 200)
self.assertEqual(response.json()["product_name"], "修改后的商品名称")
```

- [ ] **Step 2: Verify failure**

Run: `python -m unittest tests.test_admin_observation_management -v`
Expected: 404 for categories and PUT.

- [ ] **Step 3: Implement endpoints**

Declare `ObservationIdsIn(BaseModel)` with `observation_ids: list[str] = Field(max_length=200)`. Resolve observations, call `get_cached_classifications(db, observations)`, map cache_key to each ID, and return only cache key, three category levels, confidence, review flag, and model name. Do not call `classify_products` or `schedule_classification`.

For PUT, fetch or 404, call `clean_observation(payload)`, assign cleaned values to the ORM row, and retain protected fields. Reuse a helper for user count changes:

```python
def adjust_user_ref(db, old_ref, new_ref, now):
    if old_ref == new_ref:
        return
    if old_ref:
        old = db.query(User).filter(User.anonymous_id == old_ref).first()
        if old:
            old.observation_count = max(0, old.observation_count - 1)
    if new_ref:
        new = db.query(User).filter(User.anonymous_id == new_ref).first()
        if new is None:
            new = User(anonymous_id=new_ref, first_seen_at=now, last_seen_at=now, observation_count=0)
            db.add(new)
        new.last_seen_at = now
        new.observation_count += 1
```

Commit once and return the row. Preserve current cleaning behavior and errors.

- [ ] **Step 4: Verify API and regressions**

Run: `python -m unittest tests.test_admin_observation_management tests.test_observation_details tests.test_space_api -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/app/main.py tests/test_admin_observation_management.py
git commit -m "feat: add admin category lookup and observation editing"
```

### Task 2: Observation Table Categories and Manual Classification

**Files:**
- Modify: `api/app/static/index.html`
- Test: `tests/test_admin_observation_management_page.py`

**Interfaces:**
- Consumes: category POST and existing `/api/space/classification-check` plus `/classification-status`.
- Produces: `obsClassify()` and `obsLoadCategories(items)` browser functions.

- [ ] **Step 1: Write failing static/behavior tests**

Assert no `href="/visualization"` in the sidebar, table has 类别, button text/title are exact, and edit precedes delete in row markup. Assert classification function POSTs and disables the button while status is running, then calls obsLoad on success. Add a lightweight Node VM DOM/fetch harness for `obsLoadCategories` to verify ID mapping and 未分类 fallback.

- [ ] **Step 2: Verify failure**

Run: `python -m unittest tests.test_admin_observation_management_page -v`
Expected: missing controls and functions.

- [ ] **Step 3: Implement table and classification UI**

Add the category header/cell and load category data after observations render. Render `category_l1 + ' / ' + category_l2`, escape all values, and show 未分类 for null. Add:

```html
<button class="btn ghost" id="obs-classifyBtn" title="后台分类未分类商品" onclick="obsClassify()">分类</button>
<span id="obs-classifyStatus" class="muted"></span>
```

`obsClassify` POSTs with X-API-Key, disables during running, polls classification-status without overlapping timers, handles not_configured/error, and reloads on success. No model request occurs in obsLoad itself.

- [ ] **Step 4: Verify tests and JavaScript syntax**

Run: `python -m unittest tests.test_admin_observation_management_page -v`
Run: extract inline script and `node --check` on it.
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/app/static/index.html tests/test_admin_observation_management_page.py
git commit -m "feat: show observation categories and manual classification"
```

### Task 3: Full-Field Edit Drawer and Final Verification

**Files:**
- Modify: `api/app/static/index.html`
- Modify: `README.md` admin feature summary if present
- Test: `tests/test_admin_observation_management_page.py`

**Interfaces:**
- Produces: `obsEdit(id)`, `obsEditSubmit()`, `obsEditClose()` using PUT from Task 1.

- [ ] **Step 1: Write failing editor contract tests**

Assert each ObservationOut business field has a corresponding edit control, protected fields are absent from the payload, boolean/currency/platform controls are `select`, and edit precedes delete. Node VM tests verify number/empty/null conversion, datetime conversion, preservation on 422, and obsLoad after 200.

- [ ] **Step 2: Verify failure**

Run: `python -m unittest tests.test_admin_observation_management_page -v`
Expected: editor controls/functions missing.

- [ ] **Step 3: Implement editor**

Add a dedicated edit drawer with two-column form. Generate controls from a field descriptor array containing key, label, type, and options. Use selects for is_login/is_new_user/peak_hour (empty/true/false), CNY/USD, and ALLOWED_PLATFORMS including amazon. Use number inputs for integer/float fields, datetime-local for fetch_ts, and text inputs for remaining fields. Show read-only observation ID and created_at. `obsEditSubmit` converts prices in cents as numbers, empty optional fields to null, boolean strings to booleans, local datetime to ISO, and user_ref to anonymous_id. PUT with admin key; show parsed 422 detail without closing or clearing; refresh on success.

- [ ] **Step 4: Run all verification**

Run: `python -m unittest discover -s tests -q`
Expected: all pass.
Run: `node --check` on extracted console script, `git diff --check`, and scan changed files for real `sk-` keys.
Expected: no errors or secrets.

- [ ] **Step 5: Commit**

```bash
git add api/app/static/index.html tests/test_admin_observation_management_page.py README.md
git commit -m "feat: edit observations from admin console"
```
