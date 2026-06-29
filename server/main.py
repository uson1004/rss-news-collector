from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import socket
import smtplib
from pathlib import Path
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, parsedate_to_datetime
from typing import Optional
from urllib.parse import quote, urlparse, urlunparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, field_validator

from newsletter_discovery import discover_feed_candidates
from newsletter_store import (
    create_category as create_custom_newsletter_category,
    create_subscription,
    deactivate_subscription,
    ensure_categories as ensure_newsletter_categories,
    ensure_schema as ensure_newsletter_schema,
    get_category as get_custom_newsletter_category,
    get_subscription_by_token,
    list_categories as list_custom_newsletter_categories,
    list_category_sources,
    delivery_window_for,
    record_delivery_sent,
)


load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI(title="읽을게 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    ensure_newsletter_schema()
    ensure_newsletter_categories(default_newsletter_categories())


class ParseRequest(BaseModel):
    url: HttpUrl

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: object) -> object:
        return normalize_requested_article_url(value)


class ParsedArticle(BaseModel):
    title: str
    site_name: str
    url: str
    text: str
    paragraphs: list[str]
    excerpt: str
    word_count: int


class SummaryRequest(BaseModel):
    title: str
    text: str


class SummaryResponse(BaseModel):
    summary: list[str]
    model: str


class ArticleInsightRequest(BaseModel):
    title: str
    text: str
    source: str = ""
    category: str = ""


class ArticleInsightResponse(BaseModel):
    why_read: list[str]
    signals: list[str]
    frictions_or_desires: list[str]
    idea_prompts: list[str]
    caveats: list[str]
    model: str


class FollowUpPromptRequest(BaseModel):
    title: str
    summary: list[str]


class FollowUpPromptResponse(BaseModel):
    prompt: str


class TranslateRequest(BaseModel):
    title: str
    text: str
    target_language: str


class TranslateResponse(BaseModel):
    translated_text: str
    paragraphs: list[str]
    model: str
    target_language: str


DEEPL_TARGET_LANGUAGES = {
    "English": "EN",
    "Japanese": "JA",
    "Simplified Chinese": "ZH",
}


class FeedItem(BaseModel):
    title: str
    url: str
    source: str
    category: str
    published: str
    excerpt: str


class FeedResponse(BaseModel):
    category: str
    label: str
    items: list[FeedItem]


class NewsletterDiscoverRequest(BaseModel):
    label: str
    search_hint: str

    @field_validator("label", "search_hint", mode="before")
    @classmethod
    def require_non_blank_text(cls, value: object) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            raise ValueError("카테고리 이름과 검색 힌트를 입력해 주세요.")
        return normalized


class NewsletterCandidate(BaseModel):
    source_label: str
    feed_url: str
    reason: str


class NewsletterCategoryCreateRequest(BaseModel):
    label: str
    search_hint: str
    sources: list[NewsletterCandidate]

    @field_validator("label", "search_hint", mode="before")
    @classmethod
    def require_non_blank_text(cls, value: object) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            raise ValueError("카테고리 이름과 검색 힌트를 입력해 주세요.")
        return normalized

    @field_validator("sources")
    @classmethod
    def require_sources(cls, value: list[NewsletterCandidate]) -> list[NewsletterCandidate]:
        if not value:
            raise ValueError("최소 하나의 RSS 후보를 선택해 주세요.")
        return value


class NewsletterSubscribeRequest(BaseModel):
    email: str
    category_id: str
    cadence: str = "weekly"


class NewsletterSendRequest(BaseModel):
    email: str
    category_id: str


class NewsletterPreviewResponse(BaseModel):
    subject: str
    text_body: str
    html_body: str


KOREAN_GENERAL_FEEDS = [
    "https://www.yna.co.kr/rss/news.xml",
    "https://www.hani.co.kr/rss/",
    "https://rss.donga.com/total.xml",
    "https://www.khan.co.kr/rss/rssdata/total_news.xml",
]

KOREAN_TECH_FEEDS = [
    "https://techblog.woowahan.com/feed/",
    "https://d2.naver.com/d2.atom",
    "https://tech.kakao.com/feed/",
    "https://engineering.linecorp.com/ko/feed/index.html",
]


RSS_FEEDS = {
    "idea_radar": {
        "label": "아이디어 레이더",
        "feeds": [
            "https://www.yna.co.kr/rss/society.xml",
            "https://www.yna.co.kr/rss/economy.xml",
            "https://www.hani.co.kr/rss/",
            "https://www.khan.co.kr/rss/rssdata/total_news.xml",
            "https://rss.donga.com/total.xml",
            *KOREAN_TECH_FEEDS,
        ],
        "keywords": [
            "청년",
            "1인 가구",
            "고령화",
            "돌봄",
            "주거",
            "전세",
            "월세",
            "교육",
            "취업",
            "퇴사",
            "자영업",
            "지역",
            "지방",
            "이주",
            "외국인",
            "소비",
            "구독",
            "중고",
            "배달",
            "플랫폼",
            "커뮤니티",
            "동네",
            "정신건강",
            "외로움",
            "가족",
            "결혼",
            "저출생",
            "반려",
            "기후",
            "안전",
            "AI",
            "스타트업",
        ],
    },
    "geeknews": {
        "label": "긱뉴스",
        "feeds": [
            "https://news.hada.io/rss/news",
            *KOREAN_TECH_FEEDS,
            "https://www.yna.co.kr/rss/industry.xml",
        ],
        "keywords": ["개발", "기술", "스타트업", "AI", "인공지능", "소프트웨어", "서비스"],
    },
    "android": {
        "label": "안드로이드",
        "feeds": [
            "https://developers-kr.googleblog.com/feeds/posts/default?alt=rss",
            "https://android-developers.googleblog.com/feeds/posts/default?alt=rss",
            "https://medium.com/feed/androiddevelopers",
            *KOREAN_TECH_FEEDS,
            "https://www.yna.co.kr/rss/industry.xml",
        ],
        "keywords": ["안드로이드", "Android", "구글", "모바일", "스마트폰", "플레이스토어", "Kotlin", "코틀린"],
    },
    "tech": {
        "label": "IT",
        "feeds": [
            "https://news.hada.io/rss/news",
            *KOREAN_TECH_FEEDS,
            "https://www.yna.co.kr/rss/industry.xml",
            *KOREAN_GENERAL_FEEDS,
        ],
        "keywords": ["IT", "AI", "인공지능", "기술", "개발", "스타트업", "반도체", "플랫폼", "보안", "데이터"],
    },
    "business": {
        "label": "경제",
        "feeds": [
            "https://www.yna.co.kr/rss/economy.xml",
            "https://www.yna.co.kr/rss/industry.xml",
            "https://rss.donga.com/total.xml",
            "https://www.khan.co.kr/rss/rssdata/total_news.xml",
        ],
    },
    "world": {
        "label": "사회/세계",
        "feeds": [
            "https://www.yna.co.kr/rss/society.xml",
            "https://www.yna.co.kr/rss/international.xml",
            "https://www.hani.co.kr/rss/",
            "https://www.khan.co.kr/rss/rssdata/total_news.xml",
        ],
    },
    "science": {
        "label": "과학",
        "feeds": [
            "https://www.yna.co.kr/rss/industry.xml",
            *KOREAN_GENERAL_FEEDS,
        ],
        "keywords": ["과학", "연구", "우주", "기후", "바이오", "의학", "로봇", "기술", "AI"],
    },
    "sports": {
        "label": "스포츠",
        "feeds": [
            "https://www.yna.co.kr/rss/sports.xml",
            "https://rss.donga.com/total.xml",
        ],
        "keywords": ["스포츠", "축구", "야구", "농구", "배구", "골프", "올림픽", "월드컵"],
    },
}


