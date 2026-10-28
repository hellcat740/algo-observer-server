# Currency-Normalized Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve Amazon prices as USD, cache the server's daily USD/CNY rate, and compare all observations in CNY.

**Architecture:** Add an isolated exchange-rate service, database cache and authenticated API; invoke it daily through Vercel Cron or the existing resident-service scheduler. The comparison page requests one rate snapshot per analysis and normalizes integer cents before existing statistics. The extension retains explicit platform currency detection and advances to 1.1.0.

**Tech Stack:** FastAPI, SQLAlchemy, Python standard-library HTTP, vanilla JavaScript, Chrome Manifest V3, unittest/pytest.

## Global Constraints

- Preserve original `currency` and integer-cent values in observation storage.
- Never analyze mixed currencies without a valid server-provided rate; never hardcode a fallback rate.
- USD converts with `round(usd_cents * rate)`; CNY remains unchanged.
- Extension manifest and packaged zip must both report `1.1.0`.
- Every task has regression tests and a Git commit; run the complete suite before delivery.

---

### Task 1: Persistent exchange-rate service and API

**Files:**
- Create: `api/app/exchange_rates.py`
- Modify: `api/app/models.py`, `api/app/main.py`, `vercel.json`, `api/app/sync_api.py`
- Test: `tests/test_exchange_rates.py`

**Interfaces:**
- Produces: `latest_rate(db, base="USD", quote="CNY", fetcher=fetch_frankfurter) -> dict`, `refresh_rate(db) -> dict`, `start_rate_refresh() -> bool`.
- Response fields: `base`, `quote`, `rate`, `rate_date`, `source`, `fetched_at`, `stale`.

- [ ] **Step 1: Write failing unit/API tests**

Use an isolated SQLite database and mocked `urllib.request.urlopen`. Assert valid upstream data persists; a second same-day request does not fetch; upstream failure returns cached data with `stale=true`; no cache gives HTTP 503; malformed/non-positive rates fail; CNY/CNY gives 1; `/api/exchange-rates/latest` requires and accepts `X-User-Id`.

- [ ] **Step 2: Run tests and verify missing behavior**

Run: `python -m pytest tests/test_exchange_rates.py -q`
Expected: FAIL because the model, module and endpoint do not exist.

- [ ] **Step 3: Implement the cache and daily refresh**

Define `ExchangeRate` with a composite unique constraint on `(base, quote)`. Fetch Frankfurter with an 8-second timeout, validate its `date` and positive finite `rates.CNY`, then upsert and commit. `latest_rate` uses today's successful `fetched_at`, otherwise refreshes; failures fall back to the newest row or raise a dedicated `ExchangeRateUnavailable`. Register a public route through `Depends(require_user)` and map unavailability to 503. Add a Vercel cron for `/api/exchange-rates/refresh` and start a daemon daily refresh only for non-Vercel deployments; protect the refresh endpoint with the existing admin credential while leaving latest user-authenticated.

- [ ] **Step 4: Verify tests and commit**

Run: `python -m pytest tests/test_exchange_rates.py -q`
Expected: PASS.

```bash
git add api/app/exchange_rates.py api/app/models.py api/app/main.py api/app/sync_api.py vercel.json tests/test_exchange_rates.py
git commit -m "feat: cache daily USD CNY exchange rates"
```

### Task 2: Currency-normalized browser comparison

**Files:**
- Modify: `api/app/static/lab.html`
- Test: `tests/test_currency_comparison.py`

**Interfaces:**
- Consumes: Task 1 latest-rate response and existing observation `currency` fields.
- Produces: `normalizePrices(items, rates)` returning copied observations with comparison amounts in CNY cents; display metadata records the selected rate.

- [ ] **Step 1: Write failing structure and executable JavaScript tests**

Assert USD 1000 at rate 7.2 becomes CNY 7200, CNY 1000 remains 1000, missing/unknown currencies are rejected, original input is not mutated, analysis requests the rate only when needed, and failure prevents analysis. Assert the result explanation contains rate, actual date and stale-cache wording.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_currency_comparison.py -q`
Expected: FAIL because normalization and rate retrieval are absent.

- [ ] **Step 3: Implement minimal page changes**

Before `analyze`, derive required currencies and request `/api/exchange-rates/latest?base=USD&quote=CNY` with the existing identity header. In `priceOf`, retain original values but return normalized CNY cents using one supplied rate. Reject unsupported/non-positive currencies and rates. On request/conversion failure render the error and return without `analyze`. Add rate/date/source and stale status to the methodology notice, and keep CNY-only operation free of an exchange request.

- [ ] **Step 4: Verify tests and commit**

Run: `python -m pytest tests/test_currency_comparison.py -q` and extract the inline script into Node `vm.Script`.
Expected: tests PASS and no JavaScript syntax error.

```bash
git add api/app/static/lab.html tests/test_currency_comparison.py
git commit -m "feat: normalize comparison prices to CNY"
```

### Task 3: Extension currency contract and release

**Files:**
- Modify: packaged extension `content/index.js`, `manifest.json`, `api/app/static/plugin.zip`
- Test: `tests/test_platform_extraction.py`, `tests/test_amazon_ingestion.py`

**Interfaces:**
- Produces: Amazon actual-pay/display/discount currency `USD`; domestic platforms `CNY`; manifest version `1.1.0`.

- [ ] **Step 1: Strengthen failing currency/version tests**

Execute the real content script against Amazon and domestic fixtures; assert `data.price.currency`, including Amazon actual-pay, is correct. Read the manifest inside the zip and assert `version == "1.1.0"` and Amazon selectors remain enabled.

- [ ] **Step 2: Run tests and verify old package failure**

Run: `python -m pytest tests/test_platform_extraction.py tests/test_amazon_ingestion.py -q`
Expected: version assertion FAILS against 1.0.0.

- [ ] **Step 3: Implement detection, version and package**

Keep platform-derived currency as the authoritative default and only normalize recognized page currency symbols/codes; do not infer a different currency from locale. Set manifest `version` to `1.1.0`, reproduce the original zip layout and verify archived and working manifests match.

- [ ] **Step 4: Verify release tests and commit**

Run: `python -m pytest tests/test_platform_extraction.py tests/test_amazon_ingestion.py -q`
Expected: PASS.

```bash
git add api/app/static/plugin.zip tests/test_platform_extraction.py tests/test_amazon_ingestion.py
git commit -m "feat: release currency-aware extension 1.1.0"
```

### Task 4: Full verification and delivery

**Files:**
- Modify only if a demonstrated regression requires a scoped fix.

- [ ] **Step 1: Run the complete suite**

Run: `python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 2: Check artifacts and repository**

Run Node `vm.Script` checks for modified HTML, inspect `git diff --check`, confirm clean status after commits and verify the remote main SHA after pushing. Do not claim production verification without checking deployment.
