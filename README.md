# 읽을게

URL을 입력하면 복잡한 웹페이지에서 본문을 추출해 접근성 좋은 리더 뷰로 보여주는 1차 MVP입니다.

## 1차 MVP 범위

- URL 입력
- 상단 헤더의 `뉴스 읽기` / `URL로 본문 추출` 화면 분리
- FastAPI 서버의 `/api/parse`에서 본문 추출
- 직접 추출이 막히면 공식 RSS/feed를 fallback으로 사용
- 제목, 출처, 요약 설명, 본문 표시
- 단락 단위 본문 표시
- 글자 크기 조절
- 줄 간격 조절
- 문단 간격 조절
- 본문 폭 조절
- 밝은 화면, 어두운 화면, 고대비 모드
- AI 요약 패널
- AI 관찰 노트 패널
- TTS 음성 읽기
- RSS 카테고리 브라우저와 `아이디어 레이더` 기본 큐레이션
- 사용자화 카테고리 추가
- 뉴스레터 구독
- 추출 실패 안내
- 로컬 데모 기사 제공

## 제외한 기능

- 쉬운말 변환
- 자동 태깅
- NewsAPI 카테고리 브라우저
- 북마크

## 기술 스택

### Frontend

- React
- Vite
- CSS
- localStorage
- Web Speech API

### Backend

- FastAPI
- httpx
- trafilatura
- BeautifulSoup4
- Pydantic
- Claude Messages API
- DeepL API
- RSS/Atom feed parsing
- SQLite 저장소
- SMTP 뉴스레터 발송

## 실행 방법

### 1. 백엔드

```bash
cd server
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

백엔드 문서:

```txt
http://localhost:8000/docs
```

AI 요약과 AI 관찰 노트를 사용하려면 백엔드 실행 전에 Claude API 키를 설정합니다.

```bash
export ANTHROPIC_API_KEY="your_api_key_here"
export ANTHROPIC_MODEL="claude-haiku-4-5-20251001"
export DEEPL_API_KEY="your_deepl_api_key_here"
export NEWSLETTER_SMTP_HOST="smtp.example.com"
export NEWSLETTER_SMTP_PORT="587"
export NEWSLETTER_SMTP_USERNAME="your_username"
export NEWSLETTER_SMTP_PASSWORD="your_password"
export NEWSLETTER_FROM_EMAIL="noreply@example.com"
export NEWSLETTER_ADMIN_SECRET="change_this_for_batch_endpoint"
```

`ANTHROPIC_API_KEY`가 없으면 원문 리더 뷰는 그대로 동작하고, AI 요약과 AI 관찰 노트 버튼만 안내 메시지를 표시합니다.
`DEEPL_API_KEY`가 없으면 원문 리더 뷰와 요약은 그대로 동작하고, 번역 버튼만 안내 메시지를 표시합니다.
`NEWSLETTER_SMTP_*` 값이 없으면 뉴스레터 구독은 저장되지만 첫 메일 발송은 안내 메시지로 대체합니다.
`NEWSLETTER_ADMIN_SECRET`은 선택 사항입니다. 설정한 경우에만 서버 API로 예약 발송을 트리거할 수 있습니다.

### 뉴스레터 예약 발송

구독자에게 주간 뉴스레터를 보내려면 백엔드의 배치 스크립트를 실행합니다.

```bash
cd server
python deliver_newsletters.py --limit 100
```

실제 발송 없이 이번 주 발송 대상만 확인하려면 dry-run을 사용합니다.

```bash
cd server
python deliver_newsletters.py --dry-run --limit 10
```

cron 예시:

```cron
0 9 * * MON cd /path/to/rss-news/server && /usr/bin/python3 deliver_newsletters.py --limit 100 >> newsletter-delivery.log 2>&1
```

배치는 UTC ISO 주차(`YYYY-Www`) 단위로 구독별 발송 시도를 SQLite에 기록합니다. 같은 주차에는 구독자 1명당 자동 발송을 한 번만 시도하며, 실패한 시도는 기록하지만 자동 재시도하지 않습니다. 구독 직후 첫 메일을 성공적으로 보낸 경우에도 같은 주차의 예약 발송에서 제외됩니다.

서버 API로 트리거해야 하는 환경에서는 `NEWSLETTER_ADMIN_SECRET`을 설정한 뒤 헤더로 같은 값을 보냅니다.

```http
POST /api/newsletter/deliver-due?limit=100&dry_run=true
X-Newsletter-Admin-Secret: change_this_for_batch_endpoint
```

관리 비밀값이 설정되지 않았거나 헤더가 일치하지 않으면 요청은 거부됩니다.

### 2. 프론트엔드

새 터미널에서 실행합니다.

```bash
npm install
npm run dev
```

프론트엔드:

```txt
http://localhost:5173
```

## API

```http
POST /api/parse
Content-Type: application/json

