from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class CatalogEntry:
    source_label: str
    feed_url: str
    homepage: str
    keywords: tuple[str, ...]
    reason: str


CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        source_label="긱뉴스",
        feed_url="https://news.hada.io/rss/news",
        homepage="https://news.hada.io",
        keywords=("긱뉴스", "geeknews", "개발", "스타트업", "it", "기술"),
        reason="현재 앱의 긱뉴스 피드와 같은 출처",
    ),
    CatalogEntry(
        source_label="Google Developers Korea Blog",
        feed_url="https://developers-kr.googleblog.com/feeds/posts/default?alt=rss",
        homepage="https://developers-kr.googleblog.com",
        keywords=("구글", "google", "android", "안드로이드", "개발", "ai", "gemini"),
        reason="한국어 Google 개발자 블로그 RSS로 실제 글 URL을 제공합니다",
    ),
    CatalogEntry(
        source_label="Android Developers Blog",
        feed_url="https://android-developers.googleblog.com/feeds/posts/default?alt=rss",
        homepage="https://android-developers.googleblog.com",
        keywords=("android", "안드로이드", "kotlin", "jetpack", "mobile", "모바일"),
        reason="Android 공식 개발자 블로그 RSS로 실제 글 URL을 제공합니다",
    ),
    CatalogEntry(
        source_label="우아한형제들 기술블로그",
        feed_url="https://techblog.woowahan.com/feed/",
        homepage="https://techblog.woowahan.com",
        keywords=("우아한형제들", "배민", "기술블로그", "개발", "백엔드", "프론트엔드", "모바일"),
        reason="국내 서비스 개발 사례를 볼 수 있는 공개 기술블로그 RSS",
    ),
    CatalogEntry(
        source_label="네이버 D2",
        feed_url="https://d2.naver.com/d2.atom",
        homepage="https://d2.naver.com",
        keywords=("네이버", "d2", "기술블로그", "개발", "웹", "ai", "데이터"),
        reason="국내 개발자가 참고하기 좋은 네이버 기술 콘텐츠 Atom 피드",
    ),
    CatalogEntry(
        source_label="카카오테크",
        feed_url="https://tech.kakao.com/feed/",
        homepage="https://tech.kakao.com",
        keywords=("카카오", "kakao", "기술블로그", "개발", "ai", "플랫폼"),
        reason="카카오의 국내 기술블로그 RSS",
    ),
    CatalogEntry(
        source_label="LINE Engineering",
        feed_url="https://engineering.linecorp.com/ko/feed/index.html",
        homepage="https://engineering.linecorp.com/ko/",
        keywords=("라인", "line", "기술블로그", "개발", "모바일", "플랫폼"),
        reason="LINE Engineering 한국어 RSS",
    ),
    CatalogEntry(
        source_label="TechCrunch",
        feed_url="https://techcrunch.com/feed/",
        homepage="https://techcrunch.com",
        keywords=("techcrunch", "startup", "vc", "venture", "ai startup", "실리콘밸리"),
        reason="스타트업과 투자 뉴스에 잘 맞는 공개 RSS",
    ),
    CatalogEntry(
        source_label="Hacker News",
        feed_url="https://hnrss.org/frontpage",
        homepage="https://news.ycombinator.com",
        keywords=("hacker news", "hn", "개발", "기술", "스타트업", "프로덕트"),
        reason="기술/제품 키워드가 넓을 때 잘 맞는 공개 피드",
    ),
    CatalogEntry(
        source_label="The Verge",
        feed_url="https://www.theverge.com/rss/index.xml",
        homepage="https://www.theverge.com",
        keywords=("the verge", "consumer tech", "hardware", "mobile", "기기"),
        reason="소비자 기술과 기기 소식에 맞는 공개 피드",
    ),
    CatalogEntry(
        source_label="BBC Business",
        feed_url="https://feeds.bbci.co.uk/news/business/rss.xml",
        homepage="https://www.bbc.com/news/business",
        keywords=("bbc business", "경제", "business", "market", "finance"),
        reason="경제/비즈니스 카테고리에 쓰기 쉬운 공개 피드",
    ),
    CatalogEntry(
        source_label="BBC World",
        feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
        homepage="https://www.bbc.com/news/world",
        keywords=("bbc world", "world", "국제", "사회", "세계"),
        reason="세계/국제 뉴스에 잘 맞는 공개 피드",
    ),
    CatalogEntry(
        source_label="NASA News Release",
        feed_url="https://www.nasa.gov/news-release/feed/",
        homepage="https://www.nasa.gov/news/",
        keywords=("nasa", "space", "science", "우주", "과학"),
        reason="과학/우주 주제에 적합한 공개 피드",
    ),
)


def normalize_hint(value: str) -> str:
    return " ".join(value.lower().split())


def score_catalog_candidate(candidate: CatalogEntry, hint: str) -> int:
    score = 0
    normalized_hint = normalize_hint(hint)
    if candidate.source_label.lower() in normalized_hint:
        score += 8
    if candidate.homepage.lower() in normalized_hint or candidate.feed_url.lower() in normalized_hint:
        score += 10
    for keyword in candidate.keywords:
        if keyword in normalized_hint:
            score += 3
    if normalized_hint and any(part in normalized_hint for part in candidate.source_label.lower().split()):
        score += 2
    return score


def candidate_to_dict(candidate: CatalogEntry, reason: str | None = None) -> dict[str, str]:
    return {
        "source_label": candidate.source_label,
        "feed_url": candidate.feed_url,
        "reason": reason or candidate.reason,
    }


def looks_like_domain_hint(search_hint: str) -> bool:
    hint = search_hint.strip().lower()
    return bool(re.search(r"https?://", hint) or re.search(r"[a-z0-9-]+\.[a-z]{2,}", hint))


