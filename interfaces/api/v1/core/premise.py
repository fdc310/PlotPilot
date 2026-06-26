"""Premise AI — 从简短创意自动生成完整书目配置

接受一句话/一段话创意，通过 LLM 自动生成：
- 类型标签 (genre)
- 世界观基调 (worldPreset)
- 剧情结构 (storyStructure)
- 节奏把控 (pacingControl)
- 写作风格 (writingStyle)
- 特殊要求 (specialRequirements)
- 建议书名 (title)
- 建议篇幅 (suggested_chapters, suggested_words_per_chapter)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/premise", tags=["premise"])


class PremiseGenerateRequest(BaseModel):
    premise: str
    genre_hint: str = ""  # 可选：用户已选的大类提示


class PremiseGenerateResponse(BaseModel):
    title: str = ""
    genre: str = ""
    world_preset: str = ""
    story_structure: str = ""
    pacing_control: str = ""
    writing_style: str = ""
    special_requirements: str = ""
    suggested_chapters: int = 100
    suggested_words_per_chapter: int = 2500


@router.post("/generate", summary="AI 生成完整书目配置")
async def generate_premise_config(req: PremiseGenerateRequest) -> dict:
    """从简短创意自动生成所有书目配置字段。"""
    if not req.premise.strip():
        raise HTTPException(status_code=400, detail="premise 不能为空")

    # 尝试获取 LLM 服务
    try:
        from interfaces.api.dependencies import get_llm_service
        llm_service = get_llm_service()
    except Exception:
        raise HTTPException(status_code=500, detail="LLM 服务不可用，请先配置模型引擎")

    if not llm_service:
        raise HTTPException(status_code=500, detail="LLM 服务不可用，请先配置模型引擎")

    system_prompt = """你是一位资深网文编辑和创作顾问。用户会给你一个故事创意（可能只有一句话），你需要根据这个创意生成完整的书目配置。

请严格按以下 JSON 格式输出，不要输出其他内容：

```json
{
  "title": "建议书名（10字以内，抓眼球）",
  "genre": "大类/细分主题，如：玄幻/都市修仙、科幻/星际文明、网游/虚拟网游",
  "world_preset": "世界观基调（100-200字）：描述这个故事的世界设定、核心规则、独特元素",
  "story_structure": "剧情结构（200-400字）：开篇、发展、高潮、结尾四段式框架，每段说明切入点、推进方式和关键场景",
  "pacing_control": "节奏把控（200-400字）：小爽点、中爽点、大爽点的排布策略，说明触发条件和位置",
  "writing_style": "写作风格（200-400字）：叙事方式、环境描写、人物对话三个方面的要求",
  "special_requirements": "特殊要求（200-400字）：题材承诺、冲突要求、人物要求、禁忌事项",
  "suggested_chapters": 100,
  "suggested_words_per_chapter": 2500
}
```

要求：
1. 所有文本字段必须是中文
2. 内容要具体、可执行，不能泛泛而谈
3. 要体现该题材的爽点核心和读者期待
4. 如果用户提供了类型提示，优先参考"""

    user_prompt = f"故事创意：{req.premise.strip()}"
    if req.genre_hint.strip():
        user_prompt += f"\n\n类型提示：{req.genre_hint.strip()}"

    try:
        from domain.ai.value_objects.prompt import Prompt
        from domain.ai.services.llm_service import GenerationConfig

        prompt = Prompt(system=system_prompt, user=user_prompt)
        config = GenerationConfig(
            max_tokens=4096,
            temperature=0.8,
        )

        result = await llm_service.generate(prompt, config)
        content = result.content.strip()

        # 解析 JSON
        parsed = _parse_json_response(content)
        if not parsed:
            raise HTTPException(status_code=500, detail="AI 返回格式解析失败，请重试")

        return PremiseGenerateResponse(
            title=parsed.get("title", ""),
            genre=parsed.get("genre", ""),
            world_preset=parsed.get("world_preset", ""),
            story_structure=parsed.get("story_structure", ""),
            pacing_control=parsed.get("pacing_control", ""),
            writing_style=parsed.get("writing_style", ""),
            special_requirements=parsed.get("special_requirements", ""),
            suggested_chapters=parsed.get("suggested_chapters", 100),
            suggested_words_per_chapter=parsed.get("suggested_words_per_chapter", 2500),
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI 生成书目配置失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI 生成失败: {str(e)}")


def _parse_json_response(text: str) -> Optional[dict]:
    """从 LLM 输出中提取 JSON。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown code block 中提取
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找第一个 { 到最后一个 }
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None
