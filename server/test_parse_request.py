from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))

from main import ParseRequest, parse_feed_items, validate_public_http_url


class ParseRequestTest(unittest.TestCase):
    def test_parse_request_accepts_scheme_less_url(self) -> None:
        request = ParseRequest(url="example.com/article")

        self.assertEqual(str(request.url), "https://example.com/article")

    def test_parse_request_rejects_unsupported_scheme(self) -> None:
        with self.assertRaises(ValidationError):
            ParseRequest(url="ftp://example.com/article")

    def test_public_url_validation_rejects_loopback_ip(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_http_url("http://127.0.0.1/private")

    def test_public_url_validation_rejects_private_dns_result(self) -> None:
        def resolver(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
            self.assertEqual(host, "internal.example")
            self.assertEqual(port, 443)
            return [(2, 1, 6, "", ("10.0.0.8", port))]

        with self.assertRaises(ValueError):
            validate_public_http_url("https://internal.example/article", resolver=resolver)

    def test_public_url_validation_accepts_public_dns_result(self) -> None:
        def resolver(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
            self.assertEqual(host, "news.example")
            return [(2, 1, 6, "", ("93.184.216.34", port))]

        self.assertEqual(
            validate_public_http_url("https://news.example/article", resolver=resolver),
            "https://news.example/article",
        )

    def test_feed_xml_fetcher_has_single_definition(self) -> None:
        source = Path(__file__).with_name("main.py").read_text()

        self.assertEqual(source.count("async def fetch_feed_xml("), 1)

    def test_feed_item_parser_skips_non_http_links(self) -> None:
        xml = """
        <rss>
          <channel>
            <title>Example Feed</title>
            <item>
              <title>Bad Link</title>
              <link>javascript:alert(1)</link>
              <description>Bad</description>
            </item>
            <item>
              <title>Good Link</title>
              <link>https://example.com/post</link>
              <description>Good</description>
            </item>
          </channel>
        </rss>
        """

        items = parse_feed_items(xml, "tech", "IT", set(), [])

        self.assertEqual([item.url for item in items], ["https://example.com/post"])


if __name__ == "__main__":
    unittest.main()
