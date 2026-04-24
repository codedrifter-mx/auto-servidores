# Auto-Servidores: Full Code Critique & Remediation Plan

## Project Overview

**auto-servidores** is a Python tool that batch-queries a Mexican government API (DeclaraNet) to check whether public servants have up-to-date annual declarations. It reads names/RFCs from Excel seed files, hits the API, and produces Excel output files (found/not-found).

The repo spans **6 years** (2020-2026) with two distinct eras:
- **Human-era** (2020-2025): 21 commits by `alfredo`/`alfredo-flores`/`Alfredo Flores`
- **Agentic-era** (April 21-22, 2026): 7 commits by `codedrifter` (AI-assisted)

---

## 🟢 What Was Done Really Well

### Human-Era Highlights

| Aspect | Details |
|--------|---------|
| **Evolutionary architecture** | The project evolved naturally: Selenium → API-based → multithreaded → Excel I/O. Each pivot was a smart simplification. |
| **API migration** (`ae256f4`) | Removing Selenium and moving to direct API calls was an excellent decision — simpler, faster, more reliable. |
| **Domain knowledge** | The filtering logic (year, `tipoDeclaracion`, `institucionReceptora`) is correct and cleanly encoded. |

### Agentic-Era Highlights

| Aspect | Details |
|--------|---------|
| **Clean modular decomposition** (`810f66a`) | Splitting a monolith `main.py` into `cache.py`, `checkpoint.py`, `compactor.py`, `index.py`, `orchestrator.py`, `session.py`, `worker.py` — *excellent* SRP decomposition. Each module has a single clear responsibility. |
| **SQLite caching with WAL** (`cache.py`) | Using SQLite with WAL mode, in-memory write-behind buffer, configurable TTL, and thread-safe access via `RLock` — this is **production-grade caching**. Smart use of `sha256` keys and batched flush. |
| **Rate limiting** (`session.py`) | The `RateLimitGate` with semaphore, min-interval enforcement, exponential cooldown on 429s, and success-reset — very well thought out for hitting a government API that rate-limits. |
| **Exponential backoff with jitter** (`worker.py`) | `_post_with_retry` implements proper exponential backoff with random jitter, handling 429/502/503/504 — textbook retry logic. |
| **Atomic checkpoint saves** (`checkpoint.py`) | Writing to `.tmp` then `os.replace()` — prevents data corruption on crash. |
| **GUI** (`gui.py`) | The customtkinter GUI is impressive: system info panel, Excel format hints, file management with drag, sliders for configuration, tabbed layout, live logging, progress bar. This is far beyond MVP. |
| **Comprehensive tests** (`3e2c506`) | 6 test files covering all core modules with 30+ test cases. Proper use of fixtures, temp dirs, mocks, and async testing. Good edge cases (TTL expiry, slash replacement, out-of-range batch). |
| **CI/CD pipeline** (`6d8198f` + `3e2c506`) | GitHub Actions with test gate → build gate → release asset. Tests must pass before binary is built. Nice structure. |
| **Config-driven design** (`config.yaml`) | Everything configurable: API endpoints, rate limits, batch sizes, output paths. No magic numbers in code. |

---

## 🔴 What Was Done Badly

### Critical Issues

#### 1. 🚨 **`__pycache__/`, `.cache/api_cache.db`, `.checkpoint/state.json` are committed to git** (`810f66a`)

The 2026 refactor commit includes **8 `.pyc` files**, a **5.7 MB SQLite database**, and a **checkpoint state file** in the repository.

```
.cache/api_cache.db                      | Bin 0 -> 5787648 bytes  ← 5.7 MB!
.checkpoint/state.json                   |   1 +
__pycache__/cache.cpython-313.pyc        | Bin 0 -> 5424 bytes
__pycache__/checkpoint.cpython-313.pyc   | Bin 0 -> 3431 bytes
...
```

