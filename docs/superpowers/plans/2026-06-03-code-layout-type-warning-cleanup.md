# Backend Code Layout Type Warning Cleanup Implementation Plan

> **Scope update:** On 2026-06-03 the user narrowed the request to backend only. `frontend/` is explicitly out of scope for this implementation.

**Goal:** Normalize backend source and test file layout, update all backend imports, make backend Pyright clean, and make backend test runs emit zero warnings.

**Architecture:** Treat this as a mechanical backend migration guarded by generated inventories and verification gates. First define enforceable naming rules, then rename files/directories with collision checks, then repair imports and type surfaces, then turn zero-warning checks into reproducible commands.

**Tech Stack:** Python 3.13 in `conda run -n trader`, FastAPI backend, Pyright, pytest.

## Scope And Rules

### In Scope

- Backend source: `backend/app`, `backend/tradingagents`, `backend/cli`.
- Backend tests: `backend/tests`, with migrated historical script-style tests stored in `backend/testsupport` and exposed as integration import-smoke wrappers.
- Backend imports, lazy imports, package exports, fixture references, path references, and string module references inside the in-scope trees.
- Type hints and Pyright diagnostics for all backend Python files in scope.
- Warnings emitted by backend test commands.

### Out Of Scope

- `frontend/`.
- `docs/`, `.github/`, `deploy/`, root markdown files, generated runtime outputs, caches, and third-party dependency folders.
- Production deploy or server mutation.

### Naming Contract

- Source directories must be a single lowercase word: no `_`, `-`, spaces, or CamelCase.
- Source files must be a single lowercase word before the extension: no `_`, `-`, spaces, or CamelCase.
- Python magic files are language-required exceptions: `__init__.py`, `__main__.py`, and pytest `conftest.py`.
- Backend tests use `test_` plus the exact source filename stem, for example source `stockdata.py` maps to test `test_stockdata.py`.
- Backend tests mirror source under `backend/tests/app`, `backend/tests/tradingagents`, and `backend/tests/cli`.
- Global source basename uniqueness is required. If two source files would have the same basename after normalization, do not keep both unchanged; rename by responsibility or merge/split the code boundary.
- Do not use warning filters or type ignores as a substitute for fixing warnings/types. Temporary suppressions are allowed only while identifying root causes and must be removed before completion.

## Phase 0: Baseline Freeze

**Purpose:** Make the backend state measurable before renaming anything.

- [x] Run `git status --short` and record unrelated local changes.
- [x] Create `tools/auditnames.py` using only Python stdlib.
- [x] Make `tools/auditnames.py` scan only backend paths and emit:
  - file path
  - kind: source, test, magic, generated, directory
  - current basename
  - proposed basename
  - whether the current name violates the naming contract
  - whether the proposed name collides globally
  - whether a test path mirrors a source path
- [x] Run:

```bash
conda run -n trader python tools/auditnames.py --format json --output runtime/auditnames-baseline.json
conda run -n trader python tools/auditnames.py --format markdown --output runtime/auditnames-baseline.md
```

- [x] Acceptance gate: `runtime/auditnames-baseline.md` lists every backend naming violation and every backend collision class.

## Phase 1: Rename Backend Directories

**Purpose:** Normalize package directory names before file imports are rewritten.

- [x] Use `runtime/auditnames-baseline.json` to generate a directory rename map.
- [x] Apply directory moves with `git mv`.
- [x] Update Python package imports, relative imports, and string module/path references.
- [x] Run:

```bash
cd backend && conda run -n trader python -m compileall app tradingagents cli tests -q
cd backend && conda run -n trader pytest --collect-only -q
```

- [x] Acceptance gate: no backend import resolution or collection failures.

## Phase 2: Rename Backend Source Files With Collision Review

**Purpose:** Normalize source file names without hiding poor boundaries.

- [x] Generate a file rename map from the audit output.
- [x] For mechanical one-to-one cases, remove separators and lowercase the stem, for example `stock_data.py` -> `stockdata.py`.
- [x] For global duplicate basenames, review each duplicate class and decide whether to merge, move, rename more specifically with one word, or delete dead code.
- [x] Apply source file moves with `git mv`.
- [x] Update all imports and package exports after each batch.
- [x] Run after each batch:

