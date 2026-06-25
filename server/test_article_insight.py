from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent))

from main import create_claude_article_insight, parse_article_insight_output


class ArticleInsightTest(unittest.TestCase):
    def test_parse_article_insight_output_accepts_json_fenced_response(self) -> None:
        output = """
```json
{
  "why_read": ["청년 주거 선택이 바뀌는 신호를 보여줘요."],
  "signals": ["월세 부담 때문에 공유형 주거에 관심이 커질 가능성이 있어요."],
  "frictions_or_desires": ["고정비를 줄이고 싶은 욕구가 보여요."],
  "idea_prompts": ["동네 단위 월세 협상 정보를 모아보면 어떨까요?"],
  "caveats": []
}
```
"""

        insight = parse_article_insight_output(output, "test-model")

        self.assertEqual(insight.model, "test-model")
        self.assertEqual(insight.why_read, ["청년 주거 선택이 바뀌는 신호를 보여줘요."])
        self.assertEqual(insight.idea_prompts, ["동네 단위 월세 협상 정보를 모아보면 어떨까요?"])

    def test_parse_article_insight_output_adds_caveat_for_low_signal(self) -> None:
        insight = parse_article_insight_output(
            '{"why_read":[],"signals":[],"frictions_or_desires":[],"idea_prompts":[],"caveats":[]}',
            "test-model",
        )

        self.assertEqual(insight.caveats, ["이 글에서는 뚜렷한 아이디어 신호를 찾기 어려워요."])

    def test_create_article_insight_requires_api_key(self) -> None:
        original_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with self.assertRaises(HTTPException) as context:
                asyncio.run(create_claude_article_insight("제목", "본문 " * 120))
            self.assertEqual(context.exception.status_code, 503)
        finally:
            if original_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = original_key


if __name__ == "__main__":
    unittest.main()
