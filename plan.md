# Implementation Plan: `xl` Agent-First Excel CLI

## Overview

Implement the `xl` CLI as described in `xl-agent-cli-prd.md`. This is a Python-based, agent-first CLI for Excel workbooks using `openpyxl`, `Typer`, `Pydantic v2`, and supporting libraries. The plan follows the PRD's milestone structure, targeting the v1 slice outlined in Section 30.

---

## Phase 1: Foundation (Milestone 0) — COMPLETE

### Step 1.1 — Project scaffolding ✅
### Step 1.2 — Source package structure ✅
### Step 1.3 — Response envelope and error taxonomy ✅
### Step 1.4 — CLI framework + global flags ✅
### Step 1.5 — Workbook context and fingerprinting ✅
### Step 1.6 — `xl wb inspect` ✅
### Step 1.7 — `xl sheet ls` ✅
### Step 1.8 — `xl version` ✅
### Step 1.9 — Test infrastructure ✅

---

## Phase 2: Table Operations + Patch Plans (Milestone 1) — COMPLETE

### Step 2.1 — `xl table ls` ✅
### Step 2.2 — `xl table add-column` ✅
### Step 2.3 — `xl table append-rows` ✅
### Step 2.4 — Patch plan schema + `xl plan show` ✅
### Step 2.5 — Plan generators ✅
### Step 2.6 — `xl apply --dry-run` and `xl apply` ✅
### Step 2.7 — Tests for table operations and patch lifecycle ✅

---

## Phase 3: Formula + Cell/Range + Formatting (Milestone 3) — COMPLETE

### Step 3.1 — `xl formula set` ✅
### Step 3.2 — `xl formula lint` ✅
### Step 3.3 — `xl formula find` ✅
### Step 3.4 — `xl cell get` ✅
### Step 3.5 — `xl range stat` ✅
### Step 3.6 — `xl range clear` ✅
### Step 3.7 — `xl format` commands (`number`, `width`, `freeze`) ✅
### Step 3.8 — `xl validate refs` ✅
### Step 3.9 — Tests for Phase 3 (20 tests in `tests/test_phase3.py`) ✅

---

## Phase 4: Verify, Diff, and Policy (Milestone 2 completion) — COMPLETE

### Step 4.1 — `xl verify assert` ✅
### Step 4.2 — `xl diff compare` ✅
### Step 4.3 — Policy engine (`xl-policy.yaml`) ✅
### Step 4.4 — `xl wb lock-status` ✅
### Step 4.5 — Tests for Phase 4 (15 tests in `tests/test_phase4.py`) ✅

---

## Phase 5: Workflows + Observability (Milestone 4) — COMPLETE

### Step 5.1 — `xl run` workflow execution ✅
### Step 5.2 — Event stream (`EventEmitter`) ✅
### Step 5.3 — Trace mode (`TraceRecorder`) ✅
### Step 5.4 — `xl serve --stdio` ✅
### Step 5.5 — Tests for Phase 5 (15 tests in `tests/test_phase5.py`) ✅

---

## Phase 6: Hardening (Milestone 5)

### Step 6.1 — Golden workbook fixtures
- Create `tests/fixtures/workbooks/` with pre-built .xlsx files covering edge cases:
  - Workbook with hidden sheets
  - Workbook with named ranges
  - Workbook with multiple tables across sheets
  - Workbook with formulas (volatile, broken refs, mixed patterns)
  - Workbook with various number formats
  - Large workbook (1000+ rows)

### Step 6.2 — Property-based tests
- Use `hypothesis` for:
  - Plan generation → apply → verify round-trip
  - Random cell values → set → get consistency
  - Table append → row count correctness

### Step 6.3 — Performance testing
- Test with large workbooks (10K+ rows)
- Ensure read-only mode is used for inspection commands
- Profile and optimize hot paths

### Step 6.4 — Cross-platform verification
- Verify file locking on Linux
- Document platform-specific behavior

---

## Implementation Notes

- **Develop on branch**: `claude/continue-prd-4NQv5`
- **Python version**: 3.12+
- **Package manager**: `uv`
- **Build system**: `hatchling`
- **All commands** return the standard `ResponseEnvelope` JSON
- **Exit codes** follow the taxonomy in PRD Section 19
- **Testing**: pytest with fixtures, golden outputs, and property-based tests

## Implementation Summary

All v1 features from the PRD are implemented across Phases 1–5. The CLI is feature-complete with 99 passing tests covering:
- 49 tests from Phases 1–2 (foundation, tables, patch plans)
- 20 tests from Phase 3 (formula, cell/range, formatting)
- 15 tests from Phase 4 (verify, diff, policy, lock-status)
- 15 tests from Phase 5 (workflows, events, trace, stdio server)

**Remaining work** (Phase 6 — Hardening): golden fixtures, property-based tests, performance benchmarks, cross-platform verification.
