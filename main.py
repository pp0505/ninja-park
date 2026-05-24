"""
主入口 - 启动 Flask API 服务
整合爬虫、Agent、推荐三个模块，提供 REST API 给前端调用

启动：python main.py
"""

import json
import os
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, DATA_DIR, KNOWLEDGE_BASE_PATH
from scraper import NinjaParkScraper
from agent import NinjaAgent
from recommender import ClassRecommender


app = Flask(__name__, static_folder="frontend", static_url_path="/static")
CORS(app)

@app.route("/")
def index():
    return app.send_static_file("index.html")


# ── 初始化各模块 ──
recommender = ClassRecommender()
agent = NinjaAgent()


# ══════════════════════════════════════
# API 路由
# ══════════════════════════════════════

# ── 1. Agent 聊天 ──
@app.route("/api/chat", methods=["POST"])
def chat():
    """
    POST /api/chat
    Body: { "message": "有什么课程？", "history": [...] }
    """
    data = request.json
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    reply = agent.chat(message, history)
    return jsonify({"reply": reply})


# ── 2. 获取推荐数据（维度 + 班型） ──
@app.route("/api/recommend/data", methods=["GET"])
def get_recommend_data():
    """
    GET /api/recommend/data
    返回当前评分表的维度和班型数据
    """
    return jsonify(recommender.to_dict())


# ── 3. 计算推荐结果 ──
@app.route("/api/recommend", methods=["POST"])
def get_recommendation():
    """
    POST /api/recommend
    Body: { "selected_dimensions": ["协调", "放松"] }
    """
    data = request.json
    selected = data.get("selected_dimensions", [])

    if not selected:
        return jsonify({"error": "请至少选择一个维度"}), 400

    results = recommender.recommend(selected)
    return jsonify({"results": results})


# ── 4. 上传新的评分表 ──
@app.route("/api/recommend/upload", methods=["POST"])
def upload_excel():
    """
    POST /api/recommend/upload
    Form-data: file=<xlsx文件>
    老板上传新的评分表，自动替换并重新加载
    """
    if "file" not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files["file"]
    if not file.filename.endswith((".xlsx", ".xls")):
        return jsonify({"error": "请上传 .xlsx 或 .xls 文件"}), 400

    # 保存到 data 目录
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_path = DATA_DIR / "gym.xlsx"
    file.save(save_path)

    # 重新加载推荐模块
    recommender.reload(save_path)

    return jsonify({
        "success": True,
        "message": f"已更新评分表: {len(recommender.classes)} 个班型, {len(recommender.dimensions)} 个维度",
        "data": recommender.to_dict(),
    })


# ── 5. 触发爬虫更新知识库 ──
@app.route("/api/scrape", methods=["POST"])
def run_scraper():
    """
    POST /api/scrape
    手动触发爬虫更新知识库
    """
    try:
        scraper = NinjaParkScraper()
        kb = scraper.scrape_all()
        scraper.save(kb)
        agent.reload_knowledge()
        return jsonify({
            "success": True,
            "message": f"爬取完成: {kb['total_pages']} 个页面",
            "scraped_at": kb["scraped_at"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 6. 健康检查 ──
@app.route("/api/health", methods=["GET"])
def health():
    kb_exists = KNOWLEDGE_BASE_PATH.exists()
    return jsonify({
        "status": "ok",
        "knowledge_base_loaded": kb_exists,
        "class_count": len(recommender.classes),
        "dimension_count": len(recommender.dimensions),
        "ai_provider": agent.provider,
    })


# ══════════════════════════════════════
# 启动
# ══════════════════════════════════════

if __name__ == "__main__":
    # 如果知识库不存在，先运行爬虫
    if not KNOWLEDGE_BASE_PATH.exists():
        print("\n📡 首次运行，正在爬取网站内容...")
        scraper = NinjaParkScraper()
        kb = scraper.scrape_all()
        scraper.save(kb)
        agent.reload_knowledge()

    print(f"\n🚀 服务已启动: http://localhost:{FLASK_PORT}")
    print(f"   Agent API:    POST /api/chat")
    print(f"   推荐 API:     POST /api/recommend")
    print(f"   上传评分表:    POST /api/recommend/upload")
    print(f"   更新知识库:    POST /api/scrape")
    print(f"   健康检查:      GET  /api/health\n")

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
