"""小说平台投稿系统 — 多平台适配器

支持起点中文网、纵横中文网、番茄小说、晋江文学城等主流平台。

投递方式：
1. 【格式化导出】生成平台规范的投稿包（TXT + 分章 + 元数据 + 投稿指南）
2. 【浏览器自动化】通过 Selenium/Playwright 自动登录作者后台、粘贴章节、发布

注意：所有主流小说平台均无公开作者投稿 API，仅支持网页后台操作。
浏览器自动化需用户提供登录凭证（Cookie/账号密码），且存在合规风险。
"""
from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Platform(str, Enum):
    """支持的小说平台"""
    QIDIAN = "qidian"           # 起点中文网
    ZONGHENG = "zongheng"       # 纵横中文网
    FANQIE = "fanqie"          # 番茄小说
    JINJIANG = "jinjiang"       # 晋江文学城
    CIWEIMAO = "ciweimao"      # 刺猬猫
    QIMAO = "qimao"            # 七猫小说
    TADU = "tadu"              # 塔读文学
    CUSTOM = "custom"           # 自定义格式


@dataclass
class PlatformConfig:
    """平台投稿配置"""
    platform: Platform
    max_title_length: int = 30
    max_chapter_title_length: int = 50
    max_synopsis_length: int = 300
    min_chapter_words: int = 1000
    max_chapter_words: int = 30000
    encoding: str = "utf-8"
    supports_serialization: bool = True   # 是否支持分章节上传
    requires_chapter_prefix: bool = True  # 是否需要"第X章"前缀
    allowed_genres: List[str] = field(default_factory=list)
    tags_max_count: int = 5
    line_separator: str = "\n"
    paragraph_indent: str = "　　"  # 全角空格两格缩进


@dataclass
class PublishMetadata:
    """投稿元数据"""
    title: str
    author: str
    synopsis: str
    genre: str = ""
    tags: List[str] = field(default_factory=list)
    encoding: str = "utf-8"
    is_completed: bool = False
    total_words: int = 0
    language: str = "zh"


@dataclass
class PublishChapter:
    """投稿章节"""
    number: int
    title: str
    content: str
    word_count: int = 0


@dataclass
class PublishPackage:
    """投稿包 — 包含格式化后的小说数据"""
    platform: Platform
    metadata: PublishMetadata
    chapters: List[PublishChapter]
    formatted_content: Optional[bytes] = None
    formatted_filename: str = ""
    warnings: List[str] = field(default_factory=list)
    metadata_json: Optional[str] = None


# ── 平台配置常量 ──