def normalize_domain_hint(search_hint: str) -> str:
    hint = search_hint.strip()
    if hint.startswith("http://") or hint.startswith("https://"):
        return hint.rstrip("/")
    if "." in hint:
        return f"https://{hint.strip().strip('/')}"
    return hint


def has_alternate_rel(value) -> bool:
    if isinstance(value, list):
        return any("alternate" in item.lower() for item in value if isinstance(item, str))
    if isinstance(value, str):
        return "alternate" in value.lower()
    return False


def extract_claude_text(data: dict) -> str:
    parts: list[str] = []
    for content in data.get("content", []):
        if content.get("type") == "text" and content.get("text"):
            parts.append(content["text"])
    return "\n".join(parts)


def extract_json_payload(text: str) -> dict[str, object]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON object not found")

    return json.loads(cleaned[start : end + 1])


async def expand_search_hints_with_llm(label: str, search_hint: str) -> list[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    model = os.getenv("ANTHROPIC_NEWSLETTER_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"))
    prompt = f"""
You help discover RSS feeds for newsletter categories.

Return only JSON with this shape:
{{
  "expanded_hints": ["site name", "domain", "keyword phrase"]
}}

Rules:
- Use the user's hint as a filter, not as the target itself.
- Suggest likely publication names, site names, domain names, and search phrases.
- Keep each item short.
- Prefer 3 to 6 items.
- Do not include commentary, markdown, or code fences.

Category label: {label}
Search hint: {search_hint}
""".strip()

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return []

    try:
        data = response.json()
        text = extract_claude_text(data)
        payload = extract_json_payload(text)
    except Exception:
        return []

    expanded = payload.get("expanded_hints", [])
    if not isinstance(expanded, list):
        return []

    results: list[str] = []
    seen = set()
    for item in expanded:
        if not isinstance(item, str):
            continue
        value = normalize_hint(item)
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(item.strip())
    return results[:6]


def collect_seed_candidates(label: str, search_hint: str) -> list[tuple[int, dict[str, str]]]:
    normalized_hint = normalize_hint(f"{label} {search_hint}")

    candidates: list[tuple[int, dict[str, str]]] = []
    for entry in CATALOG:
        score = score_catalog_candidate(entry, normalized_hint)
        if score:
            candidates.append((score, candidate_to_dict(entry)))

    return candidates


async def collect_domain_candidates(search_hint: str) -> list[dict[str, str]]:
    if not looks_like_domain_hint(search_hint):
        return []
    return await discover_from_domain_hint(search_hint)


async def discover_from_domain_hint(search_hint: str) -> list[dict[str, str]]:
    target = normalize_domain_hint(search_hint)
    parsed = urlparse(target)
    if not parsed.netloc:
        return []

    base_url = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    homepage_candidates = [target, base_url]
    feed_candidates = [
        f"{base_url}/feed",
        f"{base_url}/rss",
        f"{base_url}/rss.xml",
        f"{base_url}/feed.xml",
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
    }

    discovered: list[dict[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=headers) as client:
            for homepage in homepage_candidates:
                try:
                    response = await client.get(homepage)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("link", attrs={"rel": has_alternate_rel}):
                    type_value = (link.get("type") or "").lower()
                    href = (link.get("href") or "").strip()
                    title = (link.get("title") or "").strip() or parsed.netloc.replace("www.", "")
                    if not href:
                        continue
                    if "rss" in type_value or "atom" in type_value or "xml" in href.lower():
                        discovered.append(
                            {
                                "source_label": title,
                                "feed_url": urljoin(str(response.url), href),
                                "reason": f"{parsed.netloc} 페이지에서 자동 발견한 RSS/Atom 링크",
                            }
                        )

        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=headers) as client:
            for feed_url in feed_candidates:
                try:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue
                content_type = response.headers.get("content-type", "").lower()
                if "xml" in content_type or "<rss" in response.text.lower() or "<feed" in response.text.lower():
                    discovered.append(
                        {
                            "source_label": parsed.netloc.replace("www.", ""),
                            "feed_url": feed_url,
                            "reason": f"{parsed.netloc}의 관례적 RSS 경로",
                        }
                    )
                    break
    except Exception:
        return []

    deduped: list[dict[str, str]] = []
    seen = set()
    for candidate in discovered:
        key = candidate["feed_url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


async def discover_feed_candidates(label: str, search_hint: str) -> list[dict[str, str]]:
    ranked_candidates = collect_seed_candidates(label, search_hint)
    domain_candidates = await collect_domain_candidates(search_hint)

    def dedupe_ranked(items: list[tuple[int, dict[str, str]]]) -> list[dict[str, str]]:
        items.sort(key=lambda item: (-item[0], item[1]["source_label"]))
        deduped: list[dict[str, str]] = []
        seen = set()
        for _, candidate in items:
            key = candidate["feed_url"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    combined = ranked_candidates + [(9, candidate) for candidate in domain_candidates]
    top_candidates = dedupe_ranked(combined)

    if top_candidates and ranked_candidates and max(score for score, _ in ranked_candidates) >= 5:
        return top_candidates[:8]

    if not top_candidates or (ranked_candidates and max(score for score, _ in ranked_candidates) < 5):
        expanded_hints = await expand_search_hints_with_llm(label, search_hint)
        if expanded_hints:
            llm_ranked: list[tuple[int, dict[str, str]]] = []
            for hint in expanded_hints:
                llm_ranked.extend(collect_seed_candidates(label, hint))
                llm_ranked.extend((9, candidate) for candidate in await collect_domain_candidates(hint))

            top_candidates = dedupe_ranked(combined + llm_ranked)

    return top_candidates[:8]
