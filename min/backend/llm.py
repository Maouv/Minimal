# llm.py — LLM streaming wrapper
# Pakai openai SDK dengan custom base_url — support semua OpenAI-compatible provider

import openai
import config
from typing import Callable, AsyncIterator
from dataclasses import dataclass


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


def _client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        base_url=config.base_url(),
        api_key=config.api_key(),
        timeout=config.timeout(),
    )


def _strip_thinking(content: str) -> str:
    """
    Strip thinking/reasoning content sebelum masuk message history.
    Fixes aider bug: thinking content leak → infinite loop.
    Format yang di-strip: <think>...</think>, <thinking>...</thinking>
    """
    import re
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)
    return content.strip()


async def stream_chat(
    messages: list[dict],
    model: str,
    on_token: Callable[[str], None],
    system_prompt: str = "",
) -> Usage:
    """
    Stream chat completion. Panggil on_token untuk setiap token.
    Return Usage setelah selesai.
    Thinking content di-strip otomatis — tidak pernah masuk history.
    """
    resolved_model = config.resolve_model(model)

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    client = _client()

    stream = await client.chat.completions.create(
        model=resolved_model,
        messages=full_messages,
        max_tokens=config.max_tokens(),
        stream=True,
        stream_options={"include_usage": True},
    )

    input_tokens = 0
    output_tokens = 0
    full_content = ""

    async for chunk in stream:
        # strip thinking chunks sebelum forward ke TUI
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                token = delta.content
                # kalau token adalah bagian dari thinking tag, skip
                full_content += token
                # hanya forward kalau bukan inside thinking block
                if not _inside_thinking(full_content):
                    on_token(token)

        if chunk.usage:
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def _inside_thinking(content: str) -> bool:
    """Cek apakah posisi sekarang masih di dalam thinking block."""
    open_count = content.count("<think>") + content.count("<thinking>")
    close_count = content.count("</think>") + content.count("</thinking>")
    return open_count > close_count


def clean_for_history(content: str) -> str:
    """
    Bersihkan response sebelum disimpan ke message history.
    Strip thinking, normalize whitespace.
    """
    return _strip_thinking(content)