> [!CAUTION]
> The SQLite cache may contain real API responses with personal data (names, RFCs, declaration data). This is a **data privacy risk** in a public repo.

#### 2. 🚨 **Real seed data is committed** — `seed/1Noidentificados.xlsx` and `seed/DURANGO.xlsx` are tracked

These files contain real names and RFCs of actual people. In a public GitHub repo, this is a **serious privacy violation**.

#### 3. 🚨 **Entire `venv/` was committed in the initial commit** (`de0fca1`)

The first commit added **763 files** including the entire `venv/` directory with all `site-packages`. This is ~231,000 lines of third-party code in git history.

#### 4. 🚨 **`.idea/` (IntelliJ) directory is tracked**

JetBrains IDE config files are committed and tracked. These are developer-specific and should never be in the repo.

#### 5. 🚨 **`.gitignore` is corrupted** — Contains null bytes (binary corruption)

```
__pycache__/    ← This line is encoded in UTF-16 with null bytes!
```

Line 12 of `.gitignore` contains `_\x00_\x00p\x00y\x00c\x00a\x00c\x00h\x00e\x00_\x00_\x00/\x00\r\x00` — this is a UTF-16LE encoded string mixed into a UTF-8 file. **Git ignores this corrupted line entirely**, which is why `__pycache__/` is tracked.

---

### Architectural / Code Issues

#### 6. ⚠️ **`Checkpoint` class is dead code** — Fully written, tested, but **never used by anything**

`checkpoint.py` is imported *only* by `tests/test_checkpoint.py`. Neither `orchestrator.py` nor `main.py` nor `gui.py` import or use it. The `checkpoint_interval: 25` in `config.yaml` is never read.

#### 7. ⚠️ **`_enforce_min_interval` holds the async lock while sleeping** (`session.py:52-58`)

```python
async def _enforce_min_interval(self):
    async with self._lock:          # ← Lock acquired
        now = time.monotonic()
        wait = self._min_interval - (now - self._last_request)
        if wait > 0:
            await asyncio.sleep(wait)   # ← Sleeping while holding lock!
        self._last_request = time.monotonic()
```

This serializes ALL concurrent tasks during the sleep, defeating the purpose of concurrency. All other tasks block on the lock while one sleeps.

#### 8. ⚠️ **`SeedIndex.load_batch()` re-reads the entire Excel file for every batch** (`index.py:30`)

```python
def load_batch(self, filepath, start=0, size=50):
    df = pd.read_excel(filepath)  # ← Full file read every batch!
    batch = df.iloc[start:start + size]
```

For a file with 1000 rows and batch_size=25, this reads the file **40 times**.

#### 9. ⚠️ **`test_cache_hit_search` test passes for the wrong reason** (`test_worker.py:113-124`)

```python
async def test_cache_hit_search(self):
    cache.get.return_value = {"estatus": True, "datos": [{"idUsrDecnet": "99"}]}
    session = _make_mock_session([(200, {"datos": []})])
    result = await process_person(...)
    assert session.post.call_count == 0  # ← This passes...
```

But `cache.get` returns the same value for **both** the search call *and* the history call. The test doesn't actually verify cache-miss-on-history. It looks correct but masks a subtle issue: the mock cache returns the same data for any `get()` call.

#### 10. ⚠️ **`output.dir` is `.` (current directory)** — Output files are written to the project root

The output Excel files (`*_ENCONTRADOS.xlsx`, `*_NO_ENCONTRADOS.xlsx`) land in the project root. Several of these are already tracked by git (because `.gitignore` says `*.xlsx` but there are already-tracked ones). This pollutes the project directory.

#### 11. ⚠️ **Errors are silently swallowed in `worker.py:93-94`**

```python
except Exception:
    return {"Name": name, "RFC": rfc, "Status": "Error"}
```

No logging, no traceback capture. When something fails, you have zero diagnostic information.

#### 12. ⚠️ **GUI config slider values don't match `config.yaml` ranges**

