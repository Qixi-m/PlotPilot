"""
aitext 配置：与 aivideo 同源 ARK/豆包环境变量；路径相对包根 aitext/。
长篇小说对话：可通过环境变量加大「梗概 + 章摘要 + 三元组 + 设定」注入上限。
"""
import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
BASE_DIR = _BASE
OUTPUT_DIR = _BASE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR = OUTPUT_DIR / "novels"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    # LLM Provider: "ark" | "anthropic" | "openai"
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

    # ARK/豆包配置
    ARK_API_KEY = os.getenv("ARK_API_KEY", "")
    ARK_BASE_URL = os.getenv(
        "ARK_BASE_URL",
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    ).strip()
    ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-2-0-mini-260215")
    ARK_TIMEOUT = int(os.getenv("ARK_TIMEOUT", "120"))
    ARK_REASONING_EFFORT = os.getenv("ARK_REASONING_EFFORT", "medium")

    # Anthropic/Claude配置
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_AUTH_TOKEN", ""))
    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    # 默认篇幅
    DEFAULT_CHAPTER_COUNT = int(os.getenv("AITEXT_DEFAULT_CHAPTERS", "5"))
    DEFAULT_WORDS_PER_CHAPTER = int(os.getenv("AITEXT_DEFAULT_WORDS_PER_CHAPTER", "2500"))
    # 滚动摘要保留最近 K 章条目
    RUNNING_SUMMARY_MAX_CHAPTERS = int(os.getenv("AITEXT_SUMMARY_MAX_CHAPTERS", "5"))
    # 向量检索：bge-small-zh-v1.5 + Chroma
    EMBEDDING_MODEL = os.getenv("AITEXT_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    VECTOR_TOP_K = int(os.getenv("AITEXT_VECTOR_TOP_K", "6"))
    VECTOR_MAX_SNIPPET_CHARS = int(os.getenv("AITEXT_VECTOR_MAX_SNIPPET_CHARS", "600"))

    # —— 对话工作台 · 上下文工程（长篇百万字级须配合侧栏梗概/章摘要/关系图）——
    CHAT_WINDOW_MESSAGES = int(os.getenv("AITEXT_CHAT_WINDOW_MESSAGES", "28"))
    # 近期对话轮次（user+assistant）在窗口内再按字符截断
    CHAT_MAX_CONTEXT_CHARS = int(os.getenv("AITEXT_CHAT_MAX_CONTEXT_CHARS", "18000"))
    # 远期摘要 context_digest.md 注入上限
    CHAT_DIGEST_MAX_CHARS = int(os.getenv("AITEXT_CHAT_DIGEST_MAX_CHARS", "8000"))
    CHAT_DIGEST_TRIGGER_COUNT = int(os.getenv("AITEXT_CHAT_DIGEST_TRIGGER_COUNT", "40"))
    # 注入 system 的「梗概锁定 + 章摘要 + 三元组 + 滚动摘要」总字符上限
    CHAT_NOVEL_KNOWLEDGE_MAX_CHARS = int(os.getenv("AITEXT_NOVEL_KNOWLEDGE_MAX_CHARS", "20000"))
    # 最近若干章的摘要注入（按章号排序后取尾部，适合长卷只带尾窗）
    CHAT_CHAPTER_SUMMARY_MAX = int(os.getenv("AITEXT_CHAPTER_SUMMARY_MAX", "48"))
    # 设定库 / 大纲压缩进 system 的上限（人类可读文本，非 JSON）
    CHAT_BIBLE_COMPACT_CHARS = int(os.getenv("AITEXT_BIBLE_COMPACT_CHARS", "14000"))
    CHAT_OUTLINE_COMPACT_CHARS = int(os.getenv("AITEXT_OUTLINE_COMPACT_CHARS", "12000"))
