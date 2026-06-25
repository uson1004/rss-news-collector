from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable

from newsletter_store import (
    claim_delivery_attempt,
    delivery_window_for,
    list_due_subscriptions,
    mark_delivery_failed,
    mark_delivery_sent,
)

DigestBuilder = Callable[[str], Awaitable[Any]]
EmailSender = Callable[[str, str, str, str], None]


def _error_text(error: BaseException) -> str:
    detail = getattr(error, "detail", "")
    if detail:
        return str(detail)
    return str(error) or error.__class__.__name__


async def _default_digest_builder(category_id: str) -> Any:
    from main import build_newsletter_digest

    return await build_newsletter_digest(category_id)


def _default_email_sender(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    from main import send_newsletter_email

    send_newsletter_email(to_email, subject, text_body, html_body)


async def deliver_due_newsletters(
    now: datetime | str | None = None,
    limit: int = 100,
    dry_run: bool = False,
    digest_builder: DigestBuilder | None = None,
    email_sender: EmailSender | None = None,
) -> dict[str, Any]:
    window = delivery_window_for(now)
    due_subscriptions = list_due_subscriptions(now, limit)
    result: dict[str, Any] = {
        "window": window,
        "due": len(due_subscriptions),
        "claimed": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "results": [],
    }

    if dry_run:
        result["results"] = [
            {
                "subscription_id": subscription["id"],
                "email": subscription["email"],
                "category_id": subscription["category_id"],
                "status": "due",
            }
            for subscription in due_subscriptions
        ]
        return result

    build_digest = digest_builder or _default_digest_builder
    send_email = email_sender or _default_email_sender
    digest_cache: dict[str, Any] = {}

    for subscription in due_subscriptions:
        attempt = claim_delivery_attempt(subscription["id"], subscription["category_id"], window)
        if attempt is None:
            result["skipped"] += 1
            result["results"].append(
                {
                    "subscription_id": subscription["id"],
                    "email": subscription["email"],
                    "category_id": subscription["category_id"],
                    "status": "skipped",
                }
            )
            continue

        result["claimed"] += 1
        row = {
            "subscription_id": subscription["id"],
            "attempt_id": attempt["id"],
            "email": subscription["email"],
            "category_id": subscription["category_id"],
            "status": "claimed",
        }

        try:
            category_id = subscription["category_id"]
            if category_id not in digest_cache:
                digest_cache[category_id] = await build_digest(category_id)
            digest = digest_cache[category_id]
            await asyncio.to_thread(
                send_email,
                subscription["email"],
                digest.subject,
                digest.text_body,
                digest.html_body,
            )
        except Exception as exc:
            mark_delivery_failed(attempt["id"], _error_text(exc))
            result["failed"] += 1
            row["status"] = "failed"
            row["error"] = _error_text(exc)
        else:
            mark_delivery_sent(attempt["id"])
            result["sent"] += 1
            row["status"] = "sent"

        result["results"].append(row)

    return result