In `gui.py:189`: `self.slider_worker.set(100)` — the slider's `to` is 20, but the initial value is set to 100. Similarly line 179: `self.slider_batch.set(50)` while the config says `batch_size: 25`. This is cosmetic (overridden later by `_load_config_to_sliders`) but shows sloppy initialization.

#### 13. ⚠️ **No `__init__.py` in `tests/` directory**

The test runner relies on `pythonpath = .` in `pytest.ini` instead. This works for pytest but may break other tooling.

#### 14. ⚠️ **README is completely stale**

README says:
- "Python 3.10" — project uses Python 3.13
- "Última versión de Chrome" — Selenium was removed 2 years ago
- "Windows (Linux pendiente)" — there's now a GUI and CI, but no mention
- No mention of `config.yaml`, the GUI, headless mode, or any 2026 features

#### 15. ⚠️ **`auto_servidores.spec` is tracked** despite `.gitignore` having `*.spec`

The `.gitignore` says `*.spec` but the file was committed before the ignore rule was added. Git continues to track it.

---

### Minor Issues

| # | Issue | File |
|---|-------|------|
| 16 | `retry_delay` variable name is misleading — it's used for `max_retries` value | `gui.py:290` |
| 17 | `_on_rl_cooldown_change` formats to 1 decimal, `_on_rl_cooldown_max_change` formats to 0 decimals — inconsistent | `gui.py:335-338` |
| 18 | `config["api"]["default_coll_name"]` parsed as `int()` in save — would crash if the API ever returns a string ID | `gui.py:419` |
| 19 | `search_params` dict is built but never used in the URL — URL is manually concatenated | `worker.py:48-49` |
| 20 | No `tests/__init__.py` file | `tests/` |
| 21 | `pytest` and `pytest-asyncio` are in `requirements.txt` — should be in a separate `dev` or `test` requirements | `requirements.txt` |

---

## Proposed Changes

### Phase 1: Git Hygiene (Critical Priority)

#### [MODIFY] [.gitignore](file:///c:/Users/Kazuk/auto-servidores/.gitignore)

Rewrite the entire `.gitignore` from scratch (it has binary corruption). Properly exclude:
- `__pycache__/`, `*.pyc`
- `.cache/`, `.checkpoint/`
- `*.xlsx` (output files)
- `seed/*.xlsx` (input data — should not be in repo)
- `.idea/`, `.opencode/`, `.vscode/`
- `venv/`, `env/`
- `dist/`, `build/`, `*.spec`
- `*.db`

#### Remove tracked files that should be ignored

Run `git rm --cached` to untrack:
- All `__pycache__/` files
- `.cache/api_cache.db`
- `.checkpoint/state.json`
- `seed/*.xlsx`
- `.idea/` directory
- `auto_servidores.spec`

> [!WARNING]
> This will NOT remove these files from git history. The 5.7 MB cache DB and the real personal data in seed files will remain in the history. Consider running `git filter-branch` or `BFG Repo Cleaner` to purge sensitive data — but this rewrites history and requires force-push. **Do you want to do a full history rewrite?**

---

### Phase 2: Dead Code Removal

#### [MODIFY] [config.yaml](file:///c:/Users/Kazuk/auto-servidores/config.yaml)

Remove `checkpoint_interval: 25` (unused config key).

#### Decision Point: `checkpoint.py`

> [!IMPORTANT]
> The `Checkpoint` class is well-written and well-tested, but **never used**. It was clearly meant to be integrated into `orchestrator.py` to allow resuming interrupted processing. Two options:
> 1. **Delete it** — remove dead code, remove the test file too
> 2. **Integrate it** — wire it into the orchestrator so interrupted runs can resume
>
> **Recommendation:** Integrate it. Resumability is valuable for this tool (long batch runs against flaky government APIs). I'll include integration in the plan.

---

### Phase 3: Bug Fixes

#### [MODIFY] [session.py](file:///c:/Users/Kazuk/auto-servidores/session.py)