PLATFORM_CONFIGS: Dict[Platform, PlatformConfig] = {
    Platform.QIDIAN: PlatformConfig(
        platform=Platform.QIDIAN,
        max_title_length=15,
        max_chapter_title_length=30,
        max_synopsis_length=200,
        min_chapter_words=2000,
        tags_max_count=5,
        allowed_genres=["玄幻", "奇幻", "武侠", "仙侠", "都市", "现实",
                       "军事", "历史", "游戏", "体育", "科幻", "悬疑",
                       "灵异", "同人", "轻小说"],
    ),
    Platform.ZONGHENG: PlatformConfig(
        platform=Platform.ZONGHENG,
        max_title_length=20,
        max_chapter_title_length=40,
        max_synopsis_length=300,
        min_chapter_words=1500,
        tags_max_count=8,
    ),
    Platform.FANQIE: PlatformConfig(
        platform=Platform.FANQIE,
        max_title_length=20,
        max_chapter_title_length=30,
        max_synopsis_length=200,
        min_chapter_words=1000,
        tags_max_count=3,
        requires_chapter_prefix=False,
    ),
    Platform.JINJIANG: PlatformConfig(
        platform=Platform.JINJIANG,
        max_title_length=15,
        max_chapter_title_length=30,
        max_synopsis_length=100,
        min_chapter_words=3000,
        tags_max_count=5,
    ),
    Platform.CIWEIMAO: PlatformConfig(
        platform=Platform.CIWEIMAO,
        max_title_length=20,
        max_chapter_title_length=40,
        max_synopsis_length=300,
        min_chapter_words=2000,
        tags_max_count=6,
    ),
    Platform.QIMAO: PlatformConfig(
        platform=Platform.QIMAO,
        max_title_length=20,
        max_chapter_title_length=30,
        max_synopsis_length=200,
        min_chapter_words=1000,
        tags_max_count=3,
    ),
    Platform.TADU: PlatformConfig(
        platform=Platform.TADU,
        max_title_length=20,
        max_chapter_title_length=30,
        max_synopsis_length=200,
        min_chapter_words=1500,
        tags_max_count=5,
    ),
    Platform.CUSTOM: PlatformConfig(
        platform=Platform.CUSTOM,
        max_title_length=100,
        max_chapter_title_length=100,
        max_synopsis_length=10000,
        min_chapter_words=0,
        tags_max_count=99,
        requires_chapter_prefix=False,
    ),
}


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    def __init__(self, config: PlatformConfig):
        self.config = config

    @abstractmethod
    def format_chapter_title(self, number: int, title: str) -> str:
        """格式化章节标题"""
        ...

    @abstractmethod
    def format_paragraph(self, text: str) -> str:
        """格式化段落"""
        ...

    @abstractmethod
    def validate_metadata(self, metadata: PublishMetadata) -> List[str]:
        """验证元数据，返回警告列表"""
        ...

    @abstractmethod
    def build_package(
        self, metadata: PublishMetadata, chapters: List[PublishChapter]
    ) -> PublishPackage:
        """构建投稿包"""
        ...

    def format_content(self, content: str) -> str:
        """格式化正文内容"""
        paragraphs = content.split("\n")
        formatted = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                formatted.append("")
                continue
            formatted.append(self.config.paragraph_indent + p)
        return self.config.line_separator.join(formatted)


