"""
AI 客服 Agent - 基于知识库回答用户问题
支持多个 AI 后端，通过 config.py 一行切换

支持的后端：
  - deepseek  → DeepSeek（最便宜，兼容 OpenAI 格式）
  - claude    → Anthropic Claude
  - gemini    → Google Gemini
  - openai    → OpenAI GPT
  - ollama    → 本地 Ollama（免费）

用法：
    from agent import NinjaAgent
    agent = NinjaAgent()
    reply = agent.chat("有什么课程？")
"""

import json
import sys
import os

import requests as req

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import KNOWLEDGE_BASE_PATH, AI_PROVIDER, get_ai_config
from scraper.scraper import NinjaParkScraper


SYSTEM_PROMPT = """你是 Hong Kong Ninja Park（香港障礙競技學園）的客服助手。

你的职责：
1. 根据知识库准确回答用户关于课程、时间表、价格、地点等问题
2. 用繁體中文或英文回答（根据用户使用的语言自动切换）
3. 回答要友善、简洁、专业
4. 如果用户想预约，引导到预约系统：https://sasukeninjaparkauau.auau.io/zh-HK/
5. 如果问题超出知识范围，建议联系客服：
   - 电话/WhatsApp: 9832 2052
   - 电邮: cs@hongkongninjapark.com

以下是你的知识库内容：
{knowledge_base}
"""

ERROR_MSG = "抱歉，AI 服务暂时不可用。请直接联系客服 9832 2052。\n(错误: {error})"


class NinjaAgent:
    """AI 客服 Agent，统一接口支持多个后端"""

    def __init__(self, provider: str = AI_PROVIDER):
        self.provider = provider
        self.config = get_ai_config()
        self.knowledge_text = self._load_knowledge()
        self.system_prompt = SYSTEM_PROMPT.format(knowledge_base=self.knowledge_text)

        print(f"🤖 AI 后端: {self.provider} (模型: {self.config['model']})")

    # ── 加载知识库 ──
    def _load_knowledge(self) -> str:
        if KNOWLEDGE_BASE_PATH.exists():
            with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
                kb = json.load(f)
            print(f"📚 已加载知识库: {kb['total_pages']} 个页面 (爬取于 {kb['scraped_at'][:10]})")
            return NinjaParkScraper.to_plain_text(kb)
        else:
            print("⚠️  知识库不存在，请先运行爬虫: python -m scraper.scraper")
            return "知识库尚未生成，请先运行爬虫。"

    # ══════════════════════════════════════
    # 统一对话入口
    # ══════════════════════════════════════
    def chat(self, user_message: str, history: list[dict] = None) -> str:
        history = history or []
        api_type = self.config["api_type"]

        try:
            if api_type == "openai":
                return self._chat_openai_compatible(user_message, history)
            elif api_type == "anthropic":
                return self._chat_anthropic(user_message, history)
            elif api_type == "gemini":
                return self._chat_gemini(user_message, history)
            else:
                return f"不支持的 api_type: {api_type}"
        except Exception as e:
            print(f"[{self.provider}] API 错误: {e}")
            return ERROR_MSG.format(error=e)

    # ══════════════════════════════════════
    # OpenAI 兼容格式（DeepSeek / OpenAI / Ollama 共用）
    # ══════════════════════════════════════
    def _chat_openai_compatible(self, user_message: str, history: list[dict]) -> str:
        """
        DeepSeek、OpenAI、Ollama 都用 OpenAI 的 /chat/completions 格式，
        只是 base_url 和 api_key 不同
        """
        cfg = self.config
        url = f"{cfg['base_url']}/chat/completions"

        messages = [{"role": "system", "content": self.system_prompt}]
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_message})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        }

        resp = req.post(url, headers=headers, json={
            "model": cfg["model"],
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7,
        }, timeout=30)

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ══════════════════════════════════════
    # Anthropic Claude（独有格式）
    # ══════════════════════════════════════
    def _chat_anthropic(self, user_message: str, history: list[dict]) -> str:
        cfg = self.config

        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})

        headers = {
            "Content-Type": "application/json",
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
        }

        resp = req.post(f"{cfg['base_url']}/v1/messages", headers=headers, json={
            "model": cfg["model"],
            "max_tokens": 1024,
            "system": self.system_prompt,
            "messages": messages,
        }, timeout=30)

        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    # ══════════════════════════════════════
    # Google Gemini（独有格式）
    # ══════════════════════════════════════
    def _chat_gemini(self, user_message: str, history: list[dict]) -> str:
        cfg = self.config

        contents = [
            {"role": "user", "parts": [{"text": self.system_prompt + "\n\n请确认你已理解以上角色设定和知识库。"}]},
            {"role": "model", "parts": [{"text": "已理解！我是 Hong Kong Ninja Park 的客服助手，随时为你服务！🥷"}]},
        ]
        for m in history:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        resp = req.post(
            f"{cfg['base_url']}/v1beta/models/{cfg['model']}:generateContent",
            params={"key": cfg["api_key"]},
            json={"contents": contents},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    # ── 重新加载知识库 ──
    def reload_knowledge(self):
        self.knowledge_text = self._load_knowledge()
        self.system_prompt = SYSTEM_PROMPT.format(knowledge_base=self.knowledge_text)
        print("🔄 知识库已重新加载")


# ══════════════════════════════════════
# 直接运行测试
# ══════════════════════════════════════
if __name__ == "__main__":
    agent = NinjaAgent()

    test_questions = [
        "你好，请问有什么课程？",
        "成人忍者班什么时间上课？",
        "How much is the kids class?",
        "我想预约 Open Gym",
    ]

    for q in test_questions:
        print(f"\n👤 {q}")
        reply = agent.chat(q)
        print(f"🥷 {reply}")