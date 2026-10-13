"""Model routing: Flash tier (cheap) vs Reasoning tier (complex geo tasks)."""
import os
from dataclasses import dataclass
from typing import Any, Literal

ModelTier = Literal['flash', 'reasoning']

_REASONING_KEYWORDS = (
    'hố đào', 'ho dao', 'móng cọc', 'mong coc', 'móng bè', 'mong be',
    'phase', 'pha thi công', 'staged', 'multi-stage',
    'settlement', 'lún', 'lun', 'stability', 'ổn định', 'on dinh',
    'contour', 'polygon', 'mesh', 'lưới', 'luoi',
    'bearing capacity', 'sức chịu tải', 'suc chiu tai',
    '3d', 'ba chiều', 'ba chieu',
)

# DeepSeek V4 Flash: cheap, fast tool-calling, short output
_DEFAULT_FLASH_MODEL = 'deepseek/deepseek-chat-v3-0324:free'
# Nemotron 3 Super 128B: strong reasoning, 128k context
_DEFAULT_REASONING_MODEL = 'nvidia/llama-3.1-nemotron-ultra-253b-v1'


@dataclass
class ModelConfig:
    model_id: str
    max_tokens: int
    temperature: float = 0.0


def flash_config() -> ModelConfig:
    return ModelConfig(
        model_id=os.environ.get('CHATAI_AGENT_FLASH_MODEL', _DEFAULT_FLASH_MODEL),
        max_tokens=512,
    )


def reasoning_config() -> ModelConfig:
    return ModelConfig(
        model_id=os.environ.get('CHATAI_AGENT_REASONING_MODEL', _DEFAULT_REASONING_MODEL),
        max_tokens=1024,
    )


def select_tier(prompt: str, max_steps: int, model_tier: str = 'auto') -> ModelTier:
    if model_tier == 'flash':
        return 'flash'
    if model_tier == 'reasoning':
        return 'reasoning'
    if max_steps > 6:
        return 'reasoning'
    prompt_lower = prompt.lower()
    if any(kw in prompt_lower for kw in _REASONING_KEYWORDS):
        return 'reasoning'
    return 'flash'


def _make_openrouter_model(cfg: ModelConfig) -> Any:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=cfg.model_id,
        openai_api_key=os.environ['CHATAI_OPENROUTER_KEY'],
        openai_api_base='https://openrouter.ai/api/v1',
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        timeout=180,
    )


def _make_ollama_model(cfg: ModelConfig) -> Any:
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=os.environ.get('CHATAI_AGENT_MODEL', 'qwen2.5:7b'),
        base_url=os.environ.get('CHATAI_OLLAMA_URL', 'http://127.0.0.1:11434'),
        temperature=cfg.temperature,
        client_kwargs={'timeout': 180},
        async_client_kwargs={'timeout': 180},
    )


def build_model_pair() -> tuple[Any, Any]:
    """Returns (flash_model, reasoning_model)."""
    using_openrouter = bool(os.environ.get('CHATAI_OPENROUTER_KEY'))
    if using_openrouter:
        return _make_openrouter_model(flash_config()), _make_openrouter_model(reasoning_config())
    # Ollama fallback: both tiers use the same local model
    m = _make_ollama_model(flash_config())
    return m, m
