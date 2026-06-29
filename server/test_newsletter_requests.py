from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))

from main import NewsletterCategoryCreateRequest, NewsletterCandidate


class NewsletterRequestValidationTest(unittest.TestCase):
    def test_category_create_rejects_blank_label(self) -> None:
        with self.assertRaises(ValidationError):
            NewsletterCategoryCreateRequest(
                label="   ",
                search_hint="AI blogs",
                sources=[NewsletterCandidate(source_label="Example", feed_url="https://example.com/feed", reason="RSS")],
            )

    def test_category_create_rejects_blank_search_hint(self) -> None:
        with self.assertRaises(ValidationError):
            NewsletterCategoryCreateRequest(
                label="AI",
                search_hint="   ",
                sources=[NewsletterCandidate(source_label="Example", feed_url="https://example.com/feed", reason="RSS")],
            )

    def test_category_create_requires_at_least_one_source(self) -> None:
        with self.assertRaises(ValidationError):
            NewsletterCategoryCreateRequest(label="AI", search_hint="AI blogs", sources=[])


if __name__ == "__main__":
    unittest.main()
