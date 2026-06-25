# Newsletter and Custom Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users create RSS-backed custom categories from a name and search hint, subscribe to those categories by email, and receive newsletter digests built from the existing RSS/article pipeline.

**Architecture:** Keep the current React + FastAPI app, but add a thin newsletter storage layer and a discovery layer. The frontend opens a short onboarding modal to create categories without exposing raw RSS URLs, then a newsletter subscription panel uses the saved categories. The backend composes digests from the existing feed parsing and article extraction flow, and sends mail through standard-library SMTP so no new dependency is needed.

**Tech Stack:** React, Vite, FastAPI, SQLite via `sqlite3`, `httpx`, `BeautifulSoup4`, `trafilatura`, Claude Messages API, standard-library `smtplib`/`email`, localStorage for UI state only.

---

### Task 1: Add newsletter storage and feed discovery primitives

**Files:**
- Create: `server/newsletter_store.py`
- Create: `server/newsletter_discovery.py`
- Modify: `server/main.py`

- [ ] **Step 1: Add the storage schema and repository functions**

```python
"""SQLite-backed storage for newsletter categories and subscriptions."""

def ensure_schema() -> None: ...
def list_custom_categories() -> list[dict[str, str]]: ...
def create_custom_category(label: str, search_hint: str, sources: list[dict[str, str]]) -> dict[str, str]: ...
def list_subscriptions() -> list[dict[str, str]]: ...
def create_subscription(email: str, category_id: str, cadence: str) -> dict[str, str]: ...
def mark_subscription_sent(subscription_id: str, sent_at: str) -> None: ...
```

Use a single SQLite file under `server/` and keep the functions thin enough that the storage backend can later be replaced without changing the HTTP layer.

- [ ] **Step 2: Add hint-based feed discovery**

```python
"""Resolve a category name and search hint into candidate RSS feeds."""

def normalize_hint(value: str) -> str: ...
def discover_feed_candidates(label: str, search_hint: str) -> list[dict[str, str]]: ...
def discover_from_domain_hint(search_hint: str) -> list[dict[str, str]]: ...
def score_catalog_candidate(candidate: dict[str, str], hint: str) -> int: ...
```

The discovery logic should first try a local curated catalog of known feeds, then try RSS autodiscovery if the hint looks like a site/domain. If the first pass is too weak, Claude expands the hint into likely publication names, domains, or search phrases, and the backend validates those against the same RSS discovery path. The output needs to be user-facing candidate records, not raw parser internals.

- [ ] **Step 3: Verify the new module imports cleanly**

Run:

```bash
python3 -m py_compile server/main.py server/newsletter_store.py server/newsletter_discovery.py
```

Expected: no syntax errors.

---

### Task 2: Wire newsletter category and subscription endpoints into FastAPI

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Add request/response models for category discovery and subscriptions**

```python
class NewsletterCategoryDiscoverRequest(BaseModel):
    label: str
    search_hint: str

class NewsletterCategoryCandidate(BaseModel):
    source_label: str
    feed_url: str
    reason: str

class NewsletterCategoryCreateRequest(BaseModel):
    label: str
    search_hint: str
    sources: list[NewsletterCategoryCandidate]

class NewsletterSubscribeRequest(BaseModel):
    email: str
    category_id: str
    cadence: str
```

- [ ] **Step 2: Add category discovery and persistence endpoints**

```python
@app.post("/api/newsletter/discover")
async def discover_newsletter_category(request: NewsletterCategoryDiscoverRequest) -> list[NewsletterCategoryCandidate]: ...

@app.post("/api/newsletter/categories")
async def create_newsletter_category(request: NewsletterCategoryCreateRequest) -> dict[str, str]: ...

@app.get("/api/newsletter/categories")
async def get_newsletter_categories() -> list[dict[str, str]]: ...
```

The discover endpoint should surface candidates and the create endpoint should persist the chosen sources together with the label and hint.

- [ ] **Step 3: Add subscription endpoints**

```python
@app.post("/api/newsletter/subscribe")
async def subscribe_newsletter(request: NewsletterSubscribeRequest) -> dict[str, str]: ...

@app.post("/api/newsletter/unsubscribe")
async def unsubscribe_newsletter(token: str) -> dict[str, str]: ...
```

Subscriptions only need one cadence for the first release, so default to weekly and keep the UI simple.

- [ ] **Step 4: Run a backend smoke check**

Run:

