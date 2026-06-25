# Reader Reliability and UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver ten independent safety, reliability, and accessibility improvements as ten tested commits.

**Architecture:** Keep backend protections and persistence rules in focused Python helpers, and extract frontend behavior into dependency-free utility modules tested with Node's built-in test runner. Integrate each helper into the existing React application with minimal JSX changes.

**Tech Stack:** React, Vite, Node test runner, FastAPI, Pydantic, SQLite, Python unittest.

---

### Task 1: Optional Supabase integration

**Files:**
- Modify: `client/src/utils/supabase.js`
- Modify: `client/src/main.jsx`
- Create: `client/src/utils/supabase.test.js`
- Modify: `client/package.json`
- Modify: `docs/superpowers/specs/2026-06-25-reader-reliability-ux-design.md`
- Modify: `docs/superpowers/plans/2026-06-25-reader-reliability-ux.md`

- [ ] Write a failing test proving missing credentials return no client.
- [ ] Run `npm --prefix client test -- supabase.test.js` and confirm failure.
- [ ] Export an optional client factory and skip the todos query when unavailable.
- [ ] Run the focused test and `npm run build`.
- [ ] Commit as the first reliability fix.

### Task 2: Block server-side requests to non-public destinations

**Files:**
- Modify: `server/main.py`
- Modify: `server/test_parse_request.py`

- [ ] Add failing tests for loopback, private, link-local, and public hosts.
- [ ] Run the focused unittest and confirm failure.
- [ ] Add hostname/IP resolution validation before article fetches.
- [ ] Run focused and full backend tests.
- [ ] Commit the SSRF protection.

### Task 3: Prevent duplicate active subscriptions

**Files:**
- Modify: `server/newsletter_store.py`
- Modify: `server/test_newsletter_delivery.py`

- [ ] Add a failing test for repeated normalized subscription requests.
- [ ] Run the focused test and confirm two records are currently created.
- [ ] Add a partial unique index and reuse/reactivate the matching subscription.
- [ ] Run newsletter and full backend tests.
- [ ] Commit the storage invariant.

### Task 4: Ignore superseded feed responses

**Files:**
- Create: `client/src/utils/latestRequest.js`
- Create: `client/src/utils/latestRequest.test.js`
- Modify: `client/src/main.jsx`

- [ ] Add a failing utility test for superseded request identity.
- [ ] Run the focused Node test and confirm failure.
- [ ] Implement request cancellation/currentness tracking and integrate it into feed loading.
- [ ] Run frontend tests and build.
- [ ] Commit the race-condition fix.

### Task 5: Normalize frontend API errors

**Files:**
- Create: `client/src/utils/api.js`
- Create: `client/src/utils/api.test.js`
- Modify: `client/src/main.jsx`

- [ ] Add failing tests for JSON, HTML, malformed JSON, and empty responses.
- [ ] Run the focused Node tests and confirm failure.
- [ ] Implement `requestJson` and replace direct response decoding.
- [ ] Run frontend tests and build.
- [ ] Commit unified API error handling.

### Task 6: Accept scheme-less URLs

**Files:**
- Create: `client/src/utils/url.js`
- Create: `client/src/utils/url.test.js`
- Modify: `client/src/main.jsx`

- [ ] Add failing URL normalization tests.
- [ ] Run the focused Node test and confirm failure.
- [ ] Normalize input before storing it and change the field to text with URL input hints.
- [ ] Run frontend tests and build.
- [ ] Commit scheme-less URL support.

### Task 7: Add reader error recovery

**Files:**
- Create: `client/src/utils/readerRecovery.js`
- Create: `client/src/utils/readerRecovery.test.js`
- Modify: `client/src/main.jsx`
- Modify: `client/src/styles.css`

- [ ] Add failing tests for retry and return recovery actions.
- [ ] Run the focused Node test and confirm failure.
- [ ] Add action callbacks and visible recovery buttons to the error state.
- [ ] Run frontend tests and build.
- [ ] Commit the recovery UX.

### Task 8: Implement accessible category tabs

**Files:**
- Create: `client/src/utils/tabs.js`
- Create: `client/src/utils/tabs.test.js`
- Modify: `client/src/main.jsx`

- [ ] Add failing keyboard navigation tests for arrows, Home, and End.
- [ ] Run the focused Node test and confirm failure.
- [ ] Add tab roles, selection state, roving tab index, and focus movement.
- [ ] Run frontend tests and build.
- [ ] Commit keyboard-accessible tabs.

### Task 9: Implement accessible modal focus behavior

**Files:**
- Create: `client/src/utils/dialog.js`
- Create: `client/src/utils/dialog.test.js`
- Modify: `client/src/main.jsx`
- Modify: `client/src/styles.css`

- [ ] Add failing tests for Escape handling and focus wrapping.
- [ ] Run the focused Node test and confirm failure.
- [ ] Add dialog refs, initial focus, focus restoration, Escape close, and Tab trapping.
- [ ] Run frontend tests and build.
- [ ] Commit modal accessibility behavior.

### Task 10: Add newsletter unsubscribe links

**Files:**
- Modify: `server/main.py`
- Modify: `server/newsletter_delivery.py`
- Modify: `server/test_newsletter_delivery.py`

- [ ] Add failing tests for text/HTML unsubscribe links and browser unsubscribe behavior.
- [ ] Run focused tests and confirm failure.
- [ ] Pass subscription tokens into rendering and add a public GET unsubscribe route.
- [ ] Run full backend tests and frontend build.
- [ ] Commit the unsubscribe flow.

### Final verification

- [ ] Run `npm --prefix client test`.
- [ ] Run `npm run build`.
- [ ] Run `server/.venv/bin/python -m unittest discover -s server -p 'test_*.py'`.
- [ ] Run `git diff --check`.
- [ ] Confirm exactly ten new commits and a clean worktree.
- [ ] Push `main` to `origin`.