{
  "url": "https://example.com/article"
}
```

응답 예시:

```json
{
  "title": "기사 제목",
  "site_name": "example.com",
  "url": "https://example.com/article",
  "text": "본문...",
  "paragraphs": ["첫 번째 문단", "두 번째 문단"],
  "excerpt": "요약 설명...",
  "word_count": 240
}
```

### AI 요약

```http
POST /api/summarize
Content-Type: application/json

{
  "title": "기사 제목",
  "text": "본문..."
}
```

응답 예시:

```json
{
  "summary": ["핵심 요약 1", "핵심 요약 2", "핵심 요약 3"],
  "model": "claude-haiku-4-5-20251001"
}
```

### AI 관찰 노트

```http
POST /api/article-insight
Content-Type: application/json

{
  "title": "기사 제목",
  "text": "본문...",
  "source": "매체명",
  "category": "idea_radar"
}
```

응답 예시:

```json
{
  "why_read": ["지금 한국 사회의 변화 신호를 보여주는 기사입니다."],
  "signals": ["청년 주거 불안이 새로운 소비 선택으로 이어집니다."],
  "frictions_or_desires": ["사용자는 복잡한 정책 설명보다 실제 선택지를 먼저 알고 싶어합니다."],
  "idea_prompts": ["이 불편을 매주 추적하는 개인화 알림을 만든다면 어떤 기준이 필요할까요?"],
  "caveats": ["AI가 작성한 관찰 노트이므로 사실 판단은 원문 기준으로 확인해야 합니다."],
  "model": "claude-haiku-4-5-20251001"
}
```

요약이 원문 내용을 짧게 압축하는 기능이라면, 관찰 노트는 기사에서 읽을만한 사회적 신호, 불편, 욕망, 제품 아이디어를 뽑아내는 보조 기능입니다. 원문을 대체하지 않고 리더 뷰 안에서만 함께 보여줍니다.

### 질문 프롬프트 생성

```http
POST /api/follow-up-prompt
Content-Type: application/json

{
  "title": "기사 제목",
  "summary": ["핵심 요약 1", "핵심 요약 2", "핵심 요약 3"]
}
```

응답 예시:

```json
{
  "prompt": "아래 기사 요약을 바탕으로..."
}
```

요약을 만든 뒤 사용자가 `질문 생성하기`를 눌렀을 때만 호출됩니다.

### AI 번역

```http
POST /api/translate
Content-Type: application/json

