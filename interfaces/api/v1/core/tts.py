"""TTS API — 有声书生成接口

提供章节/整书语音合成功能，基于 edge-tts（免费高质量 TTS）。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


# ── Request / Response Models ──

class TTSRequestModel(BaseModel):
    text: str
    voice_id: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class NovelTTSRequest(BaseModel):
    novel_id: str
    voice_id: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    chapter_start: Optional[int] = None
    chapter_end: Optional[int] = None


class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    language: str
    gender: str
    description: str = ""


# ── Dependency ──

def _get_tts_provider():
    from infrastructure.tts.tts_provider import EdgeTTSProvider
    return EdgeTTSProvider()


# ── Endpoints ──

@router.get("/voices", summary="列出可用语音")
async def list_voices(
    language: str = Query("zh", description="语言过滤 (zh/en/ja/...)"),
    provider=Depends(_get_tts_provider),
):
    """返回可用的 TTS 语音列表。默认只返回中文语音。"""
    if language == "all":
        from infrastructure.tts.tts_provider import EdgeTTSProvider
        voices = await EdgeTTSProvider.list_all_edge_voices()
    else:
        voices = await provider.list_voices(language=language)
    return {
        "voices": [
            VoiceInfo(
                voice_id=v.voice_id,
                name=v.name,
                language=v.language,
                gender=v.gender,
                description=v.description,
            ).model_dump()
            for v in voices
        ]
    }


@router.post("/synthesize", summary="文本转语音")
async def synthesize_text(
    req: TTSRequestModel,
    provider=Depends(_get_tts_provider),
):
    """将文本合成为 MP3 音频。直接返回音频流。"""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")
    if len(req.text) > 50000:
        raise HTTPException(status_code=400, detail="文本过长（最多 50000 字符），请分段合成")

    from infrastructure.tts.tts_provider import TTSRequest
    request = TTSRequest(
        text=req.text,
        voice_id=req.voice_id,
        rate=req.rate,
        volume=req.volume,
        pitch=req.pitch,
    )

    try:
        from infrastructure.tts.tts_provider import _split_text_for_tts

        # 短文本直接合成
        if len(req.text) <= 3000:
            audio_bytes = await provider.synthesize(request)
            return StreamingResponse(
                iter([audio_bytes]),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "attachment; filename=tts_output.mp3"},
            )

        # 长文本流式合成
        async def audio_stream():
            chunks = _split_text_for_tts(req.text)
            for chunk_text in chunks:
                chunk_req = TTSRequest(
                    text=chunk_text,
                    voice_id=req.voice_id,
                    rate=req.rate,
                    volume=req.volume,
                    pitch=req.pitch,
                )
                async for audio_chunk in provider.synthesize_stream(chunk_req):
                    yield audio_chunk

        return StreamingResponse(
            audio_stream(),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=tts_output.mp3"},
        )
    except Exception as e:
        logger.error("TTS 合成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@router.post("/novel/{novel_id}", summary="整书有声书生成")
async def synthesize_novel(
    novel_id: str,
    req: NovelTTSRequest,
    provider=Depends(_get_tts_provider),
):
    """将整本小说合成为有声书 MP3。流式返回。"""
    from interfaces.api.dependencies import get_novel_repository, get_chapter_repository

    novel_repo = get_novel_repository()
    chapter_repo = get_chapter_repository()

    novel = novel_repo.get_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapters = chapter_repo.list_by_novel(novel_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="该小说没有章节")

    # 过滤章节范围
    chapters = sorted(chapters, key=lambda c: c.number)
    if req.chapter_start is not None:
        chapters = [c for c in chapters if c.number >= req.chapter_start]
    if req.chapter_end is not None:
        chapters = [c for c in chapters if c.number <= req.chapter_end]

    if not chapters:
        raise HTTPException(status_code=400, detail="指定范围内没有章节")

    from infrastructure.tts.tts_provider import (
        TTSRequest as TTSReq, synthesize_novel_chapters,
    )

    async def stream_audio():
        try:
            # 逐章合成并流式输出
            for chapter in chapters:
                chapter_text = f"第{chapter.number}章 {chapter.title}\n\n{chapter.content}"
                from infrastructure.tts.tts_provider import _split_text_for_tts
                text_chunks = _split_text_for_tts(chapter_text)

                for text_chunk in text_chunks:
                    tts_req = TTSReq(
                        text=text_chunk,
                        voice_id=req.voice_id,
                        rate=req.rate,
                    )
                    async for audio_chunk in provider.synthesize_stream(tts_req):
                        yield audio_chunk

                # 章节间短暂停顿
                yield b'\x00' * 8000
        except Exception as e:
            logger.error("有声书生成中断: %s", e)
            return

    safe_title = novel.title.replace('/', '_').replace('\\', '_')[:50]
    return StreamingResponse(
        stream_audio(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}_audiobook.mp3",
        },
    )


@router.post("/chapter", summary="单章语音合成")
async def synthesize_chapter(
    novel_id: str = Query(...),
    chapter_number: int = Query(...),
    voice_id: str = Query("zh-CN-XiaoxiaoNeural"),
    rate: str = Query("+0%"),
    provider=Depends(_get_tts_provider),
):
    """合成单个章节为 MP3。"""
    from interfaces.api.dependencies import get_chapter_repository

    chapter_repo = get_chapter_repository()
    chapter = chapter_repo.get_by_novel_and_number(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    chapter_text = f"第{chapter.number}章 {chapter.title}\n\n{chapter.content}"

    from infrastructure.tts.tts_provider import TTSRequest as TTSReq, _split_text_for_tts

    async def audio_stream():
        text_chunks = _split_text_for_tts(chapter_text)
        for chunk_text in text_chunks:
            req = TTSReq(text=chunk_text, voice_id=voice_id, rate=rate)
            async for audio_chunk in provider.synthesize_stream(req):
                yield audio_chunk

    safe_title = f"ch{chapter_number}_{chapter.title}".replace('/', '_')[:50]
    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}.mp3",
        },
    )
