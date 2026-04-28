"""
爬虫模块 - 爬取 Hong Kong Ninja Park 网站内容
支持多种策略应对反爬机制（403 Forbidden）

策略优先级（auto 模式）：
  1. requests + 完整浏览器请求头 + Cookie 预热
  2. cloudscraper（专门绕过 Cloudflare 防护）
  3. Selenium 无头浏览器（终极方案）

用法：
    python -m scraper.scraper                    # 自动选择最佳策略
    python -m scraper.scraper --method requests
    python -m scraper.scraper --method cloudscraper
    python -m scraper.scraper --method selenium
    python -m scraper.scraper --dry              # 仅打印，不保存
"""

import json
import random
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_URL, SCRAPE_PAGES, KNOWLEDGE_BASE_PATH, DATA_DIR


# ── 随机 User-Agent 池 ──
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


def _build_headers(referer: str = "") -> dict:
    """构造完整的浏览器请求头"""
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Cache-Control": "max-age=0",
    }
    if referer:
        h["Referer"] = referer
    return h


class NinjaParkScraper:
    """爬取 Hong Kong Ninja Park 网站并输出结构化知识库"""

    def __init__(self, base_url=BASE_URL, pages=SCRAPE_PAGES, method="auto"):
        self.base_url = base_url
        self.pages = pages
        self.method = method
        self._driver = None
        self._session = None  # 复用 requests session

    # ══════════════════════════════════════
    # 策略 1：requests + 完整请求头 + Cookie 预热
    # ══════════════════════════════════════
    def _get_session(self) -> requests.Session:
        """创建并预热 session（首次访问首页获取 Cookie）"""
        if self._session is not None:
            return self._session

        self._session = requests.Session()
        # 预热：先访问首页拿 Cookie
        try:
            print("    ↳ 预热 Cookie...")
            self._session.get(
                self.base_url,
                headers=_build_headers(),
                timeout=15,
                allow_redirects=True,
            )
            time.sleep(random.uniform(1, 2))
        except Exception:
            pass
        return self._session

    def _fetch_requests(self, url: str) -> str | None:
        session = self._get_session()
        headers = _build_headers(referer=self.base_url)
        resp = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    # ══════════════════════════════════════
    # 策略 2：cloudscraper（绕 Cloudflare）
    # ══════════════════════════════════════
    def _fetch_cloudscraper(self, url: str) -> str | None:
        try:
            import cloudscraper
        except ImportError:
            return None

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        resp = scraper.get(url, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    # ══════════════════════════════════════
    # 策略 3：Selenium 无头浏览器
    # ══════════════════════════════════════
    def _get_driver(self):
        if self._driver is not None:
            return self._driver
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
        except ImportError:
            return None

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            try:
                self._driver = webdriver.Chrome(options=options)
            except Exception:
                return None
        return self._driver

    def _fetch_selenium(self, url: str) -> str | None:
        driver = self._get_driver()
        if driver is None:
            return None
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        return driver.page_source

    # ══════════════════════════════════════
    # 核心：按策略顺序尝试抓取
    # ══════════════════════════════════════
    def fetch_page(self, path: str) -> dict | None:
        url = urljoin(self.base_url, path)

        if self.method == "auto":
            methods = ["requests", "cloudscraper", "selenium"]
        else:
            methods = [self.method]

        for method in methods:
            try:
                if method == "requests":
                    html = self._fetch_requests(url)
                elif method == "cloudscraper":
                    html = self._fetch_cloudscraper(url)
                elif method == "selenium":
                    html = self._fetch_selenium(url)
                else:
                    continue

                if html and len(html) > 500:
                    if method != methods[0]:
                        print(f"    ↳ 使用 {method} 成功")
                    return self._parse_page(url, html)

            except Exception as e:
                if self.method != "auto":
                    print(f"  ✗ [{method}] {url}: {e}")
                continue

        print(f"  ✗ 所有策略均失败: {url}")
        return None

    # ══════════════════════════════════════
    # 解析 HTML
    # ══════════════════════════════════════
    def _parse_page(self, url: str, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        title = soup.find("h1")
        title_text = title.get_text(strip=True) if title else ""

        content_area = (
            soup.find("div", class_="entry-content")
            or soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="page-content")
            or soup.body
            or soup
        )

        # 表格
        tables = []
        for table in content_area.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if any(cells):
                    rows.append(cells)
            if rows:
                tables.append(rows)

        # 段落
        paragraphs = []
        for el in content_area.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
            text = el.get_text(strip=True)
            text = re.sub(r"\s+", " ", text)
            if text and len(text) > 2:
                prefix = f"[{el.name.upper()}] " if el.name.startswith("h") else ""
                paragraphs.append(prefix + text)

        # 图片 alt
        images = []
        for img in content_area.find_all("img"):
            alt = img.get("alt", "").strip()
            src = img.get("src", "")
            if alt and "base64" not in src:
                images.append({"alt": alt, "src": src})

        return {
            "url": url,
            "title": title_text,
            "paragraphs": paragraphs,
            "tables": tables,
            "images": images[:10],
        }

    # ══════════════════════════════════════
    # 爬取所有页面
    # ══════════════════════════════════════
    def scrape_all(self, delay: float = 1.5) -> dict:
        print(f"🕷️  开始爬取 {self.base_url} ({len(self.pages)} 个页面)")
        print(f"    策略模式: {self.method}")
        pages_data = []

        for i, path in enumerate(self.pages):
            print(f"  [{i+1}/{len(self.pages)}] {path}")
            data = self.fetch_page(path)
            if data:
                pages_data.append(data)
                print(f"    ✓ {data['title'][:40]} ({len(data['paragraphs'])} 段, {len(data['tables'])} 表)")

            if i < len(self.pages) - 1:
                time.sleep(random.uniform(delay, delay + 2))

        kb = {
            "source": self.base_url,
            "scraped_at": datetime.now().isoformat(),
            "total_pages": len(pages_data),
            "pages": pages_data,
        }
        print(f"\n✅ 爬取完成：{len(pages_data)}/{len(self.pages)} 个页面")

        if self._driver:
            self._driver.quit()
            self._driver = None

        return kb

    # ── 保存 ──
    def save(self, knowledge_base: dict, path=KNOWLEDGE_BASE_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
        size_kb = path.stat().st_size / 1024
        print(f"💾 已保存到 {path} ({size_kb:.1f} KB)")

    # ── 转纯文本 ──
    @staticmethod
    def to_plain_text(knowledge_base: dict) -> str:
        parts = []
        for page in knowledge_base["pages"]:
            parts.append(f"\n{'='*60}")
            parts.append(f"页面: {page['title']}")
            parts.append(f"链接: {page['url']}")
            parts.append("=" * 60)
            for p in page["paragraphs"]:
                parts.append(p)
            for ti, table in enumerate(page["tables"]):
                parts.append(f"\n[表格 {ti+1}]")
                for row in table:
                    parts.append(" | ".join(row))
        return "\n".join(parts)


# ══════════════════════════════════════
# CLI
# ══════════════════════════════════════
if __name__ == "__main__":
    method = "auto"
    for i, arg in enumerate(sys.argv):
        if arg == "--method" and i + 1 < len(sys.argv):
            method = sys.argv[i + 1]

    scraper = NinjaParkScraper(method=method)
    kb = scraper.scrape_all()

    if "--dry" in sys.argv:
        print("\n" + NinjaParkScraper.to_plain_text(kb))
    else:
        scraper.save(kb)

    if kb["total_pages"] == 0:
        print()
        print("=" * 60)
        print("⚠️  所有页面抓取失败！请按顺序尝试：")
        print()
        print("  1. pip install cloudscraper")
        print("     python -m scraper.scraper --method cloudscraper")
        print()
        print("  2. pip install selenium webdriver-manager")
        print("     python -m scraper.scraper --method selenium")
        print()
        print("  3. 联系网站管理员将你的 IP 加入白名单")
        print("=" * 60)
