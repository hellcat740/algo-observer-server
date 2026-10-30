# Idle Classification Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a once-daily 01:17 Asia/Shanghai classification check for at most 100 uncached products and support server-selected DeepSeek or Qwen providers.

**Architecture:** A focused configuration module resolves provider credentials and OpenAI-compatible endpoints. The existing classification flow and cache remain the single classification path. A focused scheduler queries uncached products and invokes the existing worker; an administrator-only POST endpoint starts the same check on demand.

**Tech Stack:** Python 3, FastAPI BackgroundTasks, SQLAlchemy, threading, zoneinfo, unittest, Docker Compose.

## Global Constraints

- Daily scheduled check: exactly 01:17 Asia/Shanghai; at most 100 uncached products per run.
- Default models are exactly `v4.1flash` and `qwen3.8flash`.
- Never write real API keys to source, documentation, responses, or logs.
- Model input retains only product name, seller, URL, and platform; cached products cause zero model calls.
- No new dependencies; retain existing API behavior and run all tests before delivery.
- Browser extension remains version 1.1.0.

### Task 1: Provider Configuration and Shared Model Requests

**Files:**
- Create: `api/app/classification_config.py`
- Modify: `api/app/product_categories.py`
- Test: `tests/test_classification_config.py`, `tests/test_product_categories.py`

**Interfaces:**
- Produces: `ProviderSettings` dataclass (`name`, `api_key`, `base_url`, `model`), `provider_settings() -> ProviderSettings`, `provider_is_configured() -> bool`.
- Produces: `_call_model(product) -> dict`; `classification_request(product, model=None) -> dict` remains compatible with existing callers.

- [ ] **Step 1: Write failing provider tests**

```python
with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen", "QWEN_API_KEY": "test-qwen"}, clear=True):
    settings = provider_settings()
self.assertEqual(settings.name, "qwen")
self.assertEqual(settings.api_key, "test-qwen")
self.assertEqual(settings.model, "qwen3.8flash")
self.assertEqual(settings.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")
with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen", "DASHSCOPE_API_KEY": "fallback"}, clear=True):
    self.assertEqual(provider_settings().api_key, "fallback")
with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "invalid"}, clear=True):
    with self.assertRaises(ClassificationError):
        provider_settings()
with patch.dict(os.environ, {}, clear=True):
    self.assertEqual(provider_settings().model, "v4.1flash")
```

Also test Qwen HTTP headers and URL by patching `app.product_categories.urlopen`; assert `Bearer test-qwen`, `/chat/completions`, and request model `qwen3.8flash`. Verify `_normalize(..., model_name=settings.model)` persists the selected model.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_classification_config tests.test_product_categories -v`
Expected: import failure for `classification_config`, then missing Qwen support.

- [ ] **Step 3: Implement provider resolution and shared HTTP call**

```python
@dataclass(frozen=True)
class ProviderSettings:
    name: str
    api_key: str
    base_url: str
    model: str

def provider_settings():
    name = os.environ.get("CLASSIFICATION_PROVIDER", "deepseek").strip().lower()
    if name == "deepseek":
        return ProviderSettings(name, os.environ.get("DEEPSEEK_API_KEY", "").strip(),
            os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            os.environ.get("DEEPSEEK_MODEL", "v4.1flash"))
    if name == "qwen":
        return ProviderSettings(name,
            (os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or "").strip(),
            os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            os.environ.get("QWEN_MODEL", "qwen3.8flash"))
    raise ClassificationError("CLASSIFICATION_PROVIDER 仅支持 deepseek 或 qwen")
```

Move `ClassificationError` to the config module and import it into `product_categories` for backward compatibility. Replace `_call_deepseek` with `_call_model`, retaining `_call_deepseek = _call_model` as a compatibility alias. Include the configured model in normalized results, use `provider_is_configured()` for the no-key fast path, and wrap transport errors without exposing response bodies or credentials.

- [ ] **Step 4: Run focused and existing classification tests**

Run: `python -m unittest tests.test_classification_config tests.test_product_categories tests.test_space_api -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/app/classification_config.py api/app/product_categories.py tests/test_classification_config.py tests/test_product_categories.py tests/test_space_api.py
git commit -m "feat: support DeepSeek and Qwen classification"
```

### Task 2: Daily Idle Scheduler and Bounded Product Selection

**Files:**
- Create: `api/app/classification_scheduler.py`
- Modify: `api/app/main.py`
- Test: `tests/test_classification_scheduler.py`

**Interfaces:**
- Consumes: `provider_is_configured()` and existing `run_classification_worker(products, session_factory=None, classifier=None)`.
- Produces: `next_run(now: datetime) -> datetime`, `find_uncached_products(db, limit=100) -> list`, `run_idle_check(session_factory=None, worker=run_classification_worker) -> dict`, `start_classification_scheduler() -> bool`.

- [ ] **Step 1: Write failing time, selection, and lifecycle tests**

```python
before = datetime(2026, 10, 29, 17, 16, tzinfo=timezone.utc)
after = datetime(2026, 10, 29, 17, 17, tzinfo=timezone.utc)
self.assertEqual(next_run(before), after)
self.assertEqual(next_run(after), after + timedelta(days=1))
```

Create 101 distinct products and assert exactly 100 detached products are returned, a cached product is excluded, and only the four product fields plus product ID needed by the existing cache are present. Test no-key returns `not_configured` without worker calls, no-products returns `idle`, running status does not start another worker, and a worker exception is caught by the daemon loop rather than killing it. Test Vercel returns `False`, non-Vercel first start returns `True`, and repeated start returns `False`.

- [ ] **Step 2: Run scheduler tests to verify failure**

Run: `python -m unittest tests.test_classification_scheduler -v`
Expected: import failure for `classification_scheduler`.

- [ ] **Step 3: Implement bounded selection and scheduler**

```python
SHANGHAI = ZoneInfo("Asia/Shanghai")
RUN_HOUR, RUN_MINUTE, DAILY_LIMIT = 1, 17, 100

