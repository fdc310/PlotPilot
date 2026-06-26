"""Environment-backed LLM provider configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass


ARK_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def _env_text(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


@dataclass(frozen=True)
class LLMEnvironmentSettings:
    """Typed view of legacy LLM-related environment variables."""

    provider: str = ""
    writing_model: str = ""
    system_model: str = ""

    # Anthropic / Claude
    anthropic_api_key: str = ""
    anthropic_auth_token: str = ""
    anthropic_base_url: str = ""
    anthropic_model: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""

    # Google Gemini
    gemini_api_key: str = ""
    gemini_base_url: str = ""
    gemini_model: str = ""

    # 豆包 / Ark
    ark_api_key: str = ""
    ark_base_url: str = ""
    ark_model: str = ""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = ""
    deepseek_model: str = ""

    # MiniMax / 海螺AI / 小米 MiMo
    minimax_api_key: str = ""
    minimax_base_url: str = ""
    minimax_model: str = ""

    # SiliconFlow 硅基流动
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = ""
    siliconflow_model: str = ""

    # Moonshot / Kimi
    moonshot_api_key: str = ""
    moonshot_base_url: str = ""
    moonshot_model: str = ""

    # 百度千帆 / 文心一言
    qianfan_api_key: str = ""
    qianfan_base_url: str = ""
    qianfan_model: str = ""

    # 零一万物 Yi
    yi_api_key: str = ""
    yi_base_url: str = ""
    yi_model: str = ""

    @classmethod
    def from_env(cls) -> "LLMEnvironmentSettings":
        return cls(
            provider=_env_text("LLM_PROVIDER").lower(),
            writing_model=_env_text("WRITING_MODEL"),
            system_model=_env_text("SYSTEM_MODEL"),
            # Anthropic
            anthropic_api_key=_env_text("ANTHROPIC_API_KEY"),
            anthropic_auth_token=_env_text("ANTHROPIC_AUTH_TOKEN"),
            anthropic_base_url=_env_text("ANTHROPIC_BASE_URL"),
            anthropic_model=_env_text("ANTHROPIC_MODEL"),
            # OpenAI
            openai_api_key=_env_text("OPENAI_API_KEY"),
            openai_base_url=_env_text("OPENAI_BASE_URL"),
            openai_model=_env_text("OPENAI_MODEL"),
            # Gemini
            gemini_api_key=_env_text("GEMINI_API_KEY"),
            gemini_base_url=_env_text("GEMINI_BASE_URL"),
            gemini_model=_env_text("GEMINI_MODEL"),
            # Ark
            ark_api_key=_env_text("ARK_API_KEY"),
            ark_base_url=_env_text("ARK_BASE_URL"),
            ark_model=_env_text("ARK_MODEL"),
            # DeepSeek
            deepseek_api_key=_env_text("DEEPSEEK_API_KEY"),
            deepseek_base_url=_env_text("DEEPSEEK_BASE_URL"),
            deepseek_model=_env_text("DEEPSEEK_MODEL"),
            # MiniMax
            minimax_api_key=_env_text("MINIMAX_API_KEY"),
            minimax_base_url=_env_text("MINIMAX_BASE_URL"),
            minimax_model=_env_text("MINIMAX_MODEL"),
            # SiliconFlow
            siliconflow_api_key=_env_text("SILICONFLOW_API_KEY"),
            siliconflow_base_url=_env_text("SILICONFLOW_BASE_URL"),
            siliconflow_model=_env_text("SILICONFLOW_MODEL"),
            # Moonshot
            moonshot_api_key=_env_text("MOONSHOT_API_KEY"),
            moonshot_base_url=_env_text("MOONSHOT_BASE_URL"),
            moonshot_model=_env_text("MOONSHOT_MODEL"),
            # Qianfan
            qianfan_api_key=_env_text("QIANFAN_API_KEY"),
            qianfan_base_url=_env_text("QIANFAN_BASE_URL"),
            qianfan_model=_env_text("QIANFAN_MODEL"),
            # Yi
            yi_api_key=_env_text("YI_API_KEY"),
            yi_base_url=_env_text("YI_BASE_URL"),
            yi_model=_env_text("YI_MODEL"),
        )

    @property
    def anthropic_api_key_with_token_fallback(self) -> str:
        return self.anthropic_api_key or self.anthropic_auth_token

    @property
    def openai_preset_key(self) -> str:
        if self.openai_base_url:
            return "custom-openai-compatible"
        return "openai-official"

    @property
    def ark_base_url_or_default(self) -> str:
        return self.ark_base_url or ARK_DEFAULT_BASE_URL

    def resolve_provider_env(self) -> tuple[str, str, str, str]:
        """返回 (preset_key, api_key, base_url, model) 用于环境变量引导。

        按优先级检查所有国产厂商环境变量，返回第一个有 API key 的。
        """
        providers = [
            ("deepseek", self.deepseek_api_key, self.deepseek_base_url or "https://api.deepseek.com/v1", self.deepseek_model),
            ("minimax", self.minimax_api_key, self.minimax_base_url or "https://api.minimax.chat/v1", self.minimax_model),
            ("siliconflow", self.siliconflow_api_key, self.siliconflow_base_url or "https://api.siliconflow.cn/v1", self.siliconflow_model),
            ("moonshot", self.moonshot_api_key, self.moonshot_base_url or "https://api.moonshot.cn/v1", self.moonshot_model),
            ("qianfan", self.qianfan_api_key, self.qianfan_base_url or "https://qianfan.baidubce.com/v2", self.qianfan_model),
            ("yi", self.yi_api_key, self.yi_base_url or "https://api.lingyiwanwu.com/v1", self.yi_model),
        ]
        for preset_key, key, url, model in providers:
            if key:
                return preset_key, key, url, model
        return "", "", "", ""
