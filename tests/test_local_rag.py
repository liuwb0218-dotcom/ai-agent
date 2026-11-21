# -*- coding: utf-8 -*-
"""本地 RAG 知识库测试：分块 / 导入 / 检索 / ask（mock LLM）/ 空库"""
import pytest

from app.core.config import settings
from app.services import local_rag as lr
from app.services.local_rag import LocalRagService, _PROMPT_TMPL


@pytest.fixture()
def rag(tmp_path, monkeypatch):
    """使用临时目录作为知识库，避免污染真实数据；测试环境跳过 reranker 加载"""
    original = settings.knowledge_dir
    settings.knowledge_dir = str(tmp_path)
    monkeypatch.setattr(settings, "knowledge_rerank_enabled", False)
    svc = LocalRagService()
    yield svc
    settings.knowledge_dir = original


class TestSplitText:
    def test_short_text(self):
        assert LocalRagService._split_text("你好") == ["你好"]

    def test_long_text(self):
        text = "这是一段测试内容。" * 200  # 约 1800 字
        chunks = LocalRagService._split_text(text)
        assert len(chunks) >= 3
        assert all(len(c) <= lr.CHUNK_SIZE for c in chunks)

    def test_overlap(self):
        text = "A" * 600
        chunks = LocalRagService._split_text(text)
        assert len(chunks) == 2
        # 重叠区包含两块交界内容
        assert "A" * lr.CHUNK_OVERLAP in chunks[1]


class TestImportAndSearch:
    def test_import_and_search(self, rag):
        doc = rag.import_document("商品.md", "无线鼠标售价99元，提供12个月保修。".encode("utf-8"))
        assert doc["chunks"] >= 1
        assert rag.list_documents()[0]["name"] == "商品.md"
        hits, _conf = rag._search("无线鼠标保修", 3)
        assert hits and "99" in hits[0]

    def test_unsupported_type(self, rag):
        with pytest.raises(ValueError):
            rag.import_document("evil.pdf", b"x")

    def test_delete(self, rag):
        doc = rag.import_document("测试.md", "内容内容内容".encode("utf-8"))
        assert rag.delete_document(doc["doc_id"]) is True
        assert rag.list_documents() == []
        assert rag.delete_document(doc["doc_id"]) is False

    def test_empty_kb_ask(self, rag):
        result = rag.ask("你好")
        assert result["answer"] == lr.EMPTY_KB_REPLY
        assert result["hit"] is False


class TestAsk:
    def test_ask_with_mock_llm(self, rag, monkeypatch):
        rag.import_document("FAQ.md", "取消订单后库存会自动回补。".encode("utf-8"))
        calls = []

        class FakeLLM:
            def chat(self, messages):
                calls.append(messages)
                return "取消订单后库存自动回补。"

        monkeypatch.setattr(lr, "llm_service", FakeLLM())
        result = rag.ask("取消订单会怎样")
        assert result["hit"] is True
        assert "回补" in result["answer"]
        assert calls and "取消订单后库存会自动回补" in calls[0][-1]["content"]

    def test_prompt_template_has_newlines(self):
        assert "\n" in _PROMPT_TMPL or chr(10) in _PROMPT_TMPL


class TestPersistence:
    def test_reload_index(self, rag):
        rag.import_document("知识.md", "商品保修期十二个月，支持七天无理由退货。".encode("utf-8"))
        # 用同一目录新建实例，验证索引可加载
        svc2 = LocalRagService()
        assert len(svc2.list_documents()) == 1
        hits, _conf = svc2._search("保修期", 3)
        assert hits and "保修期" in hits[0]


class TestRetrievalEnhance:
    """A2：动态 top_k / 中文分词 / BM25 / 未命中结构化返回"""

    def test_dynamic_top_k_price(self, rag):
        assert rag._dynamic_top_k("无线鼠标多少钱") == settings.knowledge_top_k_small

    def test_dynamic_top_k_compare(self, rag):
        assert rag._dynamic_top_k("机械键盘和显示器有什么区别") == settings.knowledge_top_k_large

    def test_dynamic_top_k_default(self, rag):
        assert rag._dynamic_top_k("你好") == settings.knowledge_top_k

    def test_tokenize(self):
        toks = LocalRagService._tokenize("无线鼠标 price99")
        assert "price99" in toks
        assert any("无线" in t for t in toks)  # 中文 bigram

    def test_bm25_retrieve(self, rag):
        rag.import_document("售后.md", "保修期十二个月，支持七天无理由退货。".encode("utf-8"))
        rag.import_document("商品.md", "无线鼠标售价99元。".encode("utf-8"))
        hits = rag._bm25_retrieve("保修期", 2)
        assert hits
        top_idx = hits[0][0]
        assert "保修期" in rag._chunks[top_idx]["content"]

    def test_ask_miss_returns_hit_false(self, rag, monkeypatch):
        rag.import_document("商品.md", "无线鼠标售价99元，机械键盘售价399元。".encode("utf-8"))
        monkeypatch.setattr(lr, "llm_service", type("F", (), {"chat": staticmethod(lambda m: "闲聊回复")})())
        result = rag.ask("今天晚饭吃什么")
        assert result["hit"] is False
        assert result["confidence"] < settings.knowledge_min_score
