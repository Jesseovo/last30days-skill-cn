"""Tests for score module.

Author: Jesse (https://github.com/ChiTing111)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from lib import schema, score


class TestLog1pSafe(unittest.TestCase):
    def test_none(self):
        self.assertEqual(score.log1p_safe(None), 0.0)

    def test_zero(self):
        self.assertAlmostEqual(score.log1p_safe(0), 0.0)

    def test_positive(self):
        self.assertGreater(score.log1p_safe(100), 0)

    def test_negative(self):
        self.assertEqual(score.log1p_safe(-5), 0.0)

    def test_string(self):
        self.assertEqual(score.log1p_safe("abc"), 0.0)


class TestNormalizeTo100(unittest.TestCase):
    def test_empty(self):
        result = score.normalize_to_100([])
        self.assertEqual(result, [])

    def test_single_value(self):
        result = score.normalize_to_100([50])
        self.assertEqual(len(result), 1)

    def test_range(self):
        result = score.normalize_to_100([0, 50, 100])
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result[0], 0.0)
        self.assertAlmostEqual(result[2], 100.0)

    def test_all_same(self):
        result = score.normalize_to_100([42, 42, 42])
        for v in result:
            self.assertAlmostEqual(v, 50.0)


class TestScoreBilibiliItems(unittest.TestCase):
    def test_basic_scoring(self):
        items = [
            schema.BilibiliItem(
                id="B1", title="测试视频", url="", bvid="BV1xx",
                channel_name="UP", date="2026-03-15",
                engagement=schema.Engagement(views=1000, danmaku=50, num_comments=30, likes=100),
                relevance=0.8,
            ),
        ]
        result = score.score_bilibili_items(items)
        self.assertEqual(len(result), 1)
        self.assertGreater(result[0].score, 0)
        self.assertLessEqual(result[0].score, 100)

    def test_empty_list(self):
        result = score.score_bilibili_items([])
        self.assertEqual(result, [])


class TestScoreWeiboItems(unittest.TestCase):
    def test_basic_scoring(self):
        items = [
            schema.WeiboItem(
                id="W1", text="测试微博", url="", author_handle="user",
                date="2026-03-15",
                engagement=schema.Engagement(reposts=10, num_comments=20, likes=30),
                relevance=0.7,
            ),
        ]
        result = score.score_weibo_items(items)
        self.assertEqual(len(result), 1)
        self.assertGreater(result[0].score, 0)


class TestSortItems(unittest.TestCase):
    def test_sort_by_score_desc(self):
        items = [
            schema.ZhihuItem(id="Z1", title="低分", excerpt="", url="", author="", score=20),
            schema.ZhihuItem(id="Z2", title="高分", excerpt="", url="", author="", score=80),
        ]
        result = score.sort_items(items, query_type="concept")
        self.assertEqual(result[0].id, "Z2")
        self.assertEqual(result[1].id, "Z1")


class TestRelevanceFilter(unittest.TestCase):
    def test_keeps_relevant_items(self):
        items = [
            schema.ZhihuItem(id="Z1", title="好", excerpt="", url="", author="", relevance=0.8, score=70),
            schema.ZhihuItem(id="Z2", title="差", excerpt="", url="", author="", relevance=0.05, score=10),
        ]
        result = score.relevance_filter(items, "ZHIHU")
        self.assertGreaterEqual(len(result), 1)

    def test_empty_list(self):
        result = score.relevance_filter([], "WEIBO")
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
