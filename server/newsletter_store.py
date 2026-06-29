from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("newsletter.sqlite3")


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        should_suppress = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return should_suppress


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def coerce_utc(value: datetime | str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def delivery_window_for(value: datetime | str | None = None) -> str:
    year, week, _ = coerce_utc(value).isocalendar()
    return f"{year}-W{week:02d}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9가-힣]+", "-", value.lower()).strip("-")
    return slug or "category"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def ensure_schema() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS newsletter_categories (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                search_hint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS newsletter_category_sources (
                id TEXT PRIMARY KEY,
                category_id TEXT NOT NULL,
                source_label TEXT NOT NULL,
                feed_url TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES newsletter_categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                category_id TEXT NOT NULL,
                cadence TEXT NOT NULL DEFAULT 'weekly',
                status TEXT NOT NULL DEFAULT 'active',
                unsubscribe_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                last_sent_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(category_id) REFERENCES newsletter_categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS newsletter_delivery_attempts (
                id TEXT PRIMARY KEY,
                subscription_id TEXT NOT NULL,
                category_id TEXT NOT NULL,
                delivery_window TEXT NOT NULL,
                status TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                sent_at TEXT NOT NULL DEFAULT '',
                failed_at TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                UNIQUE(subscription_id, delivery_window),
                FOREIGN KEY(subscription_id) REFERENCES newsletter_subscriptions(id) ON DELETE CASCADE
            );

            DELETE FROM newsletter_subscriptions
            WHERE status = 'active'
              AND rowid NOT IN (
                  SELECT MIN(rowid)
                  FROM newsletter_subscriptions
                  WHERE status = 'active'
                  GROUP BY LOWER(TRIM(email)), category_id, cadence
              );

            CREATE UNIQUE INDEX IF NOT EXISTS newsletter_active_subscription_unique
            ON newsletter_subscriptions (LOWER(TRIM(email)), category_id, cadence)
            WHERE status = 'active';
            """
        )


def ensure_categories(categories: list[dict[str, str]]) -> None:
    ensure_schema()
    created_at = now_iso()

    with connect() as connection:
        for category in categories:
            connection.execute(
                """
                INSERT INTO newsletter_categories (id, label, search_hint, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    search_hint = excluded.search_hint
                """,
                (
                    category["id"].strip(),
                    category["label"].strip(),
                    category.get("search_hint", "").strip(),
                    created_at,
                ),
            )


def create_category(label: str, search_hint: str, sources: list[dict[str, str]]) -> dict[str, Any]:
    ensure_schema()
    category_id = f"{slugify(label)}-{uuid.uuid4().hex[:8]}"
    created_at = now_iso()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO newsletter_categories (id, label, search_hint, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (category_id, label.strip(), search_hint.strip(), created_at),
        )

        for source in sources:
            connection.execute(
                """
                INSERT INTO newsletter_category_sources (
                    id, category_id, source_label, feed_url, reason, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    category_id,
                    source["source_label"].strip(),
                    source["feed_url"].strip(),
                    source.get("reason", "").strip(),
                    created_at,
                ),
            )

    return get_category(category_id)


def list_categories() -> list[dict[str, Any]]:
    ensure_schema()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, label, search_hint, created_at
            FROM newsletter_categories
            ORDER BY created_at DESC, label ASC
            """
        ).fetchall()

    return [row_to_category(dict(row), list_category_sources(row["id"])) for row in rows]


def get_category(category_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, label, search_hint, created_at
            FROM newsletter_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_category(dict(row), list_category_sources(category_id))


def list_category_sources(category_id: str) -> list[dict[str, str]]:
    ensure_schema()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT source_label, feed_url, reason
            FROM newsletter_category_sources
            WHERE category_id = ?
            ORDER BY created_at ASC
            """,
            (category_id,),
        ).fetchall()

    return [
        {
            "source_label": row["source_label"],
            "feed_url": row["feed_url"],
            "reason": row["reason"],
        }
        for row in rows
    ]


def row_to_category(row: dict[str, Any], sources: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "search_hint": row["search_hint"],
        "created_at": row["created_at"],
        "sources": sources,
    }


def create_subscription(email: str, category_id: str, cadence: str = "weekly") -> dict[str, Any]:
    ensure_schema()
    normalized_email = email.strip().lower()
    normalized_cadence = cadence.strip() or "weekly"
    subscription_id = uuid.uuid4().hex
    unsubscribe_token = uuid.uuid4().hex
    created_at = now_iso()

    with connect() as connection:
        existing = connection.execute(
            """
            SELECT id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
            FROM newsletter_subscriptions
            WHERE LOWER(TRIM(email)) = ?
              AND category_id = ?
              AND cadence = ?
              AND status = 'active'
            LIMIT 1
            """,
            (normalized_email, category_id, normalized_cadence),
        ).fetchone()
        if existing:
            return dict(existing)

        try:
            connection.execute(
                """
                INSERT INTO newsletter_subscriptions (
                    id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?, '')
                """,
                (
                    subscription_id,
                    normalized_email,
                    category_id,
                    normalized_cadence,
                    unsubscribe_token,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError:
            existing = connection.execute(
                """
                SELECT id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
                FROM newsletter_subscriptions
                WHERE LOWER(TRIM(email)) = ?
                  AND category_id = ?
                  AND cadence = ?
                  AND status = 'active'
                LIMIT 1
                """,
                (normalized_email, category_id, normalized_cadence),
            ).fetchone()
            if existing:
                return dict(existing)
            raise

    return get_subscription(subscription_id) or {
        "id": subscription_id,
        "email": normalized_email,
        "category_id": category_id,
        "cadence": normalized_cadence,
        "status": "active",
        "unsubscribe_token": unsubscribe_token,
        "created_at": created_at,
        "last_sent_at": "",
    }


def get_subscription(subscription_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
            FROM newsletter_subscriptions
            WHERE id = ?
            """,
            (subscription_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def list_active_subscriptions() -> list[dict[str, Any]]:
    ensure_schema()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
            FROM newsletter_subscriptions
            WHERE status = 'active'
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def list_due_subscriptions(now: datetime | str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    ensure_schema()
    window = delivery_window_for(now)
    bounded_limit = max(1, min(int(limit), 1000))
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
            FROM newsletter_subscriptions AS subscription
            WHERE status = 'active'
              AND cadence = 'weekly'
              AND NOT EXISTS (
                  SELECT 1
                  FROM newsletter_delivery_attempts AS attempt
                  WHERE attempt.subscription_id = subscription.id
                    AND attempt.delivery_window = ?
              )
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (window, bounded_limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_subscription_by_token(token: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at
            FROM newsletter_subscriptions
            WHERE unsubscribe_token = ?
            """,
            (token,),
        ).fetchone()

    return dict(row) if row else None


def mark_subscription_sent(subscription_id: str, sent_at: str | None = None) -> None:
    ensure_schema()
    with connect() as connection:
        connection.execute(
            """
            UPDATE newsletter_subscriptions
            SET last_sent_at = ?
            WHERE id = ?
            """,
            (sent_at or now_iso(), subscription_id),
        )


def claim_delivery_attempt(
    subscription_id: str,
    category_id: str,
    delivery_window: str,
    claimed_at: str | None = None,
) -> dict[str, Any] | None:
    ensure_schema()
    attempt_id = uuid.uuid4().hex
    claimed = claimed_at or now_iso()
    try:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO newsletter_delivery_attempts (
                    id, subscription_id, category_id, delivery_window, status, claimed_at
                )
                VALUES (?, ?, ?, ?, 'claimed', ?)
                """,
                (attempt_id, subscription_id, category_id, delivery_window, claimed),
            )
    except sqlite3.IntegrityError:
        return None

    return get_delivery_attempt(attempt_id)


def get_delivery_attempt(attempt_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, subscription_id, category_id, delivery_window, status, claimed_at,
                   sent_at, failed_at, error
            FROM newsletter_delivery_attempts
            WHERE id = ?
            """,
            (attempt_id,),
        ).fetchone()

    return dict(row) if row else None


def mark_delivery_sent(attempt_id: str, sent_at: str | None = None) -> None:
    ensure_schema()
    sent = sent_at or now_iso()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT subscription_id
            FROM newsletter_delivery_attempts
            WHERE id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if row is None:
            return
        connection.execute(
            """
            UPDATE newsletter_delivery_attempts
            SET status = 'sent', sent_at = ?, failed_at = '', error = ''
            WHERE id = ?
            """,
            (sent, attempt_id),
        )
        connection.execute(
            """
            UPDATE newsletter_subscriptions
            SET last_sent_at = ?
            WHERE id = ?
            """,
            (sent, row["subscription_id"]),
        )


def mark_delivery_failed(attempt_id: str, error: str, failed_at: str | None = None) -> None:
    ensure_schema()
    failed = failed_at or now_iso()
    trimmed_error = " ".join(str(error).split())[:500]
    with connect() as connection:
        connection.execute(
            """
            UPDATE newsletter_delivery_attempts
            SET status = 'failed', failed_at = ?, error = ?
            WHERE id = ?
            """,
            (failed, trimmed_error, attempt_id),
        )


def record_delivery_sent(
    subscription_id: str,
    category_id: str,
    delivery_window: str,
    sent_at: str | None = None,
) -> dict[str, Any] | None:
    ensure_schema()
    sent = sent_at or now_iso()
    attempt = claim_delivery_attempt(subscription_id, category_id, delivery_window, sent)
    if attempt is None:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM newsletter_delivery_attempts
                WHERE subscription_id = ?
                  AND delivery_window = ?
                """,
                (subscription_id, delivery_window),
            ).fetchone()
        if row is None:
            return None
        attempt_id = row["id"]
    else:
        attempt_id = attempt["id"]
    mark_delivery_sent(attempt_id, sent)
    return get_delivery_attempt(attempt_id)


def deactivate_subscription(token: str) -> bool:
    ensure_schema()
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE newsletter_subscriptions
            SET status = 'inactive'
            WHERE unsubscribe_token = ?
              AND status = 'active'
            """,
            (token,),
        )
    return cursor.rowcount > 0
