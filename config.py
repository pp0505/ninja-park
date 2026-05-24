import os
from pathlib import Path

# ─── 路径配置 ───
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"
EXCEL_PATH = DATA_DIR / "gym.xlsx"

# ═══════════════════════════════════════════════════════════
# AI 配置 - 切换模型只需改 AI_PROVIDER 这一行
# ═══════════════════════════════════════════════════════════
#
# 可选值: "deepseek" | "claude" | "gemini" | "openai" | "ollama"
#
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")

# ─── 各厂商配置 ───
AI_CONFIGS = {
    # DeepSeek（最便宜，推荐）
    # 注册: https://platform.deepseek.com
    # 价格: ~¥1/百万token（输入），~¥2/百万token（输出）
    "deepseek": {
        "api_key": os.getenv("DEEPSEEK_API_KEY", "sk-c566e2533ab84ceeb26fd7b766c7b72e"),
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "api_type": "openai",                   # DeepSeek 兼容 OpenAI 格式
    },

    # Claude (Anthropic)
    # 注册: https://console.anthropic.com
    "claude": {
        "api_key": os.getenv("ANTHROPIC_API_KEY", "your-anthropic-key-here"),
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
        "api_type": "anthropic",
    },

    # Gemini (Google)
    # 注册: https://aistudio.google.com
    "gemini": {
        "api_key": os.getenv("GOOGLE_API_KEY", "your-google-key-here"),
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-2.0-flash",
        "api_type": "gemini",
    },

    # OpenAI / GPT
    # 注册: https://platform.openai.com
    "openai": {
        "api_key": os.getenv("OPENAI_API_KEY", "your-openai-key-here"),
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_type": "openai",
    },

    # 本地模型 (Ollama) - 免费，无需 API Key
    # 安装: https://ollama.ai → ollama pull qwen2.5
    "ollama": {
        "api_key": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5",
        "api_type": "openai",                   # Ollama 兼容 OpenAI 格式
    },
}

def get_ai_config() -> dict:
    if AI_PROVIDER not in AI_CONFIGS:
        raise ValueError(f"不支持的 AI_PROVIDER: {AI_PROVIDER}，可选: {list(AI_CONFIGS.keys())}")
    return AI_CONFIGS[AI_PROVIDER]

# ─── 爬虫配置 ───
BASE_URL = "https://hongkongninjapark.com"

# 需要爬取的页面路径
SCRAPE_PAGES = [
    "/",
    "/about/",
    "/about/founders-words/",
    "/about/%e5%a0%b4%e5%9c%b0%e8%a8%ad%e6%96%bd-our-obstacles/",
    "/about/%e9%97%9c%e6%96%bc%e5%bf%8d%e8%80%85%e9%81%8b%e5%8b%95/",
    "/%e8%87%aa%e7%94%b1%e7%b7%b4%e7%bf%92%e6%99%82%e6%ae%b5open-gym-session/",
    "/%e5%bf%8d%e8%80%85%e8%a8%93%e7%b7%b4%e7%8f%ad-ninja-class/",
    "/%e5%8c%85%e7%8f%ad-%e5%8c%85%e5%a0%b4%e6%b4%bb%e5%8b%95-private-event/",
    "/%e5%93%a1%e5%b7%a5-%e5%9c%98%e9%9a%8a%e5%9f%b9%e8%a8%93-team-building/",
    "/%e6%a9%9f%e6%a7%8b%e5%90%88%e4%bd%9c/",
    "/%e7%89%a9%e5%93%81%e9%8a%b7%e5%94%ae-items-for-sale/",
    "/contact/",
]

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# ─── Flask 配置 ───
FLASK_HOST = "0.0.0.0"
FLASK_PORT = int(os.getenv("PORT", 8000))
FLASK_DEBUG = True