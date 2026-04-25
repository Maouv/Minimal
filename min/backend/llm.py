# llm.py — LLM streaming wrapper
# Pakai openai SDK dengan custom base_url — support semua OpenAI-compatible provider

import re
import openai
import config
from typing import AsyncIterator
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
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)
    return content.strip()


def _inside_thinking(content: str) -> bool:
    open_count = content.count("<think>") + content.count("<thinking>")
    close_count = content.count("</think>") + content.count("</thinking>")
    return open_count > close_count


def _just_closed_thinking(prev: str, curr: str) -> bool:
    """Return True if the last token closed a thinking block."""
    prev_open = prev.count("<think>") + prev.count("<thinking>")
    curr_close = curr.count("</think>") + curr.count("</thinking>")
    prev_close = prev.count("</think>") + prev.count("</thinking>")
    return curr_close > prev_close and prev_open > prev_close


def clean_for_history(content: str) -> str:
    return _strip_thinking(content)


async def stream_chat(
    messages: list[dict],
    model: str,
    system_prompt: str = "",
) -> AsyncIterator[tuple[str | None, Usage | None, str | None]]:
    """
    Async generator — yield (token, None, None) per token, (None, Usage, None) di akhir.
    Thinking content di-yield sebagai (None, None, thinking_chunk) terpisah.
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

    full_content = ""
    input_tokens = 0
    output_tokens = 0

    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta

            # --- Handle reasoning_content (DeepSeek, etc.) ---
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield None, None, reasoning

            if delta and delta.content:
                token = delta.content
                prev_content = full_content
                full_content += token

                if _inside_thinking(full_content):
                    # Token masih di dalam thinking block — stream sebagai thinking
                    yield None, None, token
                elif _just_closed_thinking(prev_content, full_content):
                    # Token menutup thinking block — skip closing tag, jangan emit
                    pass
                else:
                    yield token, None, None

        if chunk.usage:
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

    yield None, Usage(input_tokens=input_tokens, output_tokens=output_tokens), None
