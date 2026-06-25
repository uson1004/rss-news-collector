from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))

from main import ParseRequest


class ParseRequestTest(unittest.TestCase):
    def test_parse_request_accepts_scheme_less_url(self) -> None:
        request = ParseRequest(url="example.com/article")

        self.assertEqual(str(request.url), "https://example.com/article")

    def test_parse_request_rejects_unsupported_scheme(self) -> None:
        with self.assertRaises(ValidationError):
            ParseRequest(url="ftp://example.com/article")


if __name__ == "__main__":
    unittest.main()
