from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = PROJECT_ROOT / "server" / "export_presentation_data.py"


class PresentationDataExportTest(unittest.TestCase):
    def test_exports_presentation_snapshot_without_personal_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            temp_path = Path(temp_directory)
            database_path = temp_path / "newsletter.sqlite3"
            output_path = temp_path / "presentation-data.json"
            self._create_database(database_path)

            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
                    "--database",
                    str(database_path),
                    "--output",
                    str(output_path),
                    "--skip-supabase",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            serialized = json.dumps(payload, ensure_ascii=False)

            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["rss"]["default_category_count"], 8)
            self.assertEqual(payload["local_database"]["table_counts"]["newsletter_categories"], 1)
            self.assertEqual(payload["local_database"]["subscription_metrics"]["total"], 1)
            self.assertEqual(payload["supabase"]["snapshot"]["status"], "skipped")
            self.assertIn("발표용 카테고리", serialized)
            self.assertNotIn("private@example.com", serialized)
            self.assertNotIn("secret-unsubscribe-token", serialized)

    @staticmethod
    def _create_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE newsletter_categories (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    search_hint TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE newsletter_category_sources (
                    id TEXT PRIMARY KEY,
                    category_id TEXT NOT NULL,
                    source_label TEXT NOT NULL,
                    feed_url TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE newsletter_subscriptions (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    cadence TEXT NOT NULL DEFAULT 'weekly',
                    status TEXT NOT NULL DEFAULT 'active',
                    unsubscribe_token TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    last_sent_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE newsletter_delivery_attempts (
                    id TEXT PRIMARY KEY,
                    subscription_id TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    delivery_window TEXT NOT NULL,
                    status TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    sent_at TEXT NOT NULL DEFAULT '',
                    failed_at TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT ''
                );

                INSERT INTO newsletter_categories
                    (id, label, search_hint, created_at)
                VALUES
                    ('presentation', '발표용 카테고리', '발표 데이터', '2026-06-01T00:00:00+00:00');

                INSERT INTO newsletter_category_sources
                    (id, category_id, source_label, feed_url, reason, created_at)
                VALUES
                    ('source-1', 'presentation', 'Example', 'https://example.com/feed.xml',
                     '발표 테스트', '2026-06-01T00:00:00+00:00');

                INSERT INTO newsletter_subscriptions
                    (id, email, category_id, cadence, status, unsubscribe_token, created_at, last_sent_at)
                VALUES
                    ('subscription-1', 'private@example.com', 'presentation', 'weekly', 'active',
                     'secret-unsubscribe-token', '2026-06-02T00:00:00+00:00', '');
                """
            )


if __name__ == "__main__":
    unittest.main()
