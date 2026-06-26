"""bible_delegate — 自动 Bible 生成阶段

在 autopilot 全托管模式下，自动调用 AutoBibleGenerator 分阶段生成
世界观（五维度）→ 角色 → 地点，完成后再进入 MACRO_PLANNING。
"""
from __future__ import annotations

import logging
from typing import Any

from domain.novel.entities.novel import Novel, NovelStage, AutoAILevel

logger = logging.getLogger(__name__)


async def run_bible_generation(host: Any, novel: Novel) -> None:
    """自动生成完整 Bible（世界观 + 角色 + 地点）。"""
    novel_id = str(novel.novel_id)

    # 检查自动化级别
    auto_level = getattr(novel, "auto_ai_level", AutoAILevel.CONSERVATIVE)
    if isinstance(auto_level, str):
        auto_level = AutoAILevel(auto_level)

    if auto_level == AutoAILevel.CONSERVATIVE:
        logger.info("[%s] conservative 模式：跳过自动 Bible 生成，转为 macro_planning", novel_id)
        novel.current_stage = NovelStage.MACRO_PLANNING
        host._save_novel_state(novel)
        return

    # 更新共享状态
    host._update_shared_state(
        novel_id,
        current_stage="bible_generation",
        bible_generation_status="starting",
    )

    llm_service = getattr(host, "llm_service", None)
    if not llm_service:
        logger.warning("[%s] 无 LLM 服务，跳过 Bible 生成", novel_id)
        novel.current_stage = NovelStage.MACRO_PLANNING
        host._save_novel_state(novel)
        return

    try:
        from infrastructure.persistence.database.connection import get_database
        from application.world.services.auto_bible_generator import AutoBibleGenerator
        from application.world.services.bible_service import BibleService
        from application.world.services.worldbuilding_service import WorldbuildingService
        from infrastructure.persistence.database.sqlite_bible_repository import SqliteBibleRepository
        from infrastructure.persistence.database.sqlite_knowledge_repository import SqliteKnowledgeRepository
        from infrastructure.persistence.database.character_repository import CharacterRepository

        db = get_database()
        bible_repo = SqliteBibleRepository(db)
        knowledge_repo = SqliteKnowledgeRepository(db)
        character_repo = CharacterRepository(db)

        bible_service = BibleService(bible_repo, character_repo)
        worldbuilding_service = WorldbuildingService(db)

        generator = AutoBibleGenerator(
            llm_service=llm_service,
            bible_service=bible_service,
            worldbuilding_service=worldbuilding_service,
        )

        # 提取小说设置
        premise = novel.premise or novel.title or ""
        target_chapters = novel.target_chapters or 30

        # ─── Stage 1: Worldbuilding (五维度世界观) ───
        host._update_shared_state(novel_id, bible_generation_status="worldbuilding")
        logger.info("[%s] 开始生成世界观（五维度）", novel_id)

        try:
            await generator.generate_and_save(
                novel_id=novel_id,
                premise=premise,
                target_chapters=target_chapters,
                stage="worldbuilding",
            )
            logger.info("[%s] 世界观生成完成", novel_id)
        except Exception as e:
            logger.warning("[%s] 世界观生成失败（降级为简略世界观）: %s", novel_id, e)
            await _generate_minimal_worldbuilding(host, novel, llm_service, db)

        if not host._is_still_running(novel):
            logger.info("[%s] 用户已停止，中止 Bible 生成", novel_id)
            return

        # ─── Stage 2: Characters (角色) ───
        host._update_shared_state(novel_id, bible_generation_status="characters")
        logger.info("[%s] 开始生成角色", novel_id)

        try:
            await generator.generate_and_save(
                novel_id=novel_id,
                premise=premise,
                target_chapters=target_chapters,
                stage="characters",
            )
            logger.info("[%s] 角色生成完成", novel_id)
        except Exception as e:
            logger.warning("[%s] 角色生成失败: %s", novel_id, e)

        if not host._is_still_running(novel):
            return

        # ─── Stage 3: Locations (地点) ───
        host._update_shared_state(novel_id, bible_generation_status="locations")
        logger.info("[%s] 开始生成地点", novel_id)

        try:
            await generator.generate_and_save(
                novel_id=novel_id,
                premise=premise,
                target_chapters=target_chapters,
                stage="locations",
            )
            logger.info("[%s] 地点生成完成", novel_id)
        except Exception as e:
            logger.warning("[%s] 地点生成失败: %s", novel_id, e)

        # ─── Stage 4: Knowledge Triples (初始知识三元组) ───
        host._update_shared_state(novel_id, bible_generation_status="knowledge")
        try:
            from application.world.services.auto_knowledge_generator import AutoKnowledgeGenerator

            kg = AutoKnowledgeGenerator(
                llm_service=llm_service,
                knowledge_repository=knowledge_repo,
            )
            await kg.generate_and_save(novel_id, novel.title or "", premise)
            logger.info("[%s] 初始知识三元组生成完成", novel_id)
        except Exception as e:
            logger.warning("[%s] 知识三元组生成失败: %s", novel_id, e)

        # ─── 完成，转移到宏规划 ───
        logger.info("[%s] Bible 生成完成，进入宏规划阶段", novel_id)
        host._update_shared_state(
            novel_id,
            bible_generation_status="completed",
            bible_completed=True,
        )
        novel.current_stage = NovelStage.MACRO_PLANNING
        host._save_novel_state(novel)

    except Exception as e:
        logger.error("[%s] Bible 生成异常: %s", novel_id, e, exc_info=True)
        host._update_shared_state(novel_id, bible_generation_status="error")
        raise


async def _generate_minimal_worldbuilding(
    host: Any, novel: Novel, llm_service: Any, db: Any,
) -> None:
    """降级：用一次 LLM 调用生成极简世界观。"""
    try:
        from application.world.services.auto_bible_generator import AutoBibleGenerator
        from application.world.services.bible_service import BibleService
        from application.world.services.worldbuilding_service import WorldbuildingService
        from infrastructure.persistence.database.sqlite_bible_repository import SqliteBibleRepository
        from infrastructure.persistence.database.character_repository import CharacterRepository

        bible_repo = SqliteBibleRepository(db)
        character_repo = CharacterRepository(db)

        generator = AutoBibleGenerator(
            llm_service=llm_service,
            bible_service=BibleService(bible_repo, character_repo),
            worldbuilding_service=WorldbuildingService(db),
        )

        await generator.generate_and_save(
            novel_id=str(novel.novel_id),
            premise=novel.premise or novel.title or "",
            target_chapters=novel.target_chapters or 30,
            stage="all",
        )
        logger.info("[%s] 降级 Bible 全量生成完成", novel.novel_id)
    except Exception as e:
        logger.error("[%s] 降级 Bible 生成也失败: %s", novel.novel_id, e)