```bash
python3 -m py_compile server/main.py
```

Then run the server and verify:

```bash
curl -s http://localhost:8000/api/newsletter/categories
curl -s -X POST http://localhost:8000/api/newsletter/discover \
  -H 'Content-Type: application/json' \
  -d '{"label":"스타트업","search_hint":"TechCrunch, VC, 창업"}'
```

Expected: the first call returns a JSON list, the second returns at least one candidate or a clear refinement message.

---

### Task 3: Add digest composition and email delivery

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Compose newsletter body from existing feed/article data**

```python
def build_newsletter_digest(category_id: str, limit: int = 3) -> dict[str, object]: ...
def render_newsletter_text(digest: dict[str, object]) -> str: ...
def render_newsletter_html(digest: dict[str, object]) -> str: ...
```

The digest should reuse the current RSS feed collection and article parsing flow. If article parsing or summary generation fails, fall back to the feed excerpt instead of failing the entire newsletter.

- [ ] **Step 2: Add SMTP delivery**

```python
def send_newsletter_email(to_email: str, subject: str, text_body: str, html_body: str) -> None: ...
```

Use environment variables for SMTP configuration and keep the email sender isolated behind one function.

- [ ] **Step 3: Add preview and send endpoints**

```python
@app.post("/api/newsletter/preview")
async def preview_newsletter(category_id: str) -> dict[str, str]: ...

@app.post("/api/newsletter/send-test")
async def send_test_newsletter(email: str, category_id: str) -> dict[str, str]: ...
```

Preview returns the rendered content without sending mail. Test send exercises the full email path.

- [ ] **Step 4: Run a manual delivery smoke test**

Run:

```bash
curl -s -X POST http://localhost:8000/api/newsletter/preview \
  -H 'Content-Type: application/json' \
  -d '{"category_id":"geeknews"}'
```

Expected: a subject and body payload that reflects current feed content.

---

### Task 4: Add the onboarding modal and subscription panel in the frontend

**Files:**
- Modify: `client/src/main.jsx`
- Modify: `client/src/styles.css`

- [ ] **Step 1: Add a modal state and a category onboarding button**

```jsx
const [newsletterModalOpen, setNewsletterModalOpen] = useState(false);
const [newsletterDraft, setNewsletterDraft] = useState({
  label: '',
  searchHint: '',
  candidates: [],
  selectedSourceIds: [],
});
```

The news screen should expose a `카테고리 추가` action that opens the modal.

- [ ] **Step 2: Build the three-step onboarding flow**

```jsx
<NewsletterCategoryModal
  open={newsletterModalOpen}
  draft={newsletterDraft}
  onChangeDraft={setNewsletterDraft}
  onDiscover={discoverNewsletterCandidates}
  onSave={saveNewsletterCategory}
  onClose={() => setNewsletterModalOpen(false)}
/>
```

The modal steps are:

1. category name
2. search hint
3. candidate review and save

Do not expose RSS URLs as the primary user input.

- [ ] **Step 3: Add the newsletter subscription form**

```jsx
<NewsletterSubscribePanel
  categories={allCategories}
  onSubscribe={subscribeNewsletter}
/>
```

This panel belongs on the news screen, not the reader page. It should allow the user to choose a category, enter an email address, and subscribe with the default cadence.

- [ ] **Step 4: Style the modal and subscription panel**

Add modal overlay, step layout, candidate list cards, and compact form controls. Keep the visual style consistent with the current reader UI and do not introduce a separate design language.

- [ ] **Step 5: Run the frontend build**

Run:

```bash
npm run build
```

Expected: build succeeds without warnings that block deployment.

---

### Task 5: Update docs and verify the end-to-end flow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the new newsletter flow**

Update the README to explain:

```text
카테고리 이름 + 검색 힌트 입력
→ RSS 후보 발견
→ 카테고리 저장
→ 이메일 구독
→ 뉴스레터 발송
```

- [ ] **Step 2: Document the SMTP environment variables**

Add the exact environment variables used by the mailer so setup is repeatable.

- [ ] **Step 3: Run the final smoke checks**

Run:

```bash
python3 -m py_compile server/main.py server/newsletter_store.py server/newsletter_discovery.py
npm run build
```

Then verify in the browser:

1. open `/#/news`
2. open the category onboarding modal
3. create a category from a search hint
4. subscribe an email to the category
5. open the reader page and confirm existing flows still work
