"""Підмінні моделі ScriptedLlm та ToolCallingLlm для офлайн-тестів та демо-режиму."""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field, PrivateAttr


class ScriptedLlm(BaseLlm):
    """Повертає наперед задані JSON/текст відповіді за маркером ролі в інструкції."""

    script: dict[str, list[Any]] = Field(default_factory=dict)
    calls: list[str] = Field(default_factory=list)
    prompts: dict[str, list[str]] = Field(default_factory=dict)
    loop: bool = False
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    @staticmethod
    def _extract_system_text(llm_request: LlmRequest) -> str:
        if not llm_request.config or not llm_request.config.system_instruction:
            return ""
        si = llm_request.config.system_instruction
        if isinstance(si, str):
            return si
        parts = getattr(si, "parts", None)
        if parts:
            return "\n".join(getattr(p, "text", "") or "" for p in parts)
        return str(si)

    def _match_role(self, sys_text: str) -> str:
        for role in self.script:
            if role in sys_text:
                return role
        raise KeyError(f"No matching role for instruction: {sys_text[:120]}")

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        sys_text = self._extract_system_text(llm_request)
        with self._lock:
            role = self._match_role(sys_text)
            queue = self.script[role]
            if not queue:
                raise IndexError(f"ScriptedLlm queue exhausted for role: {role}")
            item = queue[0] if self.loop and len(queue) == 1 else queue.pop(0)
            self.calls.append(role)
            self.prompts.setdefault(role, []).append(sys_text)

        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=10,
                candidates_token_count=10,
                total_token_count=20,
            ),
        )


class ToolCallingLlm(BaseLlm):
    """Спочатку викликає задані інструменти зі списку calls, потім відповідає answer."""

    calls: list[tuple[str, dict]] = Field(default_factory=list)
    answer: str = ""
    seen_tool_results: list[str] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[0] if llm_request.contents else None
        if last is not None and last.function_response:
            self.seen_tool_results.append(str(last.function_response.response))

        if self.calls:
            name, args = self.calls.pop(0)
            part = types.Part(function_call=types.FunctionCall(name=name, args=args))
        else:
            part = types.Part(text=self.answer)

        yield LlmResponse(
            content=types.Content(role="model", parts=[part]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=8,
                candidates_token_count=8,
                total_token_count=16,
            ),
        )
