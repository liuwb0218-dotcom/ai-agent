# -*- coding: utf-8 -*-
"""应用配置：从 .env 加载（模板见 .env.example）"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # D:\AIAPP\ai-agent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """集中管理全部运行时配置项"""

    def __init__(self) -> None:
        # 模型后端
        self.model_provider = os.getenv("MODEL_PROVIDER", "ollama")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))  # 低温度保证工具调用稳定
        # 存储
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.redis_protocol = int(os.getenv("REDIS_PROTOCOL", "2"))  # Redis 5.x 需 RESP2
        self.session_ttl = int(os.getenv("SESSION_TTL", "1800"))
        # 服务
        self.host = os.getenv("HOST", "127.0.0.1")
        self.port = int(os.getenv("PORT", "8082"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        # 会话窗口
        self.max_history_messages = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
        self.max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
        # 工具调用
        self.tool_retry_times = int(os.getenv("TOOL_RETRY_TIMES", "1"))
        self.tool_timeout = int(os.getenv("TOOL_TIMEOUT", "10"))
        self.llm_timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        # 意图识别与知识库路由
        self.rag_service_url = os.getenv("RAG_SERVICE_URL", "").rstrip("/")  # rag-qa 服务地址（独立端口）
        # 本地 RAG 知识库（内置，不依赖 rag-qa-system）
        self.knowledge_dir = os.getenv("KNOWLEDGE_DIR", str(Path(BASE_DIR) / "knowledge"))
        self.embedding_model_path = os.getenv("EMBEDDING_MODEL_PATH", str(Path(BASE_DIR) / "models" / "bge-small-zh-v1.5"))
        self.knowledge_top_k = int(os.getenv("KNOWLEDGE_TOP_K", "5"))
        # 本地 RAG 检索增强（A2）
        self.knowledge_top_k_small = int(os.getenv("KNOWLEDGE_TOP_K_SMALL", "3"))   # 价格/数字类问题
        self.knowledge_top_k_large = int(os.getenv("KNOWLEDGE_TOP_K_LARGE", "8"))   # 对比/列举类问题
        self.knowledge_bm25_weight = float(os.getenv("KNOWLEDGE_BM25_WEIGHT", "0.3"))   # BM25 融合权重
        self.knowledge_min_score = float(os.getenv("KNOWLEDGE_MIN_SCORE", "0.5"))       # 弱命中阈值
        self.knowledge_rerank_enabled = os.getenv("KNOWLEDGE_RERANK_ENABLED", "false").lower() in ("1", "true", "yes")
        self.knowledge_reranker_path = os.getenv("KNOWLEDGE_RERANKER_PATH", str(Path(BASE_DIR) / "models" / "bge-reranker-base"))
        # 天气 API（和风天气 QWeather；mock = 内置演示数据，无需 Key）
        self.weather_api_provider = os.getenv("WEATHER_API_PROVIDER", "mock")  # mock | qweather
        self.weather_api_key = os.getenv("WEATHER_API_KEY", "").strip()
        self.weather_timeout = int(os.getenv("WEATHER_TIMEOUT", "10"))
        self.weather_cache_ttl = int(os.getenv("WEATHER_CACHE_TTL", "600"))
        # 数据库与用户体系
        self.database_url = os.getenv("DATABASE_URL", "mysql+pymysql://ai_agent:ai_agent%402026@127.0.0.1:3306/ai_agent?charset=utf8mb4")
        self.jwt_secret = os.getenv("JWT_SECRET", "")
        self.jwt_expire_hours = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
        self.upload_dir = os.getenv("UPLOAD_DIR", str(Path(BASE_DIR) / "uploads"))

        # 应用元信息
        self.app_name = "ai-agent"
        self.app_version = "0.1.0"


settings = Settings()
