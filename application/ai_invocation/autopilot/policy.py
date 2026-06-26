"""Autopilot invocation policy resolution — 支持分级自动化。"""
from __future__ import annotations

from typing import Any, Mapping

from application.ai_invocation.dtos import InvocationPolicy
from domain.novel.entities.novel import AutoAILevel


# 分级自动通过操作集
_BALANCED_AUTO_OPS = {
    "autopilot.macro.plan",
    "autopilot.act.plan",
    "autopilot.chapter.audit",
    "autopilot.chapter.aftermath",
    "autopilot.voice.rewrite",
    "autopilot.tension.score",
    "autopilot.narrative.sync",
    # Bible 自动生成（世界观/角色/地点）
    "bible.setup.worldbuilding",
    "bible.setup.characters",
    "bible.setup.locations",
}

_AGGRESSIVE_AUTO_OPS = _BALANCED_AUTO_OPS | {
    "autopilot.chapter.prose",
    "autopilot.stream.beat",
    "autopilot.bridge.extract",
    "autopilot.bridge.check",
    "autopilot.bridge.fix",
    "chapter.generate.prose",
}


class AutopilotInvocationPolicyResolver:
    """Resolve autopilot policy from runtime hints and novel flags.

    自动化级别 (auto_ai_level):
    - conservative: 仅 aftermath/audit 自动通过（默认行为，兼容旧版）
    - balanced: 规划 + 审计 + 改写自动通过
    - aggressive: 全部自动通过
    """

    def resolve(
        self,
        *,
        operation: str,
        node_key: str,
        novel: Any = None,
        policy_hint: InvocationPolicy | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> InvocationPolicy:
        if policy_hint is not None:
            return policy_hint

        context = dict(context or {})
        if str(context.get("force_interactive") or "").lower() in {"1", "true", "yes"}:
            return InvocationPolicy.AUTOPILOT_PAUSE

        # 读取自动化级别（兼容旧字段 auto_approve_mode）
        auto_ai_level = AutoAILevel.CONSERVATIVE
        if novel is not None:
            level = getattr(novel, "auto_ai_level", None)
            if level is not None:
                auto_ai_level = level if isinstance(level, AutoAILevel) else AutoAILevel(str(level))
            elif getattr(novel, "auto_approve_mode", False):
                auto_ai_level = AutoAILevel.AGGRESSIVE

        # 始终自动通过的：aftermath
        if operation in {"autopilot.chapter.aftermath"}:
            return InvocationPolicy.DIRECT

        # 分级自动化
        if auto_ai_level == AutoAILevel.AGGRESSIVE:
            return InvocationPolicy.DIRECT
        if auto_ai_level == AutoAILevel.BALANCED:
            if operation in _BALANCED_AUTO_OPS:
                return InvocationPolicy.DIRECT
            return InvocationPolicy.AUTOPILOT_PAUSE
        # conservative: 仅 audit 自动通过
        if operation in {"autopilot.chapter.audit"}:
            return InvocationPolicy.DIRECT
        return InvocationPolicy.AUTOPILOT_PAUSE
