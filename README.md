# Hong Kong Ninja Park - 智能助手 & 课程推荐系统

## 项目架构

```
ninja-park-project/
├── README.md                  # 项目说明（本文件）
├── requirements.txt           # Python 依赖
├── config.py                  # 全局配置（API Key、URL 等）
│
├── scraper/                   # 模块1：网页爬虫
│   ├── __init__.py
│   └── scraper.py             # 爬取 hongkongninjapark.com 内容
│
├── data/                      # 数据存储
│   ├── knowledge_base.json    # 爬虫输出的知识库（自动生成）
│   └── gym.xlsx               # 老板上传的课程评分表
│
├── agent/                     # 模块2：AI 智能客服
│   ├── __init__.py
│   └── agent.py               # 调用 Claude API 做问答
│
├── recommender/               # 模块3：课程推荐引擎
│   ├── __init__.py
│   └── recommender.py         # 读取 Excel 评分表 + 计算推荐
│
├── frontend/                  # 模块4：前端界面
│   └── app.jsx                # React 前端（整合 Agent + 推荐）
│
└── main.py                    # 启动入口（运行爬虫 + 启动服务）
```

## 工作流程

1. **scraper** → 爬取网站内容 → 保存到 `data/knowledge_base.json`
2. **recommender** → 读取 `data/gym.xlsx` → 生成课程推荐数据
3. **agent** → 加载知识库 → 接收用户问题 → 调用 Claude API 回答
4. **frontend** → 提供用户界面，整合 Agent 和推荐系统

## 使用方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（在 config.py 或环境变量）
export ANTHROPIC_API_KEY="your-key-here"

# 3. 运行爬虫（首次或需要更新时）
python -m scraper.scraper

# 4. 启动服务
python main.py
```

## 老板更新课程评分表

只需将新的 Excel 文件替换 `data/gym.xlsx`，系统自动读取新数据。
Excel 格式要求：第一行为班型名称，第一列为评分维度，数值为 1-10 分。
