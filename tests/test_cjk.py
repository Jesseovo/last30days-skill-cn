"""Tests for optional CJK tokenization helpers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import cjk


class TestCjkSegment(unittest.TestCase):
    def test_bigram_fallback_without_jieba(self):
        old_jieba = cjk._jieba
        try:
            cjk._jieba = None
            tokens = cjk.segment("国产大模型评测")
        finally:
            cjk._jieba = old_jieba

        self.assertIn("国产", tokens)
        self.assertIn("大模", tokens)
        self.assertIn("模型", tokens)
        self.assertNotIn("大", tokens)

    def test_segment_mixed_latin_and_cjk(self):
        old_jieba = cjk._jieba
        try:
            cjk._jieba = None
            tokens = cjk.segment("Claude Code编程助手")
        finally:
            cjk._jieba = old_jieba

        self.assertIn("claude", tokens)
        self.assertIn("code", tokens)
        self.assertIn("编程", tokens)

    def test_segment_runs_preserves_cjk_phrases_for_outgoing_queries(self):
        tokens = cjk.segment_runs("最新 Claude Code 编程助手 推荐")
        self.assertIn("claude", tokens)
        self.assertIn("code", tokens)
        self.assertIn("编程助手", tokens)
        self.assertNotIn("编程", tokens)


if __name__ == "__main__":
    unittest.main()
