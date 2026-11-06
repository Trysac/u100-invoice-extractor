"""LLM port and deterministic test doubles."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMPort(Protocol):
    """Minimal chat-completion interface; its exceptions propagate unchanged."""

    def complete(self, messages: Sequence[Message], *, max_tokens: int) -> str:
        """Return the model reply for ``messages``."""
        ...


class RecordingExhaustedError(Exception):
    """Raised by RecordedLLM when all recorded replies were consumed."""


class RecordedLLM:
    """Returns recorded replies in order and records every call in ``calls``."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self._index = 0
        self.calls: list[list[Message]] = []

    def complete(self, messages: Sequence[Message], *, max_tokens: int) -> str:
        """Return the next recorded reply."""
        if self._index >= len(self._replies):
            raise RecordingExhaustedError("no recorded replies left")
        self.calls.append([Message(role=m["role"], content=m["content"]) for m in messages])
        reply = self._replies[self._index]
        self._index += 1
        return reply


class FakeLLM:
    """Delegates to a function; useful for tests."""

    def __init__(self, fn: Callable[[Sequence[Message]], str]) -> None:
        self._fn = fn

    def complete(self, messages: Sequence[Message], *, max_tokens: int) -> str:
        """Return ``fn(messages)``."""
        return self._fn(messages)
