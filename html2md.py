#!/usr/bin/env python3
"""
web2md.py — 网页内容抓取并转换为 Markdown 文档
用法：
    python web2md.py                          # 交互式输入网址
    python web2md.py https://example.com      # 直接传入网址
    python web2md.py -o my_file.md <url>      # 指定输出文件名
"""

import sys
import os
import re
import time
import argparse
from urllib.parse import urlparse
from datetime import datetime


# ── 依赖检测 ──────────────────────────────────────────────────────────────────

def check_and_install(packages: dict):
    """检查并提示安装缺失依赖"""
    import importlib
    missing = []
    for import_name, pip_name in packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"[!] 缺少依赖，请先安装：\n    pip install {' '.join(missing)}\n")
        sys.exit(1)

check_and_install({
    "requests":      "requests",
    "bs4":           "beautifulsoup4",
    "markdownify":   "markdownify",
    "readability":   "readability-lxml",
})

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from readability import Document


# ── 常量 ──────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = 20  # 秒


# ── 核心函数 ──────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> tuple[str, str]:
    """
    下载网页，返回 (html内容, 最终URL)
    支持自动重试一次
    """
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text, resp.url
        except requests.exceptions.SSLError:
            # 降级：跳过SSL验证
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                                allow_redirects=True, verify=False)
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text, resp.url
        except requests.exceptions.ConnectionError as e:
            if attempt == 0:
                print(f"  连接失败，1秒后重试…")
                time.sleep(1)
            else:
                raise RuntimeError(f"无法连接到 {url}：{e}") from e
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP 错误 {e.response.status_code}：{url}") from e


def extract_main_content(html: str, url: str) -> tuple[str, str, str]:
    """
    用 readability-lxml 提取正文，返回 (title, summary, content_html)
    """
    doc = Document(html)
    title = doc.title() or "无标题"
    summary_html = doc.summary(html_partial=True)

    # 用 BeautifulSoup 进一步清理
    soup = BeautifulSoup(summary_html, "lxml")

    # 删除无用元素
    for tag in soup(["script", "style", "iframe", "noscript",
                     "aside", "nav", "footer", "header",
                     "form", "button", "input", "svg"]):
        tag.decompose()

    # 删除纯广告 class（常见模式）
    ad_patterns = re.compile(
        r"(ad|ads|advert|banner|sponsor|promo|sidebar|recommend|related|comment)",
        re.I
    )
    for tag in soup.find_all(True):
        classes = " ".join(tag.get("class", []))
        ids = tag.get("id", "")
        if ad_patterns.search(classes) or ad_patterns.search(ids):
            tag.decompose()

    # 补全相对链接（可选）
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            a["href"] = base + href

    return title, soup.get_text()[:200].strip(), str(soup)


def html_to_markdown(title: str, content_html: str, source_url: str) -> str:
    """将 HTML 转换为格式化的 Markdown"""
    body_md = md(
        content_html,
        heading_style="ATX",        # # 风格标题
        bullets="-",                 # 无序列表用 -
        strip=["a"],                 # 去掉超链接（保留文字）
        newline_style="backslash",
    )

    # 后处理：压缩超过2个的空行
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)
    # 去掉行首尾多余空格
    body_md = "\n".join(line.rstrip() for line in body_md.splitlines())
    # 去掉只含空白的行首尾
    body_md = body_md.strip()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (
        f"# {title}\n\n"
        f"> **来源：** {source_url}  \n"
        f"> **抓取时间：** {now}\n\n"
        f"---\n\n"
    )
    return header + body_md


def safe_filename(title: str, url: str) -> str:
    """根据标题生成合法文件名"""
    # 优先用标题
    name = title or urlparse(url).path.strip("/").replace("/", "_") or "output"
    # 去除不合法字符
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    # 截断过长文件名
    if len(name) > 60:
        name = name[:60]
    return name + ".md"


def save_markdown(content: str, filepath: str):
    """保存 Markdown 文件"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def process(url: str, output: str | None = None) -> str:
    """完整流程：抓取 → 提取 → 转换 → 保存，返回保存路径"""

    print(f"\n{'='*55}")
    print(f"  目标：{url}")
    print(f"{'='*55}")

    # 1. 下载
    print("  ① 正在下载网页…", end="", flush=True)
    html, final_url = fetch_html(url)
    print(f" ✓ ({len(html):,} 字节)")

    # 2. 提取正文
    print("  ② 正在提取正文…", end="", flush=True)
    title, preview, content_html = extract_main_content(html, final_url)
    print(f" ✓  标题：{title[:50]}")

    # 3. 转 Markdown
    print("  ③ 正在转换 Markdown…", end="", flush=True)
    markdown = html_to_markdown(title, content_html, final_url)
    print(f" ✓ ({len(markdown):,} 字符)")

    # 4. 保存
    filepath = output if output else safe_filename(title, final_url)
    save_markdown(markdown, filepath)
    abs_path = os.path.abspath(filepath)
    print(f"  ④ 已保存 → {abs_path}")
    print(f"{'='*55}\n")
    return abs_path


def main():
    parser = argparse.ArgumentParser(
        description="抓取网页正文并转换为 Markdown 文档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", nargs="?", help="目标网址")
    parser.add_argument("-o", "--output", help="输出文件名（默认自动生成）")
    args = parser.parse_args()

    url = args.url
    if not url:
        url = input("请输入网址：").strip()
    if not url:
        print("[!] 未输入网址，退出。")
        sys.exit(1)

    # 自动补全 scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        saved = process(url, args.output)
        print(f"完成！文件路径：{saved}")
    except RuntimeError as e:
        print(f"\n错误：{e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[中断] 用户取消。")
        sys.exit(0)


if __name__ == "__main__":
    main()