def default_newsletter_categories() -> list[dict[str, str]]:
    return [
        {
            "id": category_id,
            "label": config["label"],
            "search_hint": " ".join(config.get("keywords", [])),
        }
        for category_id, config in RSS_FEEDS.items()
    ]


async def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        validate_public_http_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers=headers,
            event_hooks={"request": [validate_outbound_request]},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        response = exc.response
        content_type = response.headers.get("content-type", "")
        response_text = response.text[:2000] if "text" in content_type else ""

        if response.status_code in {401, 403} and (
            "cloudflare" in response_text.lower() or "just a moment" in response_text.lower()
        ):
            raise HTTPException(
                status_code=502,
                detail="이 사이트는 봇 접근을 차단하고 있어 본문을 가져올 수 없어요. 다른 기사 URL을 시도해 주세요.",
            ) from exc

        if response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail="이 사이트가 자동 접근을 막아 본문을 가져오지 못했어요. 다른 기사 URL을 시도해 주세요.",
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="페이지를 가져오지 못했어요. URL을 확인하거나 다른 페이지를 시도해 주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="페이지를 가져오지 못했어요. URL을 확인하거나 다른 페이지를 시도해 주세요.",
        ) from exc

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="HTML 페이지가 아니어서 본문을 추출할 수 없어요.",
        )

    return response.text


async def collect_feed_items(category: str, limit: int = 12) -> FeedResponse:
    feed_config = RSS_FEEDS.get(category)
    if feed_config:
        return await collect_feed_items_from_urls(
            category,
            feed_config["label"],
            feed_config["feeds"],
            limit,
            feed_config.get("keywords", []),
        )

    custom_category = get_custom_newsletter_category(category)
    if custom_category:
        sources = list_category_sources(category)
        return await collect_feed_items_from_urls(
            category,
            custom_category["label"],
            [source["feed_url"] for source in sources],
            limit,
        )

    raise HTTPException(status_code=404, detail="지원하지 않는 카테고리예요.")


async def collect_feed_items_from_urls(
    category: str,
    label: str,
    feed_urls: list[str],
    limit: int = 12,
    keywords: list[str] | None = None,
) -> FeedResponse:
    items: list[FeedItem] = []
    seen_urls: set[str] = set()
    for feed_url in feed_urls:
        try:
            xml = await fetch_feed_xml(feed_url)
        except HTTPException:
            continue
        items.extend(parse_feed_items(xml, category, label, seen_urls, keywords or []))
        if len(items) >= limit:
            break

    if not items:
        raise HTTPException(status_code=404, detail="카테고리에서 읽을 글을 찾지 못했어요.")

    items.sort(key=feed_item_sort_timestamp, reverse=True)
    return FeedResponse(category=category, label=label, items=items[:limit])