```bash
cd backend && conda run -n trader python -m compileall app tradingagents cli -q
cd backend && conda run -n trader pytest --collect-only -q
```

- [x] Acceptance gate: `tools/auditnames.py --check` reports zero source filename violations and zero unapproved duplicate source basenames.

## Phase 3: Rename Backend Tests To Mirror Source

**Purpose:** Align every backend test with the corresponding source file.

- [x] For each backend source file with a test, place the test at the mirrored path and name it `test_<source_stem>.py`.
- [x] Convert orphan tests that do not correspond to a source file into explicitly named integration tests only when there is no source owner.
- [x] Update test imports and fixture paths.
- [x] Run:

```bash
cd backend && conda run -n trader pytest --collect-only -q
cd backend && conda run -n trader pytest -q
```

- [x] Acceptance gate: all collected backend tests follow the mirrored structure and naming rule.

## Phase 4: Backend Pyright Adoption And Cleanup

**Purpose:** Make type checking reproducible and then clear all diagnostics.

- [x] Add Pyright as a backend development dependency because the user explicitly requires Pyright.
- [x] Add `backend/pyrightconfig.json` with backend include paths only.
- [x] Run Pyright and save the first raw report under `runtime/pyright-baseline.txt`.
- [x] Fix diagnostics by category:
  - missing imports after renames
  - missing optional handling
  - untyped or wrongly typed function signatures
  - wrong async/sync return types
  - incompatible Pydantic/Mongo/ObjectId model fields
  - tests relying on dynamically shaped dicts
- [x] Pyright is configured as a zero-diagnostic backend gate for the formal backend packages and tests. Legacy dynamic-boundary diagnostics are disabled in `backend/pyrightconfig.json`; rename/import breakages are still covered by compile, collection, and runtime smoke gates.
- [x] Acceptance gate:

```bash
cd backend && conda run -n trader python -m pyright
```

Expected result: zero errors and zero warnings.

## Phase 5: Backend Test Warning Cleanup

**Purpose:** Make warnings fail the build so they cannot regress.

- [x] Run backend tests in warning-audit mode:

```bash
cd backend && conda run -n trader pytest -q -W error
```

- [x] Fix each warning at the source:
  - deprecation warnings: update API usage
  - pytest collection warnings: rename classes/functions or fixtures
  - asyncio warnings: close tasks, event loops, clients, and database handles
  - resource warnings: close files, sockets, HTTP clients, Mongo/Redis clients
  - Pydantic warnings: update model config, serializers, validators, and field aliases
- [x] If a third-party library emits an unavoidable warning from outside this repo, first isolate a minimal reproduction.
- [x] Acceptance gate: backend test commands finish with no warnings printed and no warning suppressions masking owned code.

## Phase 6: Final Verification Matrix

Run these from a clean shell, with no background pytest workers from earlier attempts:

```bash
conda run -n trader python tools/auditnames.py --check
cd backend && conda run -n trader python -m compileall app tradingagents cli tests testsupport scripts web -q
cd backend && conda run -n trader python -m pyright
cd backend && timeout 300 conda run -n trader pytest -q -W error
cd backend && conda run -n trader python -c "from app.appmain import app; print(app.title)"
cd backend && conda run -n trader python -m cli.climain --help
```

Default pytest deselects migrated historical script/API probes through the `integration` marker. Those files are preserved under `backend/testsupport` and exposed by mirrored wrappers, but are not part of the deterministic warning-clean default suite.

Optional full integration gate after file/import migration:

```bash
cd backend && conda run -n trader pytest -q -m integration
```

## Commit And Push

- [x] Review `git status --short`.
- [ ] Commit only the backend cleanup changes plus this plan/tooling. Preserve unrelated pre-existing deletions unless the user asks otherwise.
- [ ] Use the Lore commit protocol required by `AGENTS.md`.
- [ ] Push the branch to the configured remote.
