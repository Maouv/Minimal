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


def clean_for_history(content: str) -> str:
    return _strip_thinking(content)


class _ThinkingStateMachine:
    """
    State machine untuk detect thinking blocks saat streaming token-by-token.
    Lebih reliable dari count-based karena handle partial tags dan nested content.
    """
    OPEN_TAGS  = ("<think>", "<thinking>")
    CLOSE_TAGS = ("</think>", "</thinking>")

    def __init__(self):
        self.in_thinking = False
        self._buf = ""          # accumulate chars untuk lookahead partial tags

    def feed(self, token: str) -> tuple[str, str]:
        """
        Proses satu token. Return (text_out, thinking_out).
        Salah satunya pasti kosong, atau keduanya kalau token spanning boundary.
        """
        self._buf += token
        text_out = ""
        thinking_out = ""

        while self._buf:
            if not self.in_thinking:
                # Cari opening tag
                found, tag = self._find_tag(self._buf, self.OPEN_TAGS)
                if found is not None:
                    # Emit semua sebelum tag sebagai text
                    text_out += self._buf[:found]
                    self._buf = self._buf[found + len(tag):]
                    self.in_thinking = True
                elif self._partial_match(self._buf, self.OPEN_TAGS):
                    # Partial tag di ujung buffer — tunggu token berikutnya
                    break
                else:
                    # Tidak ada tag, semua text
                    text_out += self._buf
                    self._buf = ""
                    break
            else:
                # Cari closing tag
                found, tag = self._find_tag(self._buf, self.CLOSE_TAGS)
                if found is not None:
                    # Emit semua sebelum closing tag sebagai thinking
                    thinking_out += self._buf[:found]
                    self._buf = self._buf[found + len(tag):]
                    self.in_thinking = False
                elif self._partial_match(self._buf, self.CLOSE_TAGS):
                    # Partial closing tag — tunggu
                    break
                else:
                    # Semua thinking content
                    thinking_out += self._buf
                    self._buf = ""
                    break

        return text_out, thinking_out

    @staticmethod
    def _find_tag(buf: str, tags: tuple) -> tuple[int | None, str]:
        """Cari tag paling awal di buf. Return (index, tag) atau (None, '')."""
        best_idx, best_tag = None, ""
        for tag in tags:
            idx = buf.find(tag)
            if idx != -1 and (best_idx is None or idx < best_idx):
                best_idx, best_tag = idx, tag
        return best_idx, best_tag

    @staticmethod
    def _partial_match(buf: str, tags: tuple) -> bool:
        """Return True kalau ujung buf adalah prefix dari salah satu tag."""
        for tag in tags:
            for length in range(1, len(tag)):
                if buf.endswith(tag[:length]):
                    return True
        return False


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

    stream = await client.chat.completions.create(  # type: ignore[call-overload]
        model=resolved_model,
        messages=full_messages,  # type: ignore[arg-type]
        max_tokens=config.max_tokens(),
        stream=True,
        stream_options={"include_usage": True},
    )

    sm = _ThinkingStateMachine()
    input_tokens = 0
    output_tokens = 0

    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta

            # --- Handle reasoning_content (DeepSeek, Qwen native, etc.) ---
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield None, None, reasoning

            if delta and delta.content:
                text_out, thinking_out = sm.feed(delta.content)
                if thinking_out:
                    yield None, None, thinking_out
                if text_out:
                    yield text_out, None, None

        if chunk.usage:
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

    # Flush sisa buffer state machine (partial tag yang tidak pernah closed)
    if sm._buf:
        if sm.in_thinking:
            yield None, None, sm._buf
        else:
            yield sm._buf, None, None

    yield None, Usage(input_tokens=input_tokens, output_tokens=output_tokens), None