def feed_item_sort_timestamp(item: FeedItem) -> float:
    if not item.published:
        return 0
    try:
        parsed = parsedate_to_datetime(item.published)
    except (TypeError, ValueError):
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def feed_item_matches_keywords(title: str, excerpt: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {excerpt}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def parse_feed_items(xml: str, category: str, label: str, seen_urls: set[str], keywords: list[str]) -> list[FeedItem]:
    soup = BeautifulSoup(xml, "xml")
    feed_title = first_text(
        soup.find("channel").find("title").get_text(" ", strip=True)
        if soup.find("channel") and soup.find("channel").find("title")
        else "",
        soup.find("feed").find("title").get_text(" ", strip=True)
        if soup.find("feed") and soup.find("feed").find("title")
        else "",
        label,
    )
    parsed_items: list[FeedItem] = []

    for node in soup.find_all(["item", "entry"]):
        title_node = node.find("title")
        title = normalize_paragraph(title_node.get_text(" ", strip=True) if title_node else "")
        url = feed_item_link(node)
        if not title or not url or url in seen_urls:
            continue

        seen_urls.add(url)
        published = first_text(
            node.find("pubDate").get_text(" ", strip=True) if node.find("pubDate") else "",
            node.find("published").get_text(" ", strip=True) if node.find("published") else "",
            node.find("updated").get_text(" ", strip=True) if node.find("updated") else "",
        )
        excerpt = first_text(
            strip_markup(node.find("description").get_text(" ", strip=True))
            if node.find("description")
            else "",
            strip_markup(node.find("summary").get_text(" ", strip=True)) if node.find("summary") else "",
            strip_markup(node.find("content").get_text(" ", strip=True)) if node.find("content") else "",
        )
        if not feed_item_matches_keywords(title, excerpt, keywords):
            continue

        item_source = first_text(
            node.find("source").get_text(" ", strip=True) if node.find("source") else "",
            feed_title,
        )

        parsed_items.append(
            FeedItem(
                title=title,
                url=url,
                source=item_source,
                category=category,
                published=published,
                excerpt=excerpt[:220],
            )
        )

    return parsed_items


def feed_item_link(node: BeautifulSoup) -> str:
    link_nodes = node.find_all("link")
    for link_node in link_nodes:
        href = link_node.get("href", "").strip()
        rel = " ".join(link_node.get("rel", []) if isinstance(link_node.get("rel"), list) else [link_node.get("rel", "")])
        link_type = link_node.get("type", "")
        normalized_href = normalize_feed_item_link(href)
        if normalized_href and ("alternate" in rel.lower() or link_type.startswith("text/html")):
            return normalized_href

    link_node = link_nodes[0] if link_nodes else None
    if not link_node:
        return ""

    href = link_node.get("href")
    if href:
        return normalize_feed_item_link(href)
    return normalize_feed_item_link(link_node.get_text(" ", strip=True))


def normalize_feed_item_link(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return candidate


def strip_markup(value: str) -> str:
    return normalize_paragraph(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


async def create_claude_summary(title: str, text: str) -> SummaryResponse:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY가 설정되어 있지 않아 AI 요약을 사용할 수 없어요.",
        )

    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    clipped_text = text[:12000]
    prompt = f"""
다음 글을 한국어로 3~5개의 짧은 bullet로 요약해 주세요.

규칙:
- 원문의 의미를 바꾸거나 쉬운말로 다시 쓰지 마세요.
- 핵심 주장과 중요한 사실만 압축하세요.
- 각 bullet은 한 문장으로 작성하세요.
- bullet 기호 없이 줄바꿈으로만 구분하세요.

제목: {title}

본문:
{clipped_text}
""".strip()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 700,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 요약 요청이 실패했어요. API 키, 모델명, 사용량 제한을 확인해 주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 요약 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from exc

    data = response.json()
    output_text = extract_claude_text(data)

    bullets = [
        line.strip().lstrip("-•*0123456789. ").strip()
        for line in output_text.splitlines()
        if line.strip()
    ]
    bullets = [line for line in bullets if line][:5]
    if not bullets:
        raise HTTPException(status_code=502, detail="AI 요약 결과를 읽지 못했어요.")

    return SummaryResponse(summary=bullets, model=model)


def clean_insight_items(value: object, limit: int = 3) -> list[str]:
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = [str(item) for item in value if str(item).strip()]
    else:
        raw_items = []

    cleaned: list[str] = []
    for item in raw_items:
        normalized = " ".join(item.split()).strip().lstrip("-•*0123456789. ").strip()
        if normalized:
            cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def extract_json_object(text: str) -> dict[str, object]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise HTTPException(status_code=502, detail="AI 관찰 노트 결과를 JSON으로 읽지 못했어요.")
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="AI 관찰 노트 결과를 JSON으로 읽지 못했어요.") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="AI 관찰 노트 결과 형식이 올바르지 않아요.")
    return parsed


def parse_article_insight_output(output_text: str, model: str) -> ArticleInsightResponse:
    data = extract_json_object(output_text)
    response = ArticleInsightResponse(
        why_read=clean_insight_items(data.get("why_read"), 2),
        signals=clean_insight_items(data.get("signals"), 2),
        frictions_or_desires=clean_insight_items(data.get("frictions_or_desires"), 2),
        idea_prompts=clean_insight_items(data.get("idea_prompts"), 3),
        caveats=clean_insight_items(data.get("caveats"), 2),
        model=model,
    )
    if not any([response.why_read, response.signals, response.frictions_or_desires, response.idea_prompts]):
        response.caveats = response.caveats or ["이 글에서는 뚜렷한 아이디어 신호를 찾기 어려워요."]
    return response


async def create_claude_article_insight(
    title: str,
    text: str,
    source: str = "",
    category: str = "",
) -> ArticleInsightResponse:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY가 설정되어 있지 않아 AI 관찰 노트를 사용할 수 없어요.",
        )

    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    clipped_text = text[:12000]
    prompt = f"""
다음 기사를 원문을 대체하지 않는 'AI 관찰 노트'로 분석해 주세요.

목표:
- 사용자가 이 글을 읽을지 빠르게 판단하게 돕기
- 기사 안에서 보이는 생활 변화, 불편, 욕망, 제도와 현실의 간극, 아이디어 힌트를 찾기
- 사실과 해석을 구분하고, 기사에 없는 내용을 단정하지 않기

규칙:
- 반드시 JSON 객체만 출력하세요.
- 모든 항목은 한국어로 짧게 작성하세요.
- 기사에 근거가 약하면 caveats에 낮은 신호라고 말하고 아이디어를 억지로 만들지 마세요.
- 원문 제목, 출처, 링크를 대체하는 문구를 만들지 마세요.
- "가능성", "신호", "힌트"처럼 조심스러운 표현을 사용하세요.

JSON 형식:
{{
  "why_read": ["왜 볼 만한가 1", "왜 볼 만한가 2"],
  "signals": ["보이는 변화 1", "보이는 변화 2"],
  "frictions_or_desires": ["불편/욕망 1", "불편/욕망 2"],
  "idea_prompts": ["아이디어 힌트 1", "아이디어 힌트 2", "아이디어 힌트 3"],
  "caveats": ["주의할 점 또는 낮은 신호"]
}}

제목: {title}
출처: {source or "알 수 없음"}
카테고리: {category or "일반"}

본문:
{clipped_text}
""".strip()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 900,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 관찰 노트 요청이 실패했어요. API 키, 모델명, 사용량 제한을 확인해 주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 관찰 노트 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from exc

    return parse_article_insight_output(extract_claude_text(response.json()), model)