{
  "title": "기사 제목",
  "text": "본문...",
  "target_language": "English"
}
```

응답 예시:

```json
{
  "translated_text": "Translated body...",
  "paragraphs": ["Translated paragraph 1", "Translated paragraph 2"],
  "model": "deepl-api-free",
  "target_language": "English"
}
```

본문을 불러온 뒤 사용자가 `번역하기`를 눌렀을 때만 호출됩니다.
현재 번역은 DeepL API Free 엔드포인트를 사용합니다.
지원 선택지: 한국어, 영어, 일본어, 중국어(간체)

### RSS 카테고리

```http
GET /api/categories
GET /api/feeds/{category}
```

지원 카테고리:

- `idea_radar`
- `geeknews`
- `android`
- `tech`
- `business`
- `world`
- `science`
- `sports`

기본 카테고리는 한국 사용자가 바로 읽기 좋도록 국내 뉴스 RSS와 국내 기술블로그 RSS를 중심으로 구성했습니다.
카테고리별 키워드 필터와 최신순 정렬을 적용해, 한국어로 관련 글을 찾을 때 나오는 흐름에 가깝게 보여줍니다.
`idea_radar`는 청년, 주거, 노동, 소비, 커뮤니티, AI/스타트업처럼 한국 사회의 변화와 서비스 아이디어로 이어질 수 있는 주제를 우선 노출합니다.
`geeknews`는 기존 긱뉴스 RSS를 유지하고, 국내 기술블로그 RSS를 함께 사용합니다.

### 사용자화 카테고리 / 뉴스레터

```http
POST /api/newsletter/discover
POST /api/newsletter/categories
POST /api/newsletter/subscribe
POST /api/newsletter/unsubscribe
POST /api/newsletter/preview
POST /api/newsletter/send-test
POST /api/newsletter/deliver-due
```

사용자는 카테고리 이름과 검색 힌트만 입력하고, 서버가 RSS 후보를 찾아줍니다.
탐색은 먼저 내부 카탈로그와 도메인 자동 발견으로 시도하고, 후보가 약하면 Claude가 힌트를 해석해 검색 범위를 넓힙니다.
저장된 사용자화 카테고리는 `GET /api/categories`와 `GET /api/feeds/{category}`에서 바로 사용할 수 있습니다.

응답 예시:

```json
{
  "category": "tech",
  "label": "IT",
  "items": [
    {
      "title": "글 제목",
      "url": "https://example.com/article",
      "source": "Feed name",
      "category": "tech",
      "published": "Tue, 02 Jun 2026 00:00:00 GMT",
      "excerpt": "글 설명..."
    }
  ]
}
```

### TTS

TTS는 서버 API가 아니라 브라우저 내장 Web Speech API로 동작합니다.
본문을 불러온 뒤 `음성 읽기`, `일시정지`, `다시 읽기`, `정지` 버튼으로 제어합니다.

## 데모

상단 헤더에서 두 가지 읽기 흐름을 선택할 수 있습니다.

- `/#/news`: 뉴스 읽기. 기본값은 `아이디어 레이더`이며 RSS 카테고리에서 글을 고른 뒤 리더 뷰로 열기
- `/#/url`: URL로 본문 추출. 직접 URL을 입력하거나 샘플 URL로 리더 뷰 열기
- `/#/reader`: 공통 리더 페이지. 뉴스 글 또는 URL 입력 결과를 본문으로 표시

뉴스 글의 `읽기` 버튼이나 URL 입력 화면의 `읽기` 버튼을 누르면 대상 URL을 저장한 뒤 `/#/reader`로 이동합니다.
리더 페이지에서 본문 로딩, 실패 안내, 읽기 설정, TTS, 요약, AI 관찰 노트, 번역을 처리합니다.

프론트의 `데모 기사로 보기` 버튼은 백엔드의 `/demo/article` HTML 페이지를 실제 URL처럼 요청합니다.
외부 사이트 차단이나 네트워크 상태와 상관없이 본문 추출 흐름을 확인하기 위한 샘플입니다.

## 실제 URL 테스트 메모

성공한 테스트 URL:

- `https://developer.mozilla.org/ko/docs/Learn_web_development/Core/Accessibility/What_is_accessibility`
- `https://fastapi.tiangolo.com/ko/`
- `https://www.djangoproject.com/weblog/2025/dec/03/django-60-released/`

실패할 수 있는 URL:

- 뉴스 메인 페이지처럼 개별 본문이 없는 페이지
- 크롤링을 차단하거나 봇 접근을 막는 뉴스 사이트
- JavaScript 렌더링 후에야 본문이 생기는 페이지
