"""Publishing API — 小说平台投稿接口

提供一键投稿功能：平台格式化导出、元数据校验、投稿包下载。
支持起点中文网、番茄小说、纵横中文网等主流平台。
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publish", tags=["publish"])


# ── Request / Response Models ──

class PublishRequest(BaseModel):
    novel_id: str
    platform: str  # Platform enum value
    synopsis: str = ""
    genre: str = ""
    tags: List[str] = []
    chapter_start: Optional[int] = None
    chapter_end: Optional[int] = None


class PlatformInfo(BaseModel):
    key: str
    name: str
    max_title_length: int
    min_chapter_words: int
    tags_max_count: int


class PublishPreview(BaseModel):
    platform: str
    platform_name: str
    title: str
    author: str
    synopsis: str
    chapter_count: int
    total_words: int
    warnings: List[str]
    tags: List[str]


# ── Endpoints ──

@router.get("/platforms", summary="列出支持的投稿平台")
async def list_platforms():
    """返回所有支持的小说平台及其配置约束。"""
    from infrastructure.publish.platform_adapter import get_all_platforms
    return {"platforms": get_all_platforms()}


@router.post("/preview", summary="投稿预览")
async def preview_publish(req: PublishRequest):
    """预览投稿包内容和校验结果，不生成文件。"""
    from infrastructure.publish.platform_adapter import (
        Platform, build_publish_package,
    )
    from interfaces.api.dependencies import get_novel_repository, get_chapter_repository

    try:
        platform = Platform(req.platform)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {req.platform}")

    novel_repo = get_novel_repository()
    chapter_repo = get_chapter_repository()

    novel = novel_repo.get_by_id(req.novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapters = chapter_repo.list_by_novel(req.novel_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="该小说没有章节")

    chapters = sorted(chapters, key=lambda c: c.number)
    if req.chapter_start is not None:
        chapters = [c for c in chapters if c.number >= req.chapter_start]
    if req.chapter_end is not None:
        chapters = [c for c in chapters if c.number <= req.chapter_end]

    package = await build_publish_package(
        platform=platform,
        novel=novel,
        chapters=chapters,
        synopsis=req.synopsis,
        genre=req.genre,
        tags=req.tags,
    )

    platform_names = {
        "qidian": "起点中文网", "zongheng": "纵横中文网",
        "fanqie": "番茄小说", "jinjiang": "晋江文学城",
        "ciweimao": "刺猬猫", "qimao": "七猫小说", "tadu": "塔读文学",
    }

    return PublishPreview(
        platform=req.platform,
        platform_name=platform_names.get(req.platform, req.platform),
        title=package.metadata.title,
        author=package.metadata.author,
        synopsis=package.metadata.synopsis,
        chapter_count=len(package.chapters),
        total_words=package.metadata.total_words,
        warnings=package.warnings,
        tags=package.metadata.tags,
    ).model_dump()


@router.post("/export", summary="生成投稿包")
async def export_publish_package(req: PublishRequest):
    """生成平台投稿包并下载。包含格式化文本和元数据 JSON。"""
    from infrastructure.publish.platform_adapter import (
        Platform, build_publish_package,
    )
    from interfaces.api.dependencies import get_novel_repository, get_chapter_repository

    try:
        platform = Platform(req.platform)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {req.platform}")

    novel_repo = get_novel_repository()
    chapter_repo = get_chapter_repository()

    novel = novel_repo.get_by_id(req.novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapters = chapter_repo.list_by_novel(req.novel_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="该小说没有章节")

    chapters = sorted(chapters, key=lambda c: c.number)
    if req.chapter_start is not None:
        chapters = [c for c in chapters if c.number >= req.chapter_start]
    if req.chapter_end is not None:
        chapters = [c for c in chapters if c.number <= req.chapter_end]

    package = await build_publish_package(
        platform=platform,
        novel=novel,
        chapters=chapters,
        synopsis=req.synopsis,
        genre=req.genre,
        tags=req.tags,
    )

    # 构建 ZIP 包
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 格式化文本
        if package.formatted_content:
            zf.writestr(package.formatted_filename, package.formatted_content)

        # 元数据
        if package.metadata_json:
            zf.writestr("metadata.json", package.metadata_json)

        # 分章文件
        chapters_dir = "chapters/"
        for ch in package.chapters:
            chapter_filename = f"ch{ch.number:04d}_{ch.title[:30].replace('/', '_')}.txt"
            zf.writestr(
                chapters_dir + chapter_filename,
                ch.title + "\n\n" + ch.content,
            )

        # 投稿指南
        guide = _generate_submit_guide(req.platform, package)
        zf.writestr("投稿指南.txt", guide)

        # 校验报告
        if package.warnings:
            zf.writestr("校验报告.txt", "校验结果：\n\n" + "\n".join(
                f"⚠ {w}" for w in package.warnings
            ))

    zip_buffer.seek(0)
    safe_title = novel.title.replace('/', '_').replace('\\', '_')[:50]
    filename = f"{safe_title}_{req.platform}_投稿包.zip"

    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


def _generate_submit_guide(platform: str, package) -> str:
    """生成投稿操作指南"""
    platform_name = {
        "qidian": "起点中文网 (qidian.com)",
        "zongheng": "纵横中文网 (zongheng.com)",
        "fanqie": "番茄小说 (fanqie.com)",
        "jinjiang": "晋江文学城 (jjwxc.net)",
        "ciweimao": "刺猬猫 (ciweimao.com)",
        "qimao": "七猫小说 (qimao.com)",
        "tadu": "塔读文学 (tadu.com)",
    }.get(platform, platform)

    guides = {
        "qidian": [
            "1. 登录 qidian.com，进入「作家专区」",
            "2. 点击「创建作品」，填写书名、类型、简介",
            "3. 创建成功后进入「作品管理」→「新增章节」",
            "4. 将 chapters/ 目录下的章节内容逐章粘贴到编辑器",
            "5. 建议首次上传 3-5 章，每章 2000-3000 字",
            "6. 标签建议从 metadata.json 中复制",
        ],
        "fanqie": [
            "1. 下载番茄小说 APP 或访问 writer.fanqie.com",
            "2. 注册成为作者，创建新作品",
            "3. 填写作品信息（参考 metadata.json）",
            "4. 逐章上传章节内容",
            "5. 番茄对格式要求宽松，直接粘贴正文即可",
            "6. 保持每日更新有助于获得推荐",
        ],
        "zongheng": [
            "1. 访问 zongheng.com，注册作者账号",
            "2. 进入「作者后台」→「新建作品」",
            "3. 填写作品信息",
            "4. 逐章上传，建议每章 2000-4000 字",
        ],
    }

    lines = [
        f"=== {platform_name} 投稿指南 ===",
        "",
        f"书名：{package.metadata.title}",
        f"作者：{package.metadata.author}",
        f"章节数：{len(package.chapters)}",
        f"总字数：{package.metadata.total_words}",
        "",
        "--- 操作步骤 ---",
        "",
    ]

    guide_steps = guides.get(platform, [
        f"1. 登录 {platform_name} 作者后台",
        "2. 创建新作品，填写书名、简介、类型等信息",
        "3. 将 chapters/ 目录下的章节逐章上传",
        "4. 参考 metadata.json 中的标签和简介",
    ])
    lines.extend(guide_steps)

    if package.warnings:
        lines.extend([
            "",
            "--- 校验提醒 ---",
        ])
        for w in package.warnings:
            lines.append(f"⚠ {w}")

    return "\n".join(lines)


# ── 浏览器自动化投稿 ──

class BrowserPublishRequest(BaseModel):
    novel_id: str
    platform: str
    cookie_file: str = ""       # Cookie JSON 文件路径
    user_data_dir: str = ""     # 浏览器用户数据目录（保留登录态）
    headless: bool = True
    slow_mo: int = 500          # 操作间隔(ms)
    chapter_start: Optional[int] = None
    chapter_end: Optional[int] = None


@router.get("/browser-platforms", summary="支持浏览器自动化的平台")
async def list_browser_platforms():
    """返回支持浏览器自动化投稿的平台列表。"""
    from infrastructure.publish.browser_publisher import get_supported_browser_platforms
    return {
        "platforms": get_supported_browser_platforms(),
        "notice": "所有主流小说平台均无公开作者API，浏览器自动化需预先登录。",
        "requirements": "pip install playwright && playwright install chromium",
    }


@router.post("/browser-auto", summary="浏览器自动化投稿")
async def browser_auto_publish(req: BrowserPublishRequest):
    """通过浏览器自动化上传章节到目标平台。

    前置条件：
    1. 安装 playwright: pip install playwright && playwright install chromium
    2. 提供已登录的 Cookie 文件或浏览器用户数据目录
    3. 首次建议 headless=false 观察操作过程

    ⚠️ 风险提示：自动化操作可能违反平台协议，请自行评估。
    """
    from infrastructure.publish.browser_publisher import (
        BrowserPublishConfig, get_browser_publisher,
    )
    from infrastructure.publish.platform_adapter import Platform, build_publish_package
    from interfaces.api.dependencies import get_novel_repository, get_chapter_repository

    # 获取浏览器发布器
    config = BrowserPublishConfig(
        platform=req.platform,
        headless=req.headless,
        slow_mo=req.slow_mo,
        cookie_file=req.cookie_file,
        user_data_dir=req.user_data_dir,
        screenshot_dir="data/publish_screenshots",
    )
    publisher = get_browser_publisher(req.platform, config)
    if not publisher:
        raise HTTPException(
            status_code=400,
            detail=f"平台 {req.platform} 暂不支持浏览器自动化。支持的平台: qidian",
        )

    # 获取小说数据
    novel_repo = get_novel_repository()
    chapter_repo = get_chapter_repository()

    novel = novel_repo.get_by_id(req.novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapters = chapter_repo.list_by_novel(req.novel_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="该小说没有章节")

    chapters = sorted(chapters, key=lambda c: c.number)
    if req.chapter_start is not None:
        chapters = [c for c in chapters if c.number >= req.chapter_start]
    if req.chapter_end is not None:
        chapters = [c for c in chapters if c.number <= req.chapter_end]

    chapter_dicts = [
        {"number": c.number, "title": c.title, "content": c.content}
        for c in chapters
    ]

    # 执行自动化投稿
    try:
        results = await publisher.upload_novel(
            title=novel.title,
            synopsis=novel.premise or "",
            genre=getattr(novel, "genre", "") or "",
            tags=getattr(novel, "tags", []) or [],
            chapters=chapter_dicts,
        )

        return {
            "platform": req.platform,
            "total_steps": len(results),
            "success_count": sum(1 for r in results if r.success),
            "fail_count": sum(1 for r in results if not r.success),
            "steps": [
                {
                    "step": r.step,
                    "success": r.success,
                    "message": r.message,
                    "screenshot": r.screenshot_path,
                }
                for r in results
            ],
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("浏览器自动化投稿失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"投稿失败: {str(e)}")