def create_follow_up_prompt(title: str, summary: list[str]) -> FollowUpPromptResponse:
    clean_summary = [" ".join(item.split()) for item in summary if item and item.strip()]
    clean_summary = clean_summary[:5]
    if not clean_summary:
        raise HTTPException(status_code=422, detail="질문 프롬프트를 만들 요약이 없어요.")

    summary_text = "\n".join(f"- {item}" for item in clean_summary)
    prompt = f"""
아래 기사 요약을 바탕으로, 사용자가 내용을 더 오래 기억할 수 있도록 질문 리스트를 만들어줘.

목표:
- 사용자가 핵심 내용을 다시 떠올리게 만들기
- 요약에서 출발해 원인, 영향, 반론, 이해관계까지 생각하게 만들기
- 단순 확인보다 자기 말로 설명하고 관점을 비교하도록 돕기

질문 구성:
1. 요약에 명시된 핵심 사실을 확인하는 질문 2개
2. 요약에서 자연스럽게 이어지는 원인, 영향, 반론, 이해관계 질문 3개

규칙:
- 총 5개 질문만 만들어줘.
- 질문만 번호 목록으로 출력해줘.
- 요약과 너무 멀리 떨어진 외부 조사 질문은 만들지 마.
- 요약에 없는 내용을 사실처럼 단정하지 말고, 필요하면 "어떤 가능성이 있을까?"처럼 질문형으로 표현해줘.
- 사용자가 답을 떠올리며 내용을 기억할 수 있게 구체적으로 질문해줘.

제목: {title}

요약:
{summary_text}
""".strip()

    return FollowUpPromptResponse(prompt=prompt)


def clean_translation_output(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned_lines: list[str] = []

    for index, line in enumerate(lines):
        if not line:
            cleaned_lines.append("")
            continue

        normalized = line.strip("* ").lower()
        if index <= 2 and (
            normalized.startswith("title:")
            or normalized.startswith("제목:")
            or normalized.startswith("body:")
            or normalized.startswith("본문:")
        ):
            continue

        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines).strip()
    while "\n\n\n" in cleaned_text:
        cleaned_text = cleaned_text.replace("\n\n\n", "\n\n")
    return cleaned_text


def normalize_article_url(url: str) -> str:
    parsed = urlparse(url)
    normalized_path = parsed.path.rstrip("/") or "/"
    normalized_netloc = parsed.netloc.lower().replace("www.", "")
    return urlunparse((parsed.scheme.lower(), normalized_netloc, normalized_path, "", "", ""))


def normalize_requested_article_url(value: object) -> object:
    if not isinstance(value, str):
        return value

    normalized = " ".join(value.split()).strip()
    if not normalized:
        return normalized

    parsed = urlparse(normalized)
    if not parsed.scheme:
        normalized = f"https://{normalized}"
        parsed = urlparse(normalized)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("유효한 기사 URL을 입력해 주세요.")

    return normalized


def validate_public_http_url(url: str, resolver=socket.getaddrinfo) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise ValueError("유효한 HTTP URL을 입력해 주세요.")
    if parsed.username or parsed.password:
        raise ValueError("사용자 정보가 포함된 URL은 사용할 수 없어요.")

    normalized_hostname = hostname.rstrip(".").lower()
    if normalized_hostname == "localhost" or normalized_hostname.endswith((".localhost", ".local")):
        raise ValueError("내부 네트워크 주소는 사용할 수 없어요.")

    if (
        parsed.path == "/demo/article"
        and normalized_hostname in {"127.0.0.1", "::1"}
        and (parsed.port or 80) == 8000
    ):
        return url

    try:
        literal_ip = ipaddress.ip_address(normalized_hostname)
        addresses = [literal_ip]
    except ValueError:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        try:
            resolved = resolver(normalized_hostname, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("URL의 호스트를 확인할 수 없어요.") from exc
        addresses = []
        for result in resolved:
            socket_address = result[4]
            if socket_address:
                addresses.append(ipaddress.ip_address(socket_address[0]))

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("내부 네트워크 주소는 사용할 수 없어요.")
    return url


async def validate_outbound_request(request: httpx.Request) -> None:
    try:
        await asyncio.to_thread(validate_public_http_url, str(request.url))
    except ValueError as exc:
        raise httpx.InvalidURL(str(exc)) from exc


def extract_article_id(url: str) -> str:
    match = re.search(r"-([0-9a-f]{12})$", urlparse(url).path.rstrip("/"), flags=re.IGNORECASE)
    return match.group(1).lower() if match else ""


def discover_feed_urls(article_url: str) -> list[str]:
    parsed = urlparse(article_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{base_url}/feed",
        f"{base_url}/rss",
        f"{base_url}/rss.xml",
        f"{base_url}/feed.xml",
    ]

    if parsed.netloc.lower().endswith("medium.com") and parsed.path.strip("/"):
        candidates.insert(0, f"{base_url}/feed{parsed.path.rstrip('/')}")

    if "googleblog.com" in parsed.netloc.lower() or "blogspot." in parsed.netloc.lower():
        candidates.insert(0, f"{base_url}/feeds/posts/default?alt=rss")

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


async def fetch_feed_xml(feed_url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    }

    try:
        validate_public_http_url(feed_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers=headers,
            event_hooks={"request": [validate_outbound_request]},
        ) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=404, detail="공식 RSS 피드를 찾지 못했어요.") from exc

    return response.text


def feed_text(tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def extract_feed_item_html(item) -> str:
    encoded = item.find("encoded")
    if encoded and encoded.get_text(strip=True):
        return encoded.get_text()

    content = item.find("content")
    if content and content.get_text(strip=True):
        return content.get_text()

    description = item.find("description")
    if description and description.get_text(strip=True):
        return description.get_text()

    summary = item.find("summary")
    if summary and summary.get_text(strip=True):
        return summary.get_text()

    return ""


def clean_feed_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("img, script, style, iframe"):
        node.decompose()

    for paragraph in soup.find_all("p"):
        normalized = normalize_paragraph(paragraph.get_text(" ", strip=True))
        if normalized.startswith("Originally published in ") or " was originally published in " in normalized:
            paragraph.decompose()
        elif normalized.startswith("This post appeared first on "):
            paragraph.decompose()

    return str(soup)


def build_article_from_feed_item(item, article_url: str, feed_title: str) -> ParsedArticle:
    content_html = clean_feed_html(extract_feed_item_html(item))
    if not content_html.strip():
        raise HTTPException(status_code=404, detail="RSS에서 본문을 찾지 못했어요.")

    soup = BeautifulSoup(content_html, "html.parser")
    paragraphs = [normalize_paragraph(node.get_text(" ", strip=True)) for node in soup.find_all("p")]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]

    if not paragraphs:
        fallback_text_content = normalize_paragraph(soup.get_text(" ", strip=True))
        paragraphs = [fallback_text_content] if fallback_text_content else []

    text = "\n\n".join(paragraphs)
    if len(text) < 120:
        raise HTTPException(status_code=404, detail="RSS 본문이 너무 짧아 사용할 수 없어요.")

    title = feed_text(item.find("title")) or "제목 없음"
    description = feed_text(item.find("description"))
    site_name = feed_title.replace(" - Medium", "").strip() or urlparse(article_url).netloc.replace("www.", "")
    excerpt = description or " ".join(text[:180].split())

    return ParsedArticle(
        title=title,
        site_name=site_name,
        url=article_url,
        text=text,
        paragraphs=paragraphs,
        excerpt=excerpt,
        word_count=len(text.split()),
    )


