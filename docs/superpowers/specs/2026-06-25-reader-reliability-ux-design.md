# Reader Reliability and UX Design

## Goal

Ship ten independently reviewable fixes that make the reader safer, more resilient, and easier to recover and navigate without changing its core product scope.

## Design

1. Treat Supabase as an optional demonstration integration. Missing client credentials must disable only the todos panel, not the application.
2. Reject loopback, private, link-local, multicast, reserved, and otherwise non-public article destinations before the server performs HTTP requests. Re-check redirected destinations through the HTTP client's request hook.
3. Make an active newsletter subscription unique by normalized email, category, and cadence. Repeated subscription calls return the existing active subscription instead of creating duplicates.
4. Give each feed request an abort signal and ignore results from superseded requests.
5. Centralize frontend API response decoding so HTML, empty, and malformed error responses produce stable user-facing messages.
6. Normalize scheme-less URL input before navigation and use text input with URL-oriented keyboard hints so browser validation does not reject supported input.
7. Add retry and return actions to the reader error state.
8. Implement proper tab semantics and left/right/home/end keyboard navigation for RSS categories.
9. Make the category modal close on Escape, trap Tab focus, focus its first control on open, and restore focus on close.
10. Include a public unsubscribe URL in text and HTML newsletters, backed by a browser-friendly unsubscribe endpoint.

## Boundaries

- No new runtime dependencies.
- Existing API response shapes remain compatible except for additive fields.
- SQLite migrations must work against existing databases.
- Every behavioral change gets a regression test before implementation.
- The work is delivered as exactly ten code commits.

## Verification

- Node built-in tests for frontend utilities.
- Python unittest coverage for server validation, storage, and newsletter rendering.
- Production frontend build.
- Full backend unittest suite.
- Manual API smoke tests for health, demo parsing, duplicate subscription behavior, and unsubscribe rendering.

