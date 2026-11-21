# -*- coding: utf-8 -*-
"""本地 RAG 知识库服务：文档导入 -> 分块 -> 向量化（bge 本地模型）-> FAISS 检索 -> LLM 生成"""
import json
import logging
import re
import threading
import time
from pathlib import Path

import faiss
import numpy as np

from app.core.config import settings
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

EMPTY_KB_REPLY = "知识库暂无内容，请管理员先导入知识文档。"
NO_HIT_REPLY = "知识库中没有找到与问题相关的内容，请换个问法或补充更多关键词。"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
ALLOWED_EXTS = {".md", ".txt", ".docx"}

_PROMPT_TMPL = (
    "请只根据下面提供的【知识库内容】回答用户问题。如果知识库内容与问题无关或信息不足，"
    "直接说明“知识库中没有相关信息”，不要编造。\n\n"
    "【知识库内容】\n{context}\n\n"
    "【用户问题】{question}\n\n"
    "【回答】"
)


class LocalRagService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._index: faiss.Index | None = None
        self._chunks: list[dict] = []            # [{doc_id, content}]
        self._documents: dict[str, dict] = {}    # doc_id -> {name, chunks, created_at}
        self._bm25 = None                        # 关键词检索引擎（懒加载）
        self._reranker = None                    # 重排序模型（懒加载）
        self._load_state()

    # ---------- 路径与持久化 ----------
    @property
    def _base_dir(self) -> Path:
        return Path(settings.knowledge_dir)

    @property
    def _docs_dir(self) -> Path:
        return self._base_dir / "documents"

    @property
    def _index_path(self) -> Path:
        return self._base_dir / "faiss.index"

    @property
    def _chunks_path(self) -> Path:
        return self._base_dir / "chunks.json"

    @property
    def _docs_path(self) -> Path:
        return self._base_dir / "documents.json"

    def _load_state(self) -> None:
        try:
            self._docs_dir.mkdir(parents=True, exist_ok=True)
            if self._chunks_path.exists():
                self._chunks = json.loads(self._chunks_path.read_text(encoding="utf-8"))
            if self._docs_path.exists():
                self._documents = json.loads(self._docs_path.read_text(encoding="utf-8"))
            if self._index_path.exists() and self._chunks:
                # 字节序列化读写：避免 faiss 底层 fopen 无法处理中文路径；deserialize 需 numpy 数组
                blob = np.frombuffer(self._index_path.read_bytes(), dtype="uint8")
                self._index = faiss.deserialize_index(blob)
        except Exception as exc:  # noqa: BLE001 索引损坏时重置，不阻塞服务
            logger.warning("知识库索引加载失败，重置为空: %s", exc)
            self._chunks, self._documents, self._index = [], {}, None
            self._bm25 = None

    def _save_state(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._chunks_path.write_text(json.dumps(self._chunks, ensure_ascii=False), encoding="utf-8")
        self._docs_path.write_text(json.dumps(self._documents, ensure_ascii=False), encoding="utf-8")
        if self._index is not None:
            self._index_path.write_bytes(faiss.serialize_index(self._index))

    # ---------- embedding ----------
    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("加载本地 embedding 模型: %s", settings.embedding_model_path)
            self._model = SentenceTransformer(settings.embedding_model_path)
        return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16)
        return np.asarray(vecs, dtype="float32")

    # ---------- 文档解析与分块 ----------
    @staticmethod
    def _split_text(text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        chunks = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + CHUNK_SIZE, length)
            chunks.append(text[start:end])
            if end == length:
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
        return chunks

    def _parse_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return path.read_text(encoding="utf-8", errors="ignore")

    # ---------- 文档管理 ----------
    def import_document(self, filename: str, data: bytes) -> dict:
        """导入文档：保存原文件 -> 解析 -> 分块 -> 向量化 -> 重建索引"""
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTS:
            raise ValueError(f"不支持的文件类型 {suffix}，仅支持 {sorted(ALLOWED_EXTS)}")
        with self._lock:
            safe_name = Path(filename).name
            target = self._docs_dir / safe_name
            target.write_bytes(data)
            text = self._parse_file(target)
            chunks = self._split_text(text)
            if not chunks:
                raise ValueError("文档内容为空，无法导入")
            doc_id = f"{int(time.time())}_{len(self._documents) + 1}"
            self._documents[doc_id] = {
                "name": safe_name, "chunks": len(chunks),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._chunks.extend({"doc_id": doc_id, "content": c} for c in chunks)
            self._rebuild_index()
            self._save_state()
            logger.info("知识库导入文档 | name=%s chunks=%d", safe_name, len(chunks))
            return {"doc_id": doc_id, "name": safe_name, "chunks": len(chunks)}

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._documents:
                return False
            doc = self._documents.pop(doc_id)
            self._chunks = [c for c in self._chunks if c["doc_id"] != doc_id]
            target = self._docs_dir / doc["name"]
            if target.exists():
                target.unlink()
            self._rebuild_index()
            self._save_state()
            logger.info("知识库删除文档 | name=%s", doc["name"])
            return True

    def list_documents(self) -> list[dict]:
        return [
            {"doc_id": k, **v}
            for k, v in sorted(self._documents.items(), key=lambda x: x[1]["created_at"], reverse=True)
        ]

    def _rebuild_index(self) -> None:
        self._bm25 = None  # 文档变化后 BM25 缓存失效
        if not self._chunks:
            self._index = None
            if self._index_path.exists():
                self._index_path.unlink()
            return
        texts = [c["content"] for c in self._chunks]
        vecs = self._embed(texts)
        dim = vecs.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vecs)
        self._index = index

    # ---------- 检索与生成 ----------
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中文简易分词：英文/数字词 + 中文字符 bigram，供 BM25 使用"""
        words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        return words + [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]

    def _bm25_retrieve(self, query: str, k: int) -> list[tuple[int, float]]:
        """BM25 关键词检索：返回 [(chunk_idx, score)]，懒加载并缓存"""
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi
            corpus = [self._tokenize(c["content"]) for c in self._chunks]
            self._bm25 = BM25Okapi(corpus)
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        order = np.argsort(scores)[::-1][:k]
        hits = []
        for i in order:
            idx = int(i)
            # 小语料下 BM25 idf 可能为 0（分数=0），按“文档与 query 有公共 token”判定命中
            shared = any(self._bm25.doc_freqs[idx].get(t, 0) > 0 for t in q_tokens)
            if shared:
                hits.append((idx, float(scores[idx])))
        return hits

    def _dynamic_top_k(self, question: str) -> int:
        """按问题类型动态调整检索数量：价格/数字类取小，对比/列举类取大"""
        if any(k in question for k in ("多少钱", "价格", "售价", "报价", "库存", "几元", "元")):
            return settings.knowledge_top_k_small
        if any(k in question for k in ("区别", "对比", "分别", "哪些", "有什么不同", "所有", "全部")):
            return settings.knowledge_top_k_large
        return settings.knowledge_top_k

    def _get_reranker(self):
        """加载本地 bge-reranker（目录不存在时返回 None，自动降级为 RRF 排序）"""
        if self._reranker is None:
            from sentence_transformers import CrossEncoder
            path = Path(settings.knowledge_reranker_path)
            if path.exists():
                logger.info("加载本地重排序模型: %s", path)
                self._reranker = CrossEncoder(str(path))
            else:
                logger.warning("重排序模型目录不存在（%s），跳过重排序", path)
        return self._reranker

    def _rerank(self, query: str, candidates: list[tuple[int, str]], top_k: int) -> list[str]:
        reranker = self._get_reranker()
        if reranker is None or not candidates:
            return [content for _, content in candidates[:top_k]]
        pairs = [(query, content) for _, content in candidates]
        try:
            scores = reranker.predict(pairs)
            ordered = sorted(zip(candidates, scores), key=lambda x: -x[1])
            return [content for (_, content), _ in ordered[:top_k]]
        except Exception as exc:  # noqa: BLE001 重排序失败退回 RRF
            logger.warning("重排序失败，退回 RRF 排序: %s", exc)
            return [content for _, content in candidates[:top_k]]

    def _search(self, query: str, top_k: int) -> tuple[list[str], float]:
        """混合检索：向量(FAISS) + BM25 关键词 -> RRF 融合 ->（可选）bge-reranker 重排序

        返回 (命中的内容列表, 最高向量相似度)
        """
        if self._index is None or not self._chunks:
            return [], 0.0
        qvec = self._embed([query])
        vec_scores, vec_ids = self._index.search(qvec, min(top_k * 2, len(self._chunks)))
        max_vec_score = float(vec_scores[0][0]) if len(vec_scores[0]) else 0.0
        bm25_hits = self._bm25_retrieve(query, top_k * 2)
        # RRF 融合（Reciprocal Rank Fusion）
        rrf: dict[int, float] = {}
        for rank, idx in enumerate(vec_ids[0]):
            if idx >= 0:
                rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (60 + rank)
        for rank, (idx, _score) in enumerate(bm25_hits):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (60 + rank)
        ranked = sorted(rrf.items(), key=lambda x: -x[1])
        candidates = [(idx, self._chunks[idx]["content"]) for idx, _ in ranked[: top_k * 2]]
        if settings.knowledge_rerank_enabled:
            return self._rerank(query, candidates, top_k), max_vec_score
        return [content for _, content in candidates[:top_k]], max_vec_score

    def ask(self, question: str) -> dict:
        """检索知识库并交给 LLM 生成回答。

        返回结构化结果 {"answer", "hit", "confidence"}：hit=False 表示未命中，
        上层可转普通对话/引导追问。
        """
        if not self._documents:
            return {"answer": EMPTY_KB_REPLY, "hit": False, "confidence": 0.0}
        try:
            hits, confidence = self._search(question, self._dynamic_top_k(question))
        except Exception as exc:  # noqa: BLE001
            logger.exception("知识库检索失败")
            return {"answer": f"知识库检索失败：{exc}", "hit": False, "confidence": 0.0}
        if not hits or confidence < settings.knowledge_min_score:
            return {"answer": NO_HIT_REPLY, "hit": False, "confidence": confidence}
        context = "\n\n---\n\n".join(hits)[:4000]
        prompt = _PROMPT_TMPL.format(context=context, question=question)
        try:
            answer = llm_service.chat([
                {"role": "system", "content": "你是智能客服助手，请基于知识库内容准确、简洁地回答，使用简体中文。"},
                {"role": "user", "content": prompt},
            ])
            return {"answer": answer, "hit": True, "confidence": confidence}
        except Exception as exc:  # noqa: BLE001
            logger.exception("知识库回答生成失败")
            return {"answer": f"知识库回答生成失败：{exc}", "hit": False, "confidence": confidence}


local_rag_service = LocalRagService()