def find_matching_feed_item(feed_xml: str, article_url: str):
    soup = BeautifulSoup(feed_xml, "xml")
    normalized_url = normalize_article_url(article_url)
    article_id = extract_article_id(article_url)

    channel = soup.find("channel")
    feed_title = feed_text(channel.find("title") if channel else None)
    if not feed_title and soup.find("feed"):
        feed_title = feed_text(soup.find("feed").find("title"))

    for item in soup.find_all(["item", "entry"]):
        link = feed_item_link(item)
        guid = feed_text(item.find("guid"))
        entry_id = feed_text(item.find("id"))
        candidates = [candidate for candidate in [link, guid, entry_id] if candidate]
        normalized_candidates = {normalize_article_url(candidate) for candidate in candidates}

        if normalized_url in normalized_candidates:
            return item, feed_title

        if article_id and any(article_id == extract_article_id(candidate) for candidate in candidates):
            return item, feed_title

    raise HTTPException(status_code=404, detail="RSS에서 해당 글을 찾지 못했어요.")


async def resolve_article_from_rss(article_url: str) -> ParsedArticle:
    for feed_url in discover_feed_urls(article_url):
        try:
            feed_xml = await fetch_feed_xml(feed_url)
            item, feed_title = find_matching_feed_item(feed_xml, article_url)
            return build_article_from_feed_item(item, article_url, feed_title)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise

    raise HTTPException(
        status_code=404,
        detail="공식 RSS에서도 해당 글을 찾지 못했어요. 최근 RSS 범위를 벗어났거나 공개 본문이 아닐 수 있어요.",
    )


async def create_claude_translation(title: str, text: str, target_language: str) -> TranslateResponse:
    api_key = os.getenv("DEEPL_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="DEEPL_API_KEY가 설정되어 있지 않아 번역 기능을 사용할 수 없어요.",
        )

    clean_target = " ".join(target_language.split()).strip()
    target_language_code = DEEPL_TARGET_LANGUAGES.get(clean_target)
    if not target_language_code:
        raise HTTPException(status_code=422, detail="지원하지 않는 번역 언어예요.")

    clipped_text = text[:12000]
    paragraphs = [paragraph.strip() for paragraph in clipped_text.split("\n\n") if paragraph.strip()]
    text_chunks = paragraphs if paragraphs else [clipped_text]
    api_url = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"DeepL-Auth-Key {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text_chunks,
                    "target_lang": target_language_code,
                    "context": title,
                    "preserve_formatting": True,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail="DeepL 번역 요청이 실패했어요. API 키와 사용량 제한을 확인해 주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="DeepL 번역 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from exc

    data = response.json()
    translations = data.get("translations", [])
    translated_parts = [item.get("text", "").strip() for item in translations if item.get("text")]
    translated_text = clean_translation_output("\n\n".join(translated_parts).strip())
    if not translated_text:
        raise HTTPException(status_code=502, detail="번역 결과를 읽지 못했어요.")

    paragraphs = [part.strip() for part in translated_text.split("\n\n") if part.strip()]
    return TranslateResponse(
        translated_text=translated_text,
        paragraphs=paragraphs,
        model="deepl-api-free",
        target_language=clean_target,
    )


def extract_claude_text(data: dict) -> str:
    parts: list[str] = []
    for content in data.get("content", []):
        if content.get("type") == "text" and content.get("text"):
            parts.append(content["text"])
    return "\n".join(parts)


def first_text(*values: Optional[str]) -> str:
    for value in values:
        if value and value.strip():
            return " ".join(value.split())
    return ""


def normalize_paragraph(value: str) -> str:
    return " ".join(value.split())


def paragraphs_from_text(text: str) -> list[str]:
    return [normalize_paragraph(part) for part in text.splitlines() if normalize_paragraph(part)]


