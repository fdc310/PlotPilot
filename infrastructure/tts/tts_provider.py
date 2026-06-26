"""TTS (Text-to-Speech) Provider — 语音合成抽象层

支持多种 TTS 后端：edge-tts (默认，免费高质量)、本地引擎。
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TTSVoice:
    """可用语音描述"""
    voice_id: str
    name: str
    language: str
    gender: str  # "male" / "female" / "unknown"
    preview_url: str = ""
    description: str = ""


@dataclass(frozen=True)
class TTSRequest:
    """语音合成请求"""
    text: str
    voice_id: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"       # 语速: "-50%" ~ "+100%"
    volume: str = "+0%"     # 音量: "-50%" ~ "+100%"
    pitch: str = "+0Hz"     # 音调: "-50Hz" ~ "+50Hz"


@dataclass
class TTSProgress:
    """合成进度回调"""
    current_chunk: int = 0
    total_chunks: int = 0
    audio_bytes: int = 0
    status: str = "processing"  # "processing" / "completed" / "error"
    error: str = ""


class TTSProvider(ABC):
    """TTS 提供者抽象基类"""

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> bytes:
        """合成语音，返回 MP3 字节"""
        ...

    @abstractmethod
    async def list_voices(self, language: str = "zh") -> List[TTSVoice]:
        """列出可用语音"""
        ...

    async def synthesize_stream(self, request: TTSRequest) -> AsyncIterator[bytes]:
        """流式合成（默认回退到整段合成）"""
        data = await self.synthesize(request)
        yield data

    async def aclose(self) -> None:
        """释放资源"""
        pass


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS 提供者 — 免费、高质量、支持中文

    使用 edge-tts 库（https://github.com/rany2/edge-tts）。
    """

    # 常用中文语音预设
    CHINESE_VOICES = [
        ("zh-CN-XiaoxiaoNeural", "晓晓（女，温暖活泼）", "female"),
        ("zh-CN-YunxiNeural", "云希（男，年轻阳光）", "male"),
        ("zh-CN-YunjianNeural", "云健（男，成熟稳重）", "male"),
        ("zh-CN-XiaoyiNeural", "晓艺（女，甜美可爱）", "female"),
        ("zh-CN-YunyangNeural", "云扬（男，专业播报）", "male"),
        ("zh-CN-XiaochenNeural", "晓辰（女，温和知性）", "female"),
        ("zh-CN-XiaohanNeural", "晓涵（女，温柔）", "female"),
        ("zh-CN-XiaomengNeural", "晓梦（女，少女）", "female"),
        ("zh-CN-XiaomoNeural", "晓墨（女，文艺）", "female"),
        ("zh-CN-XiaoruiNeural", "晓睿（女，沉稳）", "female"),
        ("zh-CN-XiaoshuangNeural", "晓双（女，儿童）", "female"),
        ("zh-CN-XiaoxuanNeural", "晓萱（女，活力）", "female"),
        ("zh-CN-XiaoyanNeural", "晓颜（女，温柔）", "female"),
        ("zh-CN-XiaozhenNeural", "晓甄（女，专业）", "female"),
        ("zh-CN-YunfengNeural", "云枫（男，大气）", "male"),
        ("zh-CN-YunhaoNeural", "云皓（男，浑厚）", "male"),
        ("zh-CN-YunxiaNeural", "云夏（男，少年）", "male"),
        ("zh-CN-YunzeNeural", "云泽（男，磁性）", "male"),
        ("zh-TW-HsiaoChenNeural", "曉臻（女，台湾腔）", "female"),
        ("zh-TW-YunJheNeural", "雲喆（男，台湾腔）", "male"),
        ("zh-HK-HiuGaaiNeural", "曉佳（女，粤语）", "female"),
        ("zh-HK-WanLungNeural", "雲龍（男，粤语）", "male"),
    ]

    async def synthesize(self, request: TTSRequest) -> bytes:
        """合成整段文本为 MP3"""
        try:
            import edge_tts
        except ImportError:
            raise RuntimeError("edge-tts 未安装，请运行: pip install edge-tts")

        communicate = edge_tts.Communicate(
            text=request.text,
            voice=request.voice_id,
            rate=request.rate,
            volume=request.volume,
            pitch=request.pitch,
        )

        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])

        result = audio_data.getvalue()
        if not result:
            raise RuntimeError("TTS 合成返回空音频")
        return result

    async def synthesize_stream(self, request: TTSRequest) -> AsyncIterator[bytes]:
        """流式合成 — 实时推送音频块"""
        try:
            import edge_tts
        except ImportError:
            raise RuntimeError("edge-tts 未安装，请运行: pip install edge-tts")

        communicate = edge_tts.Communicate(
            text=request.text,
            voice=request.voice_id,
            rate=request.rate,
            volume=request.volume,
            pitch=request.pitch,
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    async def list_voices(self, language: str = "zh") -> List[TTSVoice]:
        """列出中文语音"""
        voices = []
        for voice_id, name, gender in self.CHINESE_VOICES:
            voices.append(TTSVoice(
                voice_id=voice_id,
                name=name,
                language="zh",
                gender=gender,
                description=name,
            ))
        return voices

    @staticmethod
    async def list_all_edge_voices(language_filter: str = "") -> List[TTSVoice]:
        """从 Edge TTS 服务获取所有可用语音（含非中文）"""
        try:
            import edge_tts
            voices_raw = await edge_tts.list_voices()
        except ImportError:
            return []

        result = []
        for v in voices_raw:
            locale = v.get("Locale", "")
            if language_filter and not locale.startswith(language_filter):
                continue
            result.append(TTSVoice(
                voice_id=v.get("ShortName", ""),
                name=v.get("FriendlyName", ""),
                language=locale,
                gender="female" if v.get("Gender") == "Female" else "male",
            ))
        return result


def _split_text_for_tts(text: str, max_chars: int = 3000) -> List[str]:
    """将长文本切分为适合 TTS 的段落。

    优先在句号/问号/感叹号处切分，保证每段不超过 max_chars。
    """
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r'(?<=[。！？\n])', text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current += sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]


async def synthesize_novel_chapters(
    provider: TTSProvider,
    chapters: list,
    voice_id: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
    on_progress=None,
) -> bytes:
    """合成多个章节为一个完整有声书 MP3。

    Args:
        provider: TTS 提供者
        chapters: 章节列表，需有 number, title, content 属性
        voice_id: 语音 ID
        rate: 语速
        on_progress: 进度回调 (current_chapter, total_chapters, status)

    Returns:
        完整 MP3 字节
    """
    total = len(chapters)
    combined_audio = io.BytesIO()

    for i, chapter in enumerate(chapters):
        if on_progress:
            on_progress(i + 1, total, f"正在合成第 {chapter.number} 章: {chapter.title}")

        # 构建章节文本：标题 + 正文
        chapter_text = f"第{chapter.number}章 {chapter.title}\n\n{chapter.content}"

        # 切分长文本
        text_chunks = _split_text_for_tts(chapter_text)

        for text_chunk in text_chunks:
            request = TTSRequest(
                text=text_chunk,
                voice_id=voice_id,
                rate=rate,
            )
            try:
                audio_bytes = await provider.synthesize(request)
                combined_audio.write(audio_bytes)
            except Exception as e:
                logger.warning("章节 %d TTS 合成失败: %s", chapter.number, e)
                continue

        # 章节间静音间隔（1秒空白）
        combined_audio.write(b'\x00' * 16000)  # ~0.5s silence at 16kHz

    if on_progress:
        on_progress(total, total, "completed")

    return combined_audio.getvalue()