def next_run(now):
    local = now.astimezone(SHANGHAI)
    candidate = local.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate

def find_uncached_products(db, limit=DAILY_LIMIT):
    observations = db.query(Observation).order_by(Observation.created_at, Observation.observation_id).all()
    products = deduplicate_products(observations)
    cached = get_cached_classifications(db, products)
    return [_detached_product(p) for p in products if cache_key(p) not in cached][:limit]
```

Move `_detached_product` to `product_categories.py` and import it in both modules. `run_idle_check` opens and closes its own session, checks current worker status and selected provider configuration, and invokes the worker only when work exists. `start_classification_scheduler` uses an idempotent started flag and a daemon thread that waits on a private `threading.Event` until `next_run`, invokes the check in `try/except Exception`, logs a generic error, and always calculates the following run. Import and call `start_classification_scheduler()` beside `start_rate_refresh()` in `init_db`.

- [ ] **Step 4: Run scheduler and API regression tests**

Run: `python -m unittest tests.test_classification_scheduler tests.test_space_api tests.test_main -v`
Expected: all pass; if `tests.test_main` does not exist, omit it and run the full suite in Task 4.

- [ ] **Step 5: Commit**

```bash
git add api/app/classification_scheduler.py api/app/product_categories.py api/app/space_api.py api/app/main.py tests/test_classification_scheduler.py
git commit -m "feat: schedule daily idle product classification"
```

### Task 3: Administrator Manual Check

**Files:**
- Modify: `api/app/space_api.py`
- Test: `tests/test_space_api.py`

**Interfaces:**
- Produces: `POST /api/space/classification-check -> dict` using the existing router-level administrator authentication.
- Consumes: `run_idle_check`, existing classification status functions, and FastAPI `BackgroundTasks`.

- [ ] **Step 1: Write failing endpoint tests**

```python
response = self.client.post("/api/space/classification-check")
self.assertEqual(response.status_code, 401)
with patch("app.space_api.run_idle_check") as check:
    response = self.client.post("/api/space/classification-check", headers={"X-API-Key": ADMIN_KEY})
self.assertEqual(response.status_code, 200)
self.assertEqual(response.json()["status"], "success")
check.assert_called_once()
```

Add tests for configured and unconfigured providers. BackgroundTasks executes before TestClient returns; mock the worker/check rather than making network calls. Assert the endpoint uses a fresh scheduler-owned session and never waits for a model in the request thread.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_space_api -v`
Expected: POST returns 404.

- [ ] **Step 3: Implement the endpoint**

```python
@router.post("/classification-check")
def classification_check(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_idle_check)
    return get_classification_status()
```

`run_idle_check` owns configuration, empty-work, and concurrent-run decisions. The endpoint returns the immediate state; the existing status endpoint reports completion.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_space_api tests.test_classification_scheduler -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/app/space_api.py tests/test_space_api.py
git commit -m "feat: add manual idle classification check"
```

### Task 4: Alibaba Cloud Configuration and Full Verification

**Files:**
- Modify: `.env.example`, `DEPLOY.md`, `README.md`
- Test: `tests/test_classification_scheduler.py`, `tests/test_documentation.py` if an existing documentation test pattern is available; otherwise use exact Grep and diff verification.

**Interfaces:**
- Documents `/opt/algo-observer-server/.env` and `api/app/classification_config.py`.
- Documents DeepSeek/Qwen settings, daily 01:17 check, 100-product limit, and manual POST endpoint.

- [ ] **Step 1: Add failing deployment contract checks**

Assert `.env.example` contains `CLASSIFICATION_PROVIDER=deepseek`, `QWEN_API_KEY=replace-with-qwen-secret`, the exact Qwen URL/model, and no value beginning with `sk-`. Assert deployment documentation contains `/opt/algo-observer-server/.env`, `docker compose up -d --force-recreate web`, `POST /api/space/classification-check`, `01:17`, and `100`.

- [ ] **Step 2: Run checks to verify failure**

Run: `python -m unittest tests.test_documentation -v` if created; otherwise use Grep and confirm required entries are absent before editing.

- [ ] **Step 3: Add exact configuration and operations documentation**

```text
CLASSIFICATION_PROVIDER=deepseek
DEEPSEEK_API_KEY=replace-with-deepseek-secret
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=v4.1flash
# Qwen alternative: set CLASSIFICATION_PROVIDER=qwen
QWEN_API_KEY=replace-with-qwen-secret
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.8flash
```

Document that only the selected provider's key is required, `.env` changes require `docker compose up -d --force-recreate web`, code updates require `docker compose up -d --build`, and the manual check is a POST request with `X-API-Key`.

- [ ] **Step 4: Run full verification**

Run: `python -m unittest discover -s tests -q`
Expected: all existing and new tests pass.

Run: `git diff --check && git status --short`
Expected: no whitespace errors and only intended changes. Scan modified files for `sk-[A-Za-z0-9]`; expect no matches.

- [ ] **Step 5: Commit**

```bash
git add .env.example DEPLOY.md README.md tests
git commit -m "docs: configure Alibaba Cloud classification providers"
```