def metadata_from_html(html: str, url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(url)

    title = first_text(
        tag_content(soup, 'meta[property="og:title"]'),
        tag_content(soup, 'meta[name="twitter:title"]'),
        soup.title.string if soup.title else "",
    )
    site_name = first_text(
        tag_content(soup, 'meta[property="og:site_name"]'),
        parsed_url.netloc.replace("www.", ""),
    )
    excerpt = first_text(
        tag_content(soup, 'meta[property="og:description"]'),
        tag_content(soup, 'meta[name="description"]'),
    )

    return {"title": title, "site_name": site_name, "excerpt": excerpt}


def tag_content(soup: BeautifulSoup, selector: str) -> str:
    tag = soup.select_one(selector)
    return tag.get("content", "") if tag else ""


def fallback_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ["script", "style", "noscript", "iframe", "nav", "footer", "aside", "form"]:
        for node in soup.select(selector):
            node.decompose()

    candidates = []
    for selector in ["article", "main", '[role="main"]']:
        node = soup.select_one(selector)
        if node:
            text = "\n\n".join(p.get_text(" ", strip=True) for p in node.find_all("p"))
            if len(text) > 300:
                candidates.append(text)

    paragraph_text = "\n\n".join(
        p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40
    )
    if paragraph_text:
        candidates.append(paragraph_text)

    return max(candidates, key=len, default="")


def extract_paragraphs(html: str, url: str) -> list[str]:
    extracted_xml = trafilatura.extract(
        html,
        url=url,
        output_format="xml",
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if extracted_xml:
        soup = BeautifulSoup(extracted_xml, "xml")
        paragraphs = [normalize_paragraph(node.get_text(" ", strip=True)) for node in soup.find_all("p")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        if paragraphs:
            return paragraphs

    extracted_text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if extracted_text:
        paragraphs = paragraphs_from_text(extracted_text)
        if paragraphs:
            return paragraphs

    fallback = fallback_text(html)
    return paragraphs_from_text(fallback)


def parse_article(html: str, url: str) -> ParsedArticle:
    metadata = metadata_from_html(html, url)
    paragraphs = extract_paragraphs(html, url)
    text = "\n\n".join(paragraphs)
    if len(text) < 200:
        raise HTTPException(
            status_code=422,
            detail="본문을 충분히 추출하지 못했어요. 기사나 블로그 본문 URL을 입력해 주세요.",
        )

    title = metadata["title"] or "제목 없음"
    excerpt = metadata["excerpt"] or " ".join(text[:180].split())

    return ParsedArticle(
        title=title,
        site_name=metadata["site_name"],
        url=url,
        text=text,
        paragraphs=paragraphs,
        excerpt=excerpt,
        word_count=len(text.split()),
    )


async def resolve_article(url: str) -> ParsedArticle:
    parse_error: HTTPException | None = None

    try:
        html = await fetch_html(url)
        return parse_article(html, url)
    except HTTPException as exc:
        parse_error = exc
        if exc.status_code not in {415, 422, 502}:
            raise

    try:
        return await resolve_article_from_rss(url)
    except HTTPException as rss_exc:
        if parse_error and parse_error.status_code == 502 and "차단" in parse_error.detail and rss_exc.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="이 사이트는 기사 페이지 접근을 차단했고, 공식 RSS에서도 해당 글을 찾지 못했어요. 최근 RSS 범위를 벗어났거나 공개 본문이 아닐 수 있어요.",
            ) from rss_exc
        if parse_error:
            raise parse_error
        raise rss_exc


def normalize_email_address(email: str) -> str:
    normalized = " ".join(email.split()).strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=422, detail="이메일 주소를 확인해 주세요.")
    local_part, _, domain = normalized.partition("@")
    if not local_part or "." not in domain:
        raise HTTPException(status_code=422, detail="이메일 주소를 확인해 주세요.")
    return normalized


def list_api_categories() -> list[dict[str, str]]:
    categories = [{"id": key, "label": value["label"]} for key, value in RSS_FEEDS.items()]
    categories.extend(
        {"id": category["id"], "label": category["label"]}
        for category in list_custom_newsletter_categories()
    )

    deduped: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for category in categories:
        if category["id"] in seen_ids:
            continue
        seen_ids.add(category["id"])
        deduped.append(category)
    return deduped


def get_category_label(category_id: str) -> str:
    feed_config = RSS_FEEDS.get(category_id)
    if feed_config:
        return feed_config["label"]

    custom_category = get_custom_newsletter_category(category_id)
    if custom_category:
        return custom_category["label"]

    raise HTTPException(status_code=404, detail="지원하지 않는 카테고리예요.")


async def build_newsletter_digest(category_id: str, limit: int = 3) -> NewsletterPreviewResponse:
    feed_response = await collect_feed_items(category_id, limit=limit)
    digest_items: list[dict[str, object]] = []

    for item in feed_response.items[:limit]:
        item_summary: list[str] = []
        article: ParsedArticle | None = None

        try:
            article = await resolve_article(item.url)
        except HTTPException:
            article = None

        if article and len(article.text.strip()) >= 200:
            try:
                summary_response = await create_claude_summary(article.title, article.text)
                item_summary = summary_response.summary[:3]
            except HTTPException:
                item_summary = []

        digest_items.append(
            {
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "excerpt": article.excerpt if article and article.excerpt else item.excerpt,
                "summary": item_summary,
            }
        )

    subject = f"[읽을게] {feed_response.label} 뉴스레터"
    text_body = render_newsletter_text(feed_response.label, digest_items)
    html_body = render_newsletter_html(feed_response.label, digest_items)
    return NewsletterPreviewResponse(subject=subject, text_body=text_body, html_body=html_body)


def render_newsletter_text(label: str, items: list[dict[str, object]]) -> str:
    lines = [f"{label} 뉴스레터", ""]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item['title']}")
        lines.append(f"출처: {item['source']}")
        lines.append(f"링크: {item['url']}")
        excerpt = str(item.get("excerpt", "")).strip()
        if excerpt:
            lines.append(f"요약: {excerpt}")
        summary = [str(line).strip() for line in item.get("summary", []) if str(line).strip()]
        for bullet in summary:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.append("읽을게")
    return "\n".join(lines).strip()