class QidianAdapter(PlatformAdapter):
    """起点中文网适配器"""

    def format_chapter_title(self, number: int, title: str) -> str:
        return f"第{self._to_chinese_number(number)}章 {title}"

    def format_paragraph(self, text: str) -> str:
        return self.config.paragraph_indent + text

    def validate_metadata(self, metadata: PublishMetadata) -> List[str]:
        warnings = []
        if len(metadata.title) > self.config.max_title_length:
            warnings.append(f"标题过长（{len(metadata.title)}字），起点限制{self.config.max_title_length}字")
        if len(metadata.synopsis) > self.config.max_synopsis_length:
            warnings.append(f"简介过长，起点限制{self.config.max_synopsis_length}字")
        if not metadata.tags:
            warnings.append("建议添加标签（最多5个）")
        if len(metadata.tags) > self.config.tags_max_count:
            warnings.append(f"标签过多（{len(metadata.tags)}个），起点限制{self.config.tags_max_count}个")
        return warnings

    def build_package(self, metadata: PublishMetadata, chapters: List[PublishChapter]) -> PublishPackage:
        warnings = self.validate_metadata(metadata)

        # 格式化所有章节
        formatted_chapters = []
        for ch in chapters:
            if ch.word_count < self.config.min_chapter_words:
                warnings.append(f"第{ch.number}章字数不足（{ch.word_count}字），建议≥{self.config.min_chapter_words}字")
            formatted_chapters.append(PublishChapter(
                number=ch.number,
                title=self.format_chapter_title(ch.number, ch.title),
                content=self.format_content(ch.content),
                word_count=ch.word_count,
            ))

        # 生成 TXT 包
        txt_content = self._build_txt(metadata, formatted_chapters)
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', metadata.title)[:50]

        return PublishPackage(
            platform=Platform.QIDIAN,
            metadata=metadata,
            chapters=formatted_chapters,
            formatted_content=txt_content.encode("utf-8"),
            formatted_filename=f"{safe_title}_起点投稿.txt",
            warnings=warnings,
            metadata_json=json.dumps({
                "platform": "qidian",
                "title": metadata.title[:self.config.max_title_length],
                "author": metadata.author,
                "synopsis": metadata.synopsis[:self.config.max_synopsis_length],
                "genre": metadata.genre,
                "tags": metadata.tags[:self.config.tags_max_count],
                "total_words": sum(c.word_count for c in chapters),
                "chapter_count": len(chapters),
            }, ensure_ascii=False, indent=2),
        )

    def _build_txt(self, metadata: PublishMetadata, chapters: List[PublishChapter]) -> str:
        lines = [
            f"书名：{metadata.title}",
            f"作者：{metadata.author}",
            f"简介：{metadata.synopsis}",
            f"类型：{metadata.genre}",
            f"标签：{', '.join(metadata.tags)}",
            "",
            "=" * 40,
            "",
        ]
        for ch in chapters:
            lines.append(ch.title)
            lines.append("")
            lines.append(ch.content)
            lines.append("")
            lines.append("=" * 40)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _to_chinese_number(n: int) -> str:
        """数字转中文（1-9999）"""
        if n <= 0:
            return str(n)
        digits = "零一二三四五六七八九"
        if n < 10:
            return digits[n]
        if n < 100:
            tens, ones = divmod(n, 10)
            if ones == 0:
                return digits[tens] + "十"
            return digits[tens] + "十" + digits[ones]
        if n < 10000:
            parts = []
            if n >= 1000:
                parts.append(digits[n // 1000] + "千")
                n %= 1000
            if n >= 100:
                parts.append(digits[n // 100] + "百")
                n %= 100
            if n >= 10:
                tens, ones = divmod(n, 10)
                parts.append(digits[tens] + "十")
                if ones:
                    parts.append(digits[ones])
            elif n > 0:
                parts.append(digits[n])
            return "".join(parts)
        return str(n)


class FanqieAdapter(PlatformAdapter):
    """番茄小说适配器 — 番茄对格式要求较宽松"""

    def format_chapter_title(self, number: int, title: str) -> str:
        return title  # 番茄不要求"第X章"前缀

    def format_paragraph(self, text: str) -> str:
        return text  # 番茄不要求缩进

    def validate_metadata(self, metadata: PublishMetadata) -> List[str]:
        warnings = []
        if len(metadata.title) > self.config.max_title_length:
            warnings.append(f"标题过长，番茄限制{self.config.max_title_length}字")
        if not metadata.genre:
            warnings.append("请填写作品类型")
        return warnings

    def build_package(self, metadata: PublishMetadata, chapters: List[PublishChapter]) -> PublishPackage:
        warnings = self.validate_metadata(metadata)
        formatted_chapters = []
        for ch in chapters:
            formatted_chapters.append(PublishChapter(
                number=ch.number,
                title=ch.title,
                content=ch.content,
                word_count=ch.word_count,
            ))

        safe_title = re.sub(r'[\\/:*?"<>|]', '_', metadata.title)[:50]
        return PublishPackage(
            platform=Platform.FANQIE,
            metadata=metadata,
            chapters=formatted_chapters,
            metadata_json=json.dumps({
                "platform": "fanqie",
                "title": metadata.title,
                "author": metadata.author,
                "synopsis": metadata.synopsis,
                "genre": metadata.genre,
                "tags": metadata.tags[:3],
            }, ensure_ascii=False, indent=2),
            warnings=warnings,
            formatted_filename=f"{safe_title}_番茄投稿.txt",
            formatted_content=self._build_txt(metadata, formatted_chapters).encode("utf-8"),
        )

    def _build_txt(self, metadata: PublishMetadata, chapters: List[PublishChapter]) -> str:
        lines = [f"{metadata.title}\n{metadata.author}\n\n{metadata.synopsis}\n\n"]
        for ch in chapters:
            lines.append(ch.title)
            lines.append("")
            lines.append(ch.content)
            lines.append("\n\n")
        return "\n".join(lines)


class GenericAdapter(PlatformAdapter):
    """通用适配器 — 适用于没有特殊要求的平台"""

    def format_chapter_title(self, number: int, title: str) -> str:
        if self.config.requires_chapter_prefix:
            return f"第{number}章 {title}"
        return title

    def format_paragraph(self, text: str) -> str:
        return self.config.paragraph_indent + text

    def validate_metadata(self, metadata: PublishMetadata) -> List[str]:
        warnings = []
        if len(metadata.title) > self.config.max_title_length:
            warnings.append(f"标题过长（{len(metadata.title)}字）")
        if len(metadata.synopsis) > self.config.max_synopsis_length:
            warnings.append(f"简介过长")
        return warnings

    def build_package(self, metadata: PublishMetadata, chapters: List[PublishChapter]) -> PublishPackage:
        warnings = self.validate_metadata(metadata)
        formatted_chapters = []
        for ch in chapters:
            formatted_chapters.append(PublishChapter(
                number=ch.number,
                title=self.format_chapter_title(ch.number, ch.title),
                content=self.format_content(ch.content),
                word_count=ch.word_count,
            ))

        safe_title = re.sub(r'[\\/:*?"<>|]', '_', metadata.title)[:50]
        txt_lines = [f"{metadata.title}\n{metadata.author}\n\n"]
        for ch in formatted_chapters:
            txt_lines.append(ch.title + "\n\n" + ch.content + "\n\n")

        return PublishPackage(
            platform=self.config.platform,
            metadata=metadata,
            chapters=formatted_chapters,
            formatted_content="\n".join(txt_lines).encode("utf-8"),
            formatted_filename=f"{safe_title}_{self.config.platform.value}.txt",
            warnings=warnings,
        )


# ── 工厂 ──

_ADAPTER_MAP = {
    Platform.QIDIAN: QidianAdapter,
    Platform.FANQIE: FanqieAdapter,
}


def get_adapter(platform: Platform) -> PlatformAdapter:
    """获取平台适配器"""
    config = PLATFORM_CONFIGS.get(platform, PLATFORM_CONFIGS[Platform.CUSTOM])
    adapter_cls = _ADAPTER_MAP.get(platform, GenericAdapter)
    return adapter_cls(config)


def get_all_platforms() -> List[Dict[str, Any]]:
    """返回所有支持的平台信息"""
    platforms = []
    for p in Platform:
        if p == Platform.CUSTOM:
            continue
        config = PLATFORM_CONFIGS.get(p)
        if config:
            platforms.append({
                "key": p.value,
                "name": {
                    "qidian": "起点中文网",
                    "zongheng": "纵横中文网",
                    "fanqie": "番茄小说",
                    "jinjiang": "晋江文学城",
                    "ciweimao": "刺猬猫",
                    "qimao": "七猫小说",
                    "tadu": "塔读文学",
                    "custom": "自定义",
                }.get(p.value, p.value),
                "max_title_length": config.max_title_length,
                "min_chapter_words": config.min_chapter_words,
                "tags_max_count": config.tags_max_count,
            })
    return platforms


async def build_publish_package(
    platform: Platform,
    novel,
    chapters: list,
    synopsis: str = "",
    genre: str = "",
    tags: Optional[List[str]] = None,
) -> PublishPackage:
    """构建投稿包的便捷函数。

    Args:
        platform: 目标平台
        novel: 小说实体（需有 title, author, premise）
        chapters: 章节列表（需有 number, title, content, word_count）
        synopsis: 简介（默认用 premise）
        genre: 类型
        tags: 标签列表

    Returns:
        PublishPackage
    """
    metadata = PublishMetadata(
        title=novel.title,
        author=novel.author or "佚名",
        synopsis=synopsis or novel.premise or "",
        genre=genre,
        tags=tags or [],
        total_words=sum(getattr(c, 'word_count', len(getattr(c, 'content', '') or '')) for c in chapters),
    )

    pub_chapters = []
    for ch in chapters:
        content = getattr(ch, 'content', '') or ''
        pub_chapters.append(PublishChapter(
            number=ch.number,
            title=ch.title or f"第{ch.number}章",
            content=content,
            word_count=getattr(ch, 'word_count', None) or len(content),
        ))

    adapter = get_adapter(platform)
    return adapter.build_package(metadata, pub_chapters)
