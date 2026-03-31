"""Tests for entity_extract module (Chinese platforms)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import entity_extract


class TestExtractWeiboUsers(unittest.TestCase):
    def test_basic_author_handle(self):
        items = [{"author_handle": "科技博主", "text": ""}]
        result = entity_extract._extract_weibo_users(items)
        self.assertEqual(result, ["科技博主"])

    def test_mentions_in_text(self):
        items = [{"text": "转自 @研究员A 和 @开发者B"}]
        result = entity_extract._extract_weibo_users(items)
        self.assertIn("研究员A", result)
        self.assertIn("开发者B", result)

    def test_generic_handles_filtered(self):
        items = [
            {"author_handle": "@人民日报", "text": ""},
            {"author_handle": "真实用户", "text": ""},
        ]
        result = entity_extract._extract_weibo_users(items)
        self.assertEqual(result, ["真实用户"])

    def test_frequency_ranking(self):
        items = [
            {"author_handle": "热门", "text": ""},
            {"author_handle": "热门", "text": ""},
            {"author_handle": "冷门", "text": ""},
        ]
        result = entity_extract._extract_weibo_users(items)
        self.assertEqual(result[0], "热门")

    def test_empty_input(self):
        self.assertEqual(entity_extract._extract_weibo_users([]), [])


class TestExtractXiaohongshuTopics(unittest.TestCase):
    def test_double_hash_topic(self):
        items = [{"text": "今日分享 #旅行攻略# 干货"}]
        result = entity_extract._extract_xiaohongshu_topics(items)
        self.assertIn("旅行攻略", result)

    def test_multiple_topics(self):
        items = [{"title": "#美妆# 和 #护肤#"}]
        result = entity_extract._extract_xiaohongshu_topics(items)
        self.assertIn("美妆", result)
        self.assertIn("护肤", result)

    def test_hashtags_list(self):
        items = [{"hashtags": ["露营", "户外"]}]
        result = entity_extract._extract_xiaohongshu_topics(items)
        self.assertIn("露营", result)
        self.assertIn("户外", result)

    def test_empty_input(self):
        self.assertEqual(entity_extract._extract_xiaohongshu_topics([]), [])


class TestExtractZhihuQuestions(unittest.TestCase):
    def test_title_field(self):
        items = [{"title": "如何评价某产品的 2026 年更新？"}]
        result = entity_extract._extract_zhihu_questions(items)
        self.assertIn("如何评价某产品的 2026 年更新？", result)

    def test_question_field(self):
        items = [{"question": "深度学习入门路线？"}]
        result = entity_extract._extract_zhihu_questions(items)
        self.assertIn("深度学习入门路线？", result)


class TestExtractEntities(unittest.TestCase):
    def test_integration(self):
        weibo = [{"author_handle": "数码君", "text": "关注 @同事小王 #忽略#"}]
        xhs = [{"text": "推荐 #好物分享#"}]
        zh = [{"title": "值得购买吗？"}]
        result = entity_extract.extract_entities(weibo, xhs, zhihu_items=zh)
        self.assertIn("数码君", result["weibo_users"])
        self.assertIn("同事小王", result["weibo_users"])
        self.assertIn("好物分享", result["xiaohongshu_topics"])
        self.assertIn("值得购买吗？", result["zhihu_questions"])

    def test_max_limits(self):
        wb = [{"author_handle": f"用户{i}", "text": ""} for i in range(10)]
        result = entity_extract.extract_entities(wb, [], max_weibo_users=2)
        self.assertLessEqual(len(result["weibo_users"]), 2)

    def test_empty_inputs(self):
        result = entity_extract.extract_entities([], [])
        self.assertEqual(result["weibo_users"], [])
        self.assertEqual(result["xiaohongshu_topics"], [])
        self.assertEqual(result["zhihu_questions"], [])

    def test_return_keys(self):
        result = entity_extract.extract_entities([], [])
        self.assertEqual(
            set(result.keys()),
            {"weibo_users", "xiaohongshu_topics", "zhihu_questions"},
        )


if __name__ == "__main__":
    unittest.main()
