"""Tests for normalize module.

Author: Jesse (https://github.com/ChiTing111)
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from lib import normalize, schema

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '..', 'fixtures')


class TestFilterByDateRange(unittest.TestCase):
    def _make_item(self, date_str):
        return schema.ZhihuItem(
            id="Z1", title="test", excerpt="", url="", author="",
            date=date_str, date_confidence="high",
        )

    def test_within_range(self):
        items = [self._make_item("2026-03-15")]
        result = normalize.filter_by_date_range(items, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 1)

    def test_before_range(self):
        items = [self._make_item("2026-02-15")]
        result = normalize.filter_by_date_range(items, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 0)

    def test_after_range(self):
        items = [self._make_item("2026-04-15")]
        result = normalize.filter_by_date_range(items, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 0)

    def test_none_date_kept_by_default(self):
        items = [self._make_item(None)]
        result = normalize.filter_by_date_range(items, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 1)

    def test_none_date_filtered_when_required(self):
        items = [self._make_item(None)]
        result = normalize.filter_by_date_range(items, "2026-03-01", "2026-03-31", require_date=True)
        self.assertEqual(len(result), 0)


class TestNormalizeBilibiliItems(unittest.TestCase):
    def test_basic_normalization(self):
        raw = [{
            "id": "B1",
            "bvid": "BV1xx",
            "title": "测试视频",
            "url": "https://bilibili.com/video/BV1xx",
            "channel_name": "UP主",
            "author_mid": "123",
            "date": "2026-03-15",
            "engagement": {"views": 1000, "danmaku": 50, "comments": 30, "likes": 100, "favorites": 40},
            "description": "描述",
            "duration": 600,
            "relevance": 0.8,
        }]
        result = normalize.normalize_bilibili_items(raw, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], schema.BilibiliItem)
        self.assertEqual(result[0].bvid, "BV1xx")
        self.assertEqual(result[0].channel_name, "UP主")

    def test_empty_input(self):
        result = normalize.normalize_bilibili_items([], "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 0)


class TestNormalizeWeiboItems(unittest.TestCase):
    def test_basic_normalization(self):
        raw = [{
            "mid": "123",
            "text": "测试微博",
            "url": "https://weibo.com/123",
            "author_handle": "test_user",
            "author_id": "456",
            "date": "2026-03-15",
            "reposts_count": 10,
            "comments_count": 20,
            "attitudes_count": 30,
            "relevance": 0.8,
            "why_relevant": "测试",
        }]
        result = normalize.normalize_weibo_items(raw, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], schema.WeiboItem)


class TestNormalizeZhihuItems(unittest.TestCase):
    def test_basic_normalization(self):
        raw = [{
            "id": "Z1",
            "title": "测试问题",
            "excerpt": "测试摘要",
            "url": "https://zhihu.com/q/123",
            "author": "知友",
            "date": "2026-03-15",
            "content_type": "answer",
            "voteup_count": 100,
            "comment_count": 20,
            "relevance": 0.7,
            "why_relevant": "测试",
        }]
        result = normalize.normalize_zhihu_items(raw, "2026-03-01", "2026-03-31")
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], schema.ZhihuItem)


class TestFixtureParsing(unittest.TestCase):
    """Verify fixture JSON files are valid and parseable."""

    def test_bilibili_fixture_valid(self):
        path = os.path.join(FIXTURES_DIR, 'bilibili_sample.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        results = data['data']['result']
        self.assertGreater(len(results), 0)
        self.assertIn('bvid', results[0])
        self.assertIn('title', results[0])

    def test_weibo_fixture_valid(self):
        path = os.path.join(FIXTURES_DIR, 'weibo_sample.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        statuses = data['statuses']
        self.assertGreater(len(statuses), 0)
        self.assertIn('text', statuses[0])
        self.assertIn('user', statuses[0])

    def test_zhihu_fixture_valid(self):
        path = os.path.join(FIXTURES_DIR, 'zhihu_sample.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        results = data['data']
        self.assertGreater(len(results), 0)
        self.assertIn('object', results[0])


if __name__ == '__main__':
    unittest.main()