Fix `_enforce_min_interval` to not hold the lock while sleeping:

```python
async def _enforce_min_interval(self):
    async with self._lock:
        now = time.monotonic()
        wait = self._min_interval - (now - self._last_request)
        self._last_request = now + max(wait, 0)  # Reserve the slot
    if wait > 0:
        await asyncio.sleep(wait)  # Sleep OUTSIDE the lock
```

#### [MODIFY] [index.py](file:///c:/Users/Kazuk/auto-servidores/index.py)

Cache the DataFrame after first read, avoid re-reading the entire Excel for each batch:

```python
def __init__(self, seed_dir="seed"):
    self.seed_dir = seed_dir
    self.index = []
    self._df_cache = {}  # filepath -> DataFrame
    self._build_index()

def load_batch(self, filepath, start=0, size=50):
    if filepath not in self._df_cache:
        self._df_cache[filepath] = pd.read_excel(filepath)
    df = self._df_cache[filepath]
    ...
```

#### [MODIFY] [worker.py](file:///c:/Users/Kazuk/auto-servidores/worker.py)

- Add `logging.exception()` to the catch-all in `process_person()` (line 93-94)
- Use `params` dict for URL construction instead of manual string concatenation (avoid encoding bugs)

#### [MODIFY] [gui.py](file:///c:/Users/Kazuk/auto-servidores/gui.py)

- Fix slider initial values (lines 179, 189) to match config defaults instead of arbitrary numbers
- Fix `retry_delay` variable name confusion (line 290)
- Consistent decimal formatting across slider callbacks

---

### Phase 4: Checkpoint Integration

#### [MODIFY] [orchestrator.py](file:///c:/Users/Kazuk/auto-servidores/orchestrator.py)

Integrate `Checkpoint` to enable resume after interruption:
- Import and instantiate `Checkpoint`
- On each processed person, call `checkpoint.mark_processed()`
- Before processing, skip already-processed RFCs via `checkpoint.is_processed()`
- Save checkpoint periodically (every batch) and on completion
- Clear checkpoint when a file is fully processed

---

### Phase 5: Documentation & Housekeeping

#### [MODIFY] [README.md](file:///c:/Users/Kazuk/auto-servidores/README.md)

Full rewrite:
- Update Python version to 3.13
- Remove Chrome/Selenium references
- Document GUI mode and headless mode (`--no-gui`)
- Document `config.yaml` settings
- Document the seed folder format
- Add screenshot of the GUI (optional)

#### [MODIFY] [requirements.txt](file:///c:/Users/Kazuk/auto-servidores/requirements.txt)

- Pin versions (at minimum major versions)
- Move `pytest` + `pytest-asyncio` to a separate `requirements-dev.txt`

#### [MODIFY] [config.yaml](file:///c:/Users/Kazuk/auto-servidores/config.yaml)

Change `output.dir` from `.` to `output/` and add `output/` to `.gitignore`.

---

## Open Questions

> [!IMPORTANT]
> 1. **History rewrite**: Do you want me to use `git filter-branch` / BFG to purge the cached API data (5.7 MB with potential PII) and seed Excel files from git history? This requires force-push.
> 2. **Checkpoint integration**: Should I integrate the Checkpoint class into the orchestrator (for resumable runs), or just delete the dead code?
> 3. **`output.dir`**: Is changing output from `.` (project root) to `output/` acceptable? Your existing output xlsx files would remain in the root.

---

## Verification Plan

### Automated Tests
```bash
pytest tests/ -v
```
All existing tests must continue to pass. New tests for:
- `SeedIndex` caching behavior
- `_enforce_min_interval` lock-free sleep
- Checkpoint integration in orchestrator (if integrated)

### Manual Verification
- Verify `.gitignore` properly excludes all generated files
- Verify `git status` shows no tracked files that should be ignored
- Run the GUI and confirm slider defaults match `config.yaml`
- Run headless mode with a small seed file to verify end-to-end
