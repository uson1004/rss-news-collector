# Newsletter and Custom Categories Design

## Goal

Add a newsletter flow to `읽을게` that lets a user create a custom reading category from a category name plus search hints, subscribe to that category by email, and receive periodic digests built from the same RSS pipeline already used by the news browser.

## Product Shape

The product should not ask users for RSS URLs up front. The input flow is:

1. Category name
2. Search hint text, such as a site name, blog name, or keywords
3. System-discovered RSS candidates
4. User selects one or more candidates
5. Category is saved and becomes available in both the news browser and newsletter subscription flow

The newsletter itself should reuse the same category model:

- Built-in categories remain available
- User-defined categories are stored alongside them
- A newsletter subscription points at a category, not at a raw RSS URL

## Architecture

The backend stays in FastAPI and keeps the current RSS parsing pipeline. A small storage layer keeps category and subscription records in SQLite for now, with a narrow interface so the storage backend can later be moved to Supabase without rewriting the app.

The backend is split conceptually into three responsibilities:

- category discovery from search hints
- rule-based discovery first, then Claude-assisted expansion when the hint is too weak
- persistence for categories and subscriptions
- digest composition and email delivery

The frontend adds a lightweight onboarding modal for category creation and a newsletter subscription panel on the news screen. The modal is intentionally short and step-based so users never have to understand RSS before the feature works.

## Data Model

The design uses three core records:

```text
newsletter_categories
- id
- label
- search_hint
- created_at

newsletter_sources
- id
- category_id
- feed_url
- source_label
- created_at

newsletter_subscriptions
- id
- email
- category_id
- cadence
- status
- unsubscribe_token
- created_at
- last_sent_at
```

This keeps the user-facing category separate from the underlying feed sources and the email subscription state.

## Discovery Strategy

The user enters search hints instead of RSS URLs. The backend resolves those hints in two ways:

1. A curated local feed catalog for well-known sources and keywords
2. RSS autodiscovery when the hint looks like a domain, homepage, or blog name
3. Claude-assisted expansion when the first pass is too weak or empty

The discovery response returns ranked candidates with source title, feed URL, and a short explanation so the user can choose before saving. If discovery finds nothing useful, the UI asks the user to refine the hint instead of exposing RSS internals.

## Newsletter Flow

The newsletter flow should reuse the current article pipeline:

1. Resolve the selected category to its feed URLs
2. Collect recent feed items
3. Parse article bodies where possible
4. Build a digest from existing summaries or excerpt fallback
5. Send the digest to all active subscriptions for that category

For the first implementation, the digest can be a simple weekly-style summary with a small fixed number of items per category. The important part is that the category is the control surface, not the raw feed URL.

## UI Flow

The news screen gets two new entry points:

- `카테고리 추가`
- `뉴스레터 구독`

`카테고리 추가` opens a modal wizard:

1. Enter category name
2. Enter search hints
3. Review discovered RSS candidates
4. Save the category

`뉴스레터 구독` is a small form on the page:

- email address
- category selection
- cadence selection
- subscribe button

## Constraints

- Do not add a new dependency unless the existing standard library or current packages cannot do the job.
- Keep the category model compatible with the current built-in RSS category shape.
- Keep the storage interface thin so Supabase can replace SQLite later.
- Avoid exposing RSS URL handling in the primary UI; it should stay behind discovery.

## Success Criteria

The design is complete when:

- a user can create a category from a name and search hint
- the app shows candidate feeds without asking for a raw RSS URL
- the user can subscribe to that category by email
- the backend can generate and send a digest from the stored category
- the existing news browser still works for built-in categories