def render_newsletter_html(label: str, items: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for item in items:
        summary = "".join(
            f"<li>{escape_html(str(line).strip())}</li>"
            for line in item.get("summary", [])
            if str(line).strip()
        )
        excerpt = escape_html(str(item.get("excerpt", "")).strip())
        blocks.append(
            f"""
            <article style="margin:0 0 24px;padding:16px;border:1px solid #ddd;border-radius:12px;">
              <p style="margin:0 0 6px;color:#2563eb;font-weight:700;">{escape_html(str(item['source']))}</p>
              <h2 style="margin:0 0 8px;font-size:20px;line-height:1.3;">
                <a href="{escape_html(str(item['url']))}" style="color:#111827;text-decoration:none;">{escape_html(str(item['title']))}</a>
              </h2>
              {f'<p style="margin:0 0 10px;color:#374151;">{excerpt}</p>' if excerpt else ''}
              {f'<ul style="margin:0;padding-left:18px;color:#111827;">{summary}</ul>' if summary else ''}
            </article>
            """
        )

    return f"""
    <!doctype html>
    <html lang="ko">
      <body style="margin:0;padding:24px;background:#f6f5f1;font-family:Inter,Arial,sans-serif;color:#111827;">
        <main style="max-width:760px;margin:0 auto;background:#ffffff;padding:24px;border-radius:16px;">
          <p style="margin:0 0 8px;color:#2563eb;font-weight:800;letter-spacing:0.04em;">읽을게</p>
          <h1 style="margin:0 0 20px;font-size:28px;line-height:1.2;">{escape_html(label)} 뉴스레터</h1>
          {''.join(blocks)}
        </main>
      </body>
    </html>
    """


def personalize_newsletter_digest(
    digest: NewsletterPreviewResponse,
    unsubscribe_token: str,
) -> NewsletterPreviewResponse:
    token = unsubscribe_token.strip()
    if not token:
        return digest

    public_base_url = os.getenv("NEWSLETTER_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    unsubscribe_url = f"{public_base_url}/api/newsletter/unsubscribe?token={quote(token, safe='')}"
    text_body = f"{digest.text_body.rstrip()}\n\n구독 해지: {unsubscribe_url}"
    unsubscribe_footer = (
        '<p style="margin:24px 0 0;color:#6b7280;font-size:13px;">'
        f'<a href="{escape_html(unsubscribe_url)}" style="color:#6b7280;">뉴스레터 구독 해지</a>'
        "</p>"
    )
    if "</main>" in digest.html_body:
        html_body = digest.html_body.replace("</main>", f"{unsubscribe_footer}</main>", 1)
    else:
        html_body = f"{digest.html_body}{unsubscribe_footer}"
    return NewsletterPreviewResponse(
        subject=digest.subject,
        text_body=text_body,
        html_body=html_body,
    )


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def send_newsletter_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    smtp_host = os.getenv("NEWSLETTER_SMTP_HOST") or os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("NEWSLETTER_SMTP_PORT") or os.getenv("SMTP_PORT") or "587")
    smtp_username = os.getenv("NEWSLETTER_SMTP_USERNAME") or os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("NEWSLETTER_SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("NEWSLETTER_FROM_EMAIL") or os.getenv("SMTP_FROM_EMAIL")
    from_name = os.getenv("NEWSLETTER_FROM_NAME", "읽을게")
    use_starttls = (os.getenv("NEWSLETTER_SMTP_STARTTLS") or os.getenv("SMTP_STARTTLS") or "true").lower() != "false"

    if not smtp_host or not from_email:
        raise HTTPException(
            status_code=503,
            detail="뉴스레터 발송용 SMTP 설정이 없어 이메일을 보낼 수 없어요.",
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        if use_starttls:
            smtp.starttls()
        if smtp_username and smtp_password:
            smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


async def send_category_newsletter(
    category_id: str,
    email: str,
    unsubscribe_token: str = "",
) -> NewsletterPreviewResponse:
    digest = await build_newsletter_digest(category_id)
    digest = personalize_newsletter_digest(digest, unsubscribe_token)
    await asyncio.to_thread(send_newsletter_email, email, digest.subject, digest.text_body, digest.html_body)
    return digest


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
async def categories() -> list[dict[str, str]]:
    return list_api_categories()


@app.get("/api/newsletter/categories")
async def newsletter_categories() -> list[dict[str, str]]:
    return list_api_categories()


@app.post("/api/newsletter/discover", response_model=list[NewsletterCandidate])
async def newsletter_discover(request: NewsletterDiscoverRequest) -> list[NewsletterCandidate]:
    candidates = await discover_feed_candidates(request.label, request.search_hint)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="검색 힌트로 RSS 후보를 찾지 못했어요. 블로그 이름, 사이트 이름, 도메인을 조금 더 구체적으로 적어 주세요.",
        )
    return [NewsletterCandidate(**candidate) for candidate in candidates]


@app.post("/api/newsletter/categories", response_model=dict[str, object])
async def newsletter_create_category(request: NewsletterCategoryCreateRequest) -> dict[str, object]:
    if not request.label.strip():
        raise HTTPException(status_code=422, detail="카테고리 이름을 입력해 주세요.")
    if not request.sources:
        raise HTTPException(status_code=422, detail="최소 하나의 RSS 후보를 선택해 주세요.")

    category = create_custom_newsletter_category(
        request.label,
        request.search_hint,
        [source.model_dump() for source in request.sources],
    )
    return category


@app.get("/api/feeds/{category}", response_model=FeedResponse)
async def feed(category: str) -> FeedResponse:
    return await collect_feed_items(category)


@app.post("/api/parse", response_model=ParsedArticle)
async def parse(request: ParseRequest) -> ParsedArticle:
    url = str(request.url)
    return await resolve_article(url)


@app.post("/api/summarize", response_model=SummaryResponse)
async def summarize(request: SummaryRequest) -> SummaryResponse:
    if len(request.text.strip()) < 200:
        raise HTTPException(status_code=422, detail="요약할 본문이 너무 짧아요.")
    return await create_claude_summary(request.title, request.text)


@app.post("/api/article-insight", response_model=ArticleInsightResponse)
async def article_insight(request: ArticleInsightRequest) -> ArticleInsightResponse:
    if len(request.text.strip()) < 200:
        raise HTTPException(status_code=422, detail="관찰 노트를 만들 본문이 너무 짧아요.")
    return await create_claude_article_insight(request.title, request.text, request.source, request.category)


@app.post("/api/follow-up-prompt", response_model=FollowUpPromptResponse)
async def follow_up_prompt(request: FollowUpPromptRequest) -> FollowUpPromptResponse:
    return create_follow_up_prompt(request.title, request.summary)


@app.post("/api/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest) -> TranslateResponse:
    if len(request.text.strip()) < 80:
        raise HTTPException(status_code=422, detail="번역할 본문이 너무 짧아요.")
    return await create_claude_translation(request.title, request.text, request.target_language)


@app.post("/api/newsletter/subscribe", response_model=dict[str, str])
async def newsletter_subscribe(request: NewsletterSubscribeRequest) -> dict[str, str]:
    email = normalize_email_address(request.email)
    cadence = request.cadence.strip().lower() or "weekly"
    if cadence not in {"weekly"}:
        raise HTTPException(status_code=422, detail="현재는 weekly 구독만 지원해요.")

    category_label = get_category_label(request.category_id)
    subscription = create_subscription(email, request.category_id, cadence)

    try:
        digest = await send_category_newsletter(
            request.category_id,
            email,
            subscription["unsubscribe_token"],
        )
        sent_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record_delivery_sent(
            subscription["id"],
            request.category_id,
            delivery_window_for(sent_at),
            sent_at,
        )
        return {
            "id": subscription["id"],
            "message": f"{category_label} 뉴스레터 구독이 완료됐어요. 첫 메일을 보냈어요.",
            "subject": digest.subject,
        }
    except HTTPException as exc:
        if exc.status_code == 503:
            return {
                "id": subscription["id"],
                "message": f"{category_label} 뉴스레터 구독은 완료됐지만 메일 발송 설정이 없어 첫 메일은 보낼 수 없어요.",
            }
        raise
    except Exception:
        return {
            "id": subscription["id"],
            "message": f"{category_label} 뉴스레터 구독은 완료됐지만 첫 메일 발송에는 실패했어요.",
        }


@app.post("/api/newsletter/unsubscribe", response_model=dict[str, str])
async def newsletter_unsubscribe(request: dict[str, str]) -> dict[str, str]:
    token = request.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=422, detail="해지 토큰이 필요해요.")
    subscription = get_subscription_by_token(token)
    if not subscription:
        raise HTTPException(status_code=404, detail="구독 정보를 찾지 못했어요.")
    if subscription["status"] != "active":
        return {"status": "ok", "message": "이미 해지된 뉴스레터 구독이에요."}
    if not deactivate_subscription(token):
        raise HTTPException(status_code=500, detail="구독 해지에 실패했어요.")
    return {"status": "ok", "message": "뉴스레터 구독을 해지했어요."}


@app.get("/api/newsletter/unsubscribe", response_class=HTMLResponse)
async def newsletter_unsubscribe_page(token: str) -> HTMLResponse:
    clean_token = token.strip()
    subscription = get_subscription_by_token(clean_token)
    if not clean_token or not subscription:
        return HTMLResponse(
            "<!doctype html><html lang=\"ko\"><body><h1>구독 정보를 찾지 못했어요.</h1></body></html>",
            status_code=404,
        )
    if subscription["status"] != "active":
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="ko">
              <head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
              <body style="margin:0;padding:48px 20px;background:#efebe1;color:#201b16;font-family:system-ui,sans-serif;">
                <main style="max-width:640px;margin:0 auto;padding:32px;background:#fffdf7;border:1px solid #d8ccba;">
                  <p style="color:#9d2f23;font-weight:800;">읽을게</p>
                  <h1>이미 해지된 구독이에요.</h1>
                  <p>이 카테고리의 정기 메일은 다시 보내지 않습니다.</p>
                </main>
              </body>
            </html>
            """
        )
    deactivate_subscription(clean_token)
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="ko">
          <head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
          <body style="margin:0;padding:48px 20px;background:#efebe1;color:#201b16;font-family:system-ui,sans-serif;">
            <main style="max-width:640px;margin:0 auto;padding:32px;background:#fffdf7;border:1px solid #d8ccba;">
              <p style="color:#9d2f23;font-weight:800;">읽을게</p>
              <h1>뉴스레터 구독을 해지했어요.</h1>
              <p>앞으로 이 카테고리의 정기 메일을 보내지 않습니다.</p>
            </main>
          </body>
        </html>
        """
    )


@app.post("/api/newsletter/preview", response_model=NewsletterPreviewResponse)
async def newsletter_preview(request: NewsletterSendRequest) -> NewsletterPreviewResponse:
    normalize_email_address(request.email)
    get_category_label(request.category_id)
    return await build_newsletter_digest(request.category_id)


@app.post("/api/newsletter/send-test", response_model=dict[str, str])
async def newsletter_send_test(request: NewsletterSendRequest) -> dict[str, str]:
    email = normalize_email_address(request.email)
    category_label = get_category_label(request.category_id)
    digest = await send_category_newsletter(request.category_id, email)
    return {
        "status": "ok",
        "message": f"{category_label} 뉴스레터 테스트 메일을 보냈어요.",
        "subject": digest.subject,
    }


@app.post("/api/newsletter/deliver-due", response_model=dict[str, object])
async def newsletter_deliver_due(
    limit: int = 100,
    dry_run: bool = False,
    x_newsletter_admin_secret: str = Header(default=""),
) -> dict[str, object]:
    admin_secret = os.getenv("NEWSLETTER_ADMIN_SECRET", "")
    if not admin_secret or x_newsletter_admin_secret != admin_secret:
        raise HTTPException(status_code=403, detail="뉴스레터 발송 권한이 없어요.")

    from newsletter_delivery import deliver_due_newsletters

    return await deliver_due_newsletters(limit=limit, dry_run=dry_run)


@app.get("/demo/article", response_class=HTMLResponse)
async def demo_article() -> str:
    return """
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta property="og:title" content="복잡한 웹페이지를 읽기 좋은 화면으로 바꾸는 법" />
        <meta property="og:site_name" content="읽을게 데모 뉴스" />
        <meta name="description" content="접근성 좋은 리더 뷰가 왜 필요한지 설명하는 데모 기사입니다." />
        <title>복잡한 웹페이지를 읽기 좋은 화면으로 바꾸는 법</title>
      </head>
      <body>
        <header><h1>광고 영역</h1><nav>홈 뉴스 메뉴</nav></header>
        <aside>추천 기사와 배너 광고</aside>
        <article>
          <h1>복잡한 웹페이지를 읽기 좋은 화면으로 바꾸는 법</h1>
          <p>웹페이지에는 본문뿐 아니라 메뉴, 광고, 팝업, 추천 영역처럼 읽기를 방해하는 요소가 함께 들어 있다. 이런 요소는 일반 사용자에게도 피로감을 주지만, 시각적 집중이 어려운 사용자에게는 더 큰 장벽이 된다.</p>
          <p>읽기 전용 화면은 페이지에서 핵심 본문을 추출하고, 적절한 글자 크기와 줄 간격, 넓은 여백을 제공해 사용자가 글에 집중할 수 있도록 돕는다. 특히 본문 폭을 제한하면 시선 이동 거리가 줄어 긴 글을 읽을 때 부담이 낮아진다.</p>
          <p>접근성 좋은 리더 뷰는 단순히 예쁜 화면이 아니다. 사용자가 직접 글자 크기, 줄 간격, 화면 폭, 색상 대비를 조절할 수 있어야 한다. 같은 글이라도 사람마다 편하게 읽는 조건이 다르기 때문이다.</p>
          <p>이 MVP는 인공지능 기능보다 먼저 본문 추출과 읽기 경험을 안정적으로 구현하는 데 집중한다. 이후 요약, 쉬운말 변환, 음성 읽기 같은 기능을 추가하면 정보 접근성을 더 넓힐 수 있다.</p>
        </article>
        <footer>저작권 및 회사 정보</footer>
      </body>
    </html>
    """
