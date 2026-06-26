"""平台浏览器自动化投稿 — 通过 Playwright 模拟作者后台操作

由于所有主流小说平台均无公开作者 API，本模块提供浏览器自动化方案。
支持 Playwright（首选）和 Selenium（备选）。

⚠️ 风险提示：
- 自动化操作可能违反平台协议
- 建议先人工确认平台是否允许
- 首次使用建议手动走一遍流程确认选择器正确
- 频繁自动化操作可能触发风控

使用方式：
1. 用户在浏览器中手动登录平台并保存 Cookie
2. 本系统加载 Cookie 后自动化章节上传
3. 或提供账号密码自动登录（不推荐）
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BrowserPublishConfig:
    """浏览器自动化配置"""
    platform: str
    headless: bool = True
    slow_mo: int = 500        # 操作间隔(ms)，防风控
    timeout: int = 30000      # 页面等待超时(ms)
    cookie_file: str = ""     # Cookie 文件路径
    screenshot_dir: str = ""  # 截图保存目录
    user_data_dir: str = ""   # 浏览器用户数据目录（含登录态）


@dataclass
class PublishStep:
    """投稿步骤结果"""
    step: str
    success: bool
    message: str
    screenshot_path: str = ""
    elapsed_ms: int = 0


class BrowserPublisher(ABC):
    """浏览器自动化投稿基类"""

    def __init__(self, config: BrowserPublishConfig):
        self.config = config
        self._browser = None
        self._context = None
        self._page = None

    @abstractmethod
    async def login(self) -> PublishStep:
        """登录平台"""
        ...

    @abstractmethod
    async def create_work(self, title: str, synopsis: str, genre: str, tags: List[str]) -> PublishStep:
        """创建新作品"""
        ...

    @abstractmethod
    async def upload_chapter(self, chapter_number: int, title: str, content: str) -> PublishStep:
        """上传章节"""
        ...

    @abstractmethod
    async def submit_for_review(self) -> PublishStep:
        """提交审核"""
        ...

    async def upload_novel(
        self,
        title: str,
        synopsis: str,
        genre: str,
        tags: List[str],
        chapters: List[Dict[str, Any]],
        on_progress=None,
    ) -> List[PublishStep]:
        """完整投稿流程"""
        results = []

        # 1. 启动浏览器
        await self._start_browser()

        try:
            # 2. 登录
            step = await self.login()
            results.append(step)
            if not step.success:
                return results

            # 3. 创建作品
            step = await self.create_work(title, synopsis, genre, tags)
            results.append(step)
            if not step.success:
                return results

            # 4. 逐章上传
            for ch in chapters:
                if on_progress:
                    on_progress(ch["number"], len(chapters), f"上传第{ch['number']}章")
                step = await self.upload_chapter(ch["number"], ch["title"], ch["content"])
                results.append(step)
                if not step.success:
                    logger.warning("第%d章上传失败: %s", ch["number"], step.message)

                # 防风控间隔
                await asyncio.sleep(self.config.slow_mo / 1000)

            # 5. 提交审核
            step = await self.submit_for_review()
            results.append(step)

        finally:
            await self._stop_browser()

        return results

    async def _start_browser(self):
        """启动 Playwright 浏览器"""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

            launch_args = {"headless": self.config.headless, "slow_mo": self.config.slow_mo}
            if self.config.user_data_dir:
                # 使用持久化上下文（保留登录态）
                self._context = await self._playwright.chromium.launch_persistent_context(
                    self.config.user_data_dir, **launch_args
                )
                self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            else:
                self._browser = await self._playwright.chromium.launch(**launch_args)
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="zh-CN",
                )
                self._page = await self._context.new_page()

                # 加载 Cookie
                if self.config.cookie_file and os.path.exists(self.config.cookie_file):
                    with open(self.config.cookie_file, "r") as f:
                        cookies = json.load(f)
                    await self._context.add_cookies(cookies)
                    logger.info("已加载 %d 个 Cookie", len(cookies))

            self._page.set_default_timeout(self.config.timeout)
            logger.info("浏览器已启动 (headless=%s)", self.config.headless)

        except ImportError:
            raise RuntimeError(
                "playwright 未安装。请运行:\n"
                "  pip install playwright\n"
                "  playwright install chromium\n"
            )

    async def _stop_browser(self):
        """关闭浏览器"""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if hasattr(self, '_playwright') and self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug("浏览器关闭异常: %s", e)

    async def _screenshot(self, name: str) -> str:
        """截取当前页面截图"""
        if not self.config.screenshot_dir or not self._page:
            return ""
        try:
            os.makedirs(self.config.screenshot_dir, exist_ok=True)
            path = os.path.join(self.config.screenshot_dir, f"{name}.png")
            await self._page.screenshot(path=path)
            return path
        except Exception:
            return ""


class QidianBrowserPublisher(BrowserPublisher):
    """起点中文网浏览器自动化投稿

    作者后台: https://author.qidian.com
    """

    AUTHOR_URL = "https://author.qidian.com"
    CREATE_URL = "https://author.qidian.com/book/write?bookId=0"
    CHAPTER_URL_TEMPLATE = "https://author.qidian.com/chapter/write/{book_id}"

    async def login(self) -> PublishStep:
        """检查登录状态（需预先在浏览器中登录并保存 Cookie）"""
        try:
            await self._page.goto(f"{self.AUTHOR_URL}/mypage", wait_until="networkidle")
            # 检查是否跳转到登录页
            if "login" in self._page.url or "passport" in self._page.url:
                return PublishStep(
                    step="login",
                    success=False,
                    message="未登录。请先在浏览器中手动登录起点，或提供 Cookie 文件。",
                )
            await self._screenshot("qidian_login_ok")
            return PublishStep(step="login", success=True, message="登录状态正常")
        except Exception as e:
            return PublishStep(step="login", success=False, message=f"登录检查失败: {e}")

    async def create_work(self, title: str, synopsis: str, genre: str, tags: List[str]) -> PublishStep:
        """创建新作品"""
        try:
            await self._page.goto(self.CREATE_URL, wait_until="networkidle")
            await asyncio.sleep(1)

            # 填写书名
            await self._page.fill('input[name="bookName"], #bookName', title[:15])
            await asyncio.sleep(0.5)

            # 填写简介
            synopsis_el = await self._page.query_selector(
                'textarea[name="description"], #description, .book-desc textarea'
            )
            if synopsis_el:
                await synopsis_el.fill(synopsis[:200])

            # 选择分类（如果有的话）
            if genre:
                try:
                    await self._page.click('.category-select, #categoryId')
                    await asyncio.sleep(0.5)
                    await self._page.click(f'text="{genre}"')
                except Exception:
                    logger.debug("分类选择跳过")

            # 添加标签
            for tag in tags[:5]:
                try:
                    tag_input = await self._page.query_selector(
                        'input[name="tags"], .tag-input input, #tags'
                    )
                    if tag_input:
                        await tag_input.fill(tag)
                        await tag_input.press("Enter")
                        await asyncio.sleep(0.3)
                except Exception:
                    pass

            # 截图确认
            await self._screenshot("qidian_create_form")

            # 点击创建/提交
            try:
                submit_btn = await self._page.query_selector(
                    'button[type="submit"], .submit-btn, button:has-text("创建")'
                )
                if submit_btn:
                    await submit_btn.click()
                    await self._page.wait_for_load_state("networkidle")
            except Exception:
                pass

            await self._screenshot("qidian_create_done")
            return PublishStep(step="create_work", success=True, message=f"作品「{title}」创建请求已发送")

        except Exception as e:
            await self._screenshot("qidian_create_error")
            return PublishStep(step="create_work", success=False, message=f"创建作品失败: {e}")

    async def upload_chapter(self, chapter_number: int, title: str, content: str) -> PublishStep:
        """上传单个章节"""
        try:
            # 定位章节编辑器
            editor = await self._page.query_selector(
                '.chapter-content textarea, .ql-editor, #chapterContent, [contenteditable="true"]'
            )
            if not editor:
                return PublishStep(
                    step="upload_chapter",
                    success=False,
                    message="未找到章节编辑器，请确认已进入章节编辑页面",
                )

            # 填写标题
            title_el = await self._page.query_selector(
                'input[name="chapterName"], #chapterName, .chapter-title input'
            )
            if title_el:
                await title_el.fill(title[:30])

            # 填写内容
            await editor.fill("")
            await editor.type(content[:50000])  # 安全限制

            await asyncio.sleep(0.5)
            await self._screenshot(f"qidian_ch{chapter_number}")

            # 保存/发布
            save_btn = await self._page.query_selector(
                'button:has-text("发布"), button:has-text("保存"), .publish-btn'
            )
            if save_btn:
                await save_btn.click()
                await asyncio.sleep(2)

            return PublishStep(
                step="upload_chapter",
                success=True,
                message=f"第{chapter_number}章已提交",
            )
        except Exception as e:
            return PublishStep(
                step="upload_chapter",
                success=False,
                message=f"第{chapter_number}章上传失败: {e}",
            )

    async def submit_for_review(self) -> PublishStep:
        """起点无需手动提交审核，章节发布后自动进入审核队列"""
        return PublishStep(
            step="submit_for_review",
            success=True,
            message="起点章节发布后自动进入审核队列，无需额外操作",
        )


# ── 平台工厂 ──

_BROWSER_PUBLISHERS = {
    "qidian": QidianBrowserPublisher,
}


def get_browser_publisher(platform: str, config: BrowserPublishConfig) -> Optional[BrowserPublisher]:
    """获取浏览器自动化投稿器"""
    cls = _BROWSER_PUBLISHERS.get(platform)
    if cls:
        return cls(config)
    return None


def get_supported_browser_platforms() -> List[str]:
    """返回支持浏览器自动化的平台列表"""
    return list(_BROWSER_PUBLISHERS.keys())
