from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import newsletter_store
from newsletter_delivery import deliver_due_newsletters
from main import NewsletterPreviewResponse, newsletter_unsubscribe_page, personalize_newsletter_digest
from newsletter_store import (
    claim_delivery_attempt,
    create_category,
    create_subscription,
    deactivate_subscription,
    delivery_window_for,
    ensure_categories,
    get_delivery_attempt,
    get_subscription,
    list_active_subscriptions,
    list_due_subscriptions,
    mark_delivery_failed,
    mark_delivery_sent,
    record_delivery_sent,
)


class NewsletterDeliveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = newsletter_store.DB_PATH
        newsletter_store.DB_PATH = Path(self.tempdir.name) / "newsletter.sqlite3"
        self.now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
        self.category = create_category(
            "Test",
            "test",
            [{"source_label": "Example", "feed_url": "https://example.com/feed.xml"}],
        )

    def tearDown(self) -> None:
        newsletter_store.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def create_weekly_subscription(self, email: str = "reader@example.com") -> dict[str, object]:
        return create_subscription(email, self.category["id"], "weekly")

    def test_default_category_can_be_seeded_for_subscription(self) -> None:
        ensure_categories([{"id": "geeknews", "label": "긱뉴스", "search_hint": "개발 기술"}])

        subscription = create_subscription("default@example.com", "geeknews", "weekly")

        self.assertEqual(subscription["category_id"], "geeknews")
        self.assertEqual(subscription["email"], "default@example.com")

    def test_repeated_subscription_reuses_active_record(self) -> None:
        first = self.create_weekly_subscription(" Reader@Example.com ")
        second = self.create_weekly_subscription("reader@example.com")

        self.assertEqual(second["id"], first["id"])
        self.assertEqual(len(list_active_subscriptions()), 1)

    def test_delivery_window_uses_utc_iso_week(self) -> None:
        self.assertEqual(delivery_window_for("2026-01-04T23:59:00+00:00"), "2026-W01")
        self.assertEqual(delivery_window_for("2026-01-05T00:00:00+00:00"), "2026-W02")
        self.assertEqual(delivery_window_for(datetime(2026, 6, 8, 12, 0)), "2026-W24")

    def test_store_claim_sent_failed_and_due_filters(self) -> None:
        subscription = self.create_weekly_subscription()
        inactive = self.create_weekly_subscription("inactive@example.com")
        deactivate_subscription(inactive["unsubscribe_token"])

        due = list_due_subscriptions(self.now)
        self.assertEqual([row["id"] for row in due], [subscription["id"]])

        window = delivery_window_for(self.now)
        attempt = claim_delivery_attempt(subscription["id"], subscription["category_id"], window)
        self.assertIsNotNone(attempt)
        self.assertIsNone(claim_delivery_attempt(subscription["id"], subscription["category_id"], window))
        self.assertEqual(list_due_subscriptions(self.now), [])

        mark_delivery_failed(attempt["id"], "  SMTP exploded " * 60, "2026-06-08T12:01:00+00:00")
        failed = get_delivery_attempt(attempt["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertLessEqual(len(failed["error"]), 500)
        self.assertEqual(get_subscription(subscription["id"])["last_sent_at"], "")

        mark_delivery_sent(attempt["id"], "2026-06-08T12:02:00+00:00")
        sent = get_delivery_attempt(attempt["id"])
        self.assertEqual(sent["status"], "sent")
        self.assertEqual(get_subscription(subscription["id"])["last_sent_at"], "2026-06-08T12:02:00+00:00")

    def test_record_delivery_sent_blocks_same_window_resend(self) -> None:
        subscription = self.create_weekly_subscription()
        record_delivery_sent(
            subscription["id"],
            subscription["category_id"],
            delivery_window_for(self.now),
            "2026-06-08T12:00:00+00:00",
        )

        self.assertEqual(list_due_subscriptions(self.now), [])
        self.assertEqual(get_subscription(subscription["id"])["last_sent_at"], "2026-06-08T12:00:00+00:00")

    def test_deliver_due_newsletters_is_idempotent_and_caches_digest(self) -> None:
        first = self.create_weekly_subscription("one@example.com")
        second = self.create_weekly_subscription("two@example.com")
        digest_calls: list[str] = []
        sent_to: list[str] = []

        async def build_digest(category_id: str) -> SimpleNamespace:
            digest_calls.append(category_id)
            return SimpleNamespace(subject="Subject", text_body="Text", html_body="<p>HTML</p>")

        def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
            sent_to.append(to_email)

        summary = asyncio.run(
            deliver_due_newsletters(
                now=self.now,
                digest_builder=build_digest,
                email_sender=send_email,
            )
        )
        second_summary = asyncio.run(
            deliver_due_newsletters(
                now=self.now,
                digest_builder=build_digest,
                email_sender=send_email,
            )
        )

        self.assertEqual(summary["due"], 2)
        self.assertEqual(summary["claimed"], 2)
        self.assertEqual(summary["sent"], 2)
        self.assertEqual(second_summary["due"], 0)
        self.assertEqual(sorted(sent_to), [first["email"], second["email"]])
        self.assertEqual(digest_calls, [self.category["id"]])

    def test_dry_run_has_no_side_effects(self) -> None:
        subscription = self.create_weekly_subscription()

        summary = asyncio.run(deliver_due_newsletters(now=self.now, dry_run=True))

        self.assertEqual(summary["due"], 1)
        self.assertEqual(summary["results"][0]["status"], "due")
        self.assertEqual(get_subscription(subscription["id"])["last_sent_at"], "")
        self.assertEqual(len(list_due_subscriptions(self.now)), 1)

    def test_smtp_failure_records_failed_attempt_without_last_sent(self) -> None:
        subscription = self.create_weekly_subscription()

        async def build_digest(category_id: str) -> SimpleNamespace:
            return SimpleNamespace(subject="Subject", text_body="Text", html_body="<p>HTML</p>")

        def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
            raise RuntimeError("smtp down")

        summary = asyncio.run(
            deliver_due_newsletters(
                now=self.now,
                digest_builder=build_digest,
                email_sender=send_email,
            )
        )

        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["results"][0]["status"], "failed")
        self.assertEqual(get_subscription(subscription["id"])["last_sent_at"], "")
        self.assertEqual(list_due_subscriptions(self.now), [])

    def test_personalized_digest_contains_unsubscribe_link(self) -> None:
        digest = NewsletterPreviewResponse(
            subject="Subject",
            text_body="Text body",
            html_body="<html><body><main>HTML body</main></body></html>",
        )
        with patch.dict(os.environ, {"NEWSLETTER_PUBLIC_BASE_URL": "https://reader.example"}, clear=False):
            personalized = personalize_newsletter_digest(digest, "unsubscribe-token")

        expected_url = "https://reader.example/api/newsletter/unsubscribe?token=unsubscribe-token"
        self.assertIn(expected_url, personalized.text_body)
        self.assertIn(expected_url, personalized.html_body)

    def test_browser_unsubscribe_page_deactivates_subscription(self) -> None:
        subscription = self.create_weekly_subscription()

        response = asyncio.run(newsletter_unsubscribe_page(subscription["unsubscribe_token"]))

        self.assertIn("구독을 해지했어요", response.body.decode())
        self.assertEqual(list_active_subscriptions(), [])

    def test_unsubscribe_is_idempotent_for_inactive_subscriptions(self) -> None:
        subscription = self.create_weekly_subscription()

        self.assertTrue(deactivate_subscription(subscription["unsubscribe_token"]))
        self.assertFalse(deactivate_subscription(subscription["unsubscribe_token"]))

        response = asyncio.run(newsletter_unsubscribe_page(subscription["unsubscribe_token"]))

        self.assertIn("이미 해지된 구독이에요", response.body.decode())


if __name__ == "__main__":
    unittest.main()
