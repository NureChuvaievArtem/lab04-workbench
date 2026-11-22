"""Запуск будь-якого ADK-агента або графа з передачею подій у Streamlit."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from google.adk import Workflow
from google.adk.runners import InMemoryRunner
from google.genai import types

OnEvent = Callable[[dict], None]


@dataclass
class RunResult:
    """Агрегований результат виконання агента або графа."""

    state: dict
    trace: list[dict]
    final_text: str
    tool_outputs: list[str] = field(default_factory=list)
    llm_calls: dict[str, int] = field(default_factory=dict)
    tokens: int = 0
    seconds: float = 0.0


async def run_agent_async(
    agent,
    text: str,
    on_event: OnEvent | None = None,
    app_name: str = "workbench",
) -> RunResult:
    """Асинхронно виконує ADK-агента або Workflow і збирає метрики та трасу."""
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="developer"
    )
    trace: list[dict] = []
    tool_outputs: list[str] = []
    calls: dict[str, int] = defaultdict(int)
    tokens = 0
    final_text = ""
    started = time.perf_counter()

    message = types.Content(role="user", parts=[types.Part(text=text)])
    async for event in runner.run_async(
        user_id="developer", session_id=session.id, new_message=message
    ):
        parts = event.content.parts if event.content and event.content.parts else []
        event_text = "".join(p.text or "" for p in parts)
        for p in parts:
            if p.function_response and p.function_response.response:
                tool_outputs.append(str(p.function_response.response.get("result", "")))

        from_model = (
            bool(event_text)
            and event.author != "user"
            and not (isinstance(agent, Workflow) and event.author == agent.name)
        )
        if event.usage_metadata or from_model:
            calls[event.author] += 1
        if event.usage_metadata:
            tokens += event.usage_metadata.total_token_count or 0
        if event_text:
            final_text = event_text

        node = (event.node_info.path or "").split("/")[-1] if event.node_info else ""
        route = event.actions.route if event.actions else None
        record = {
            "t": round(time.perf_counter() - started, 2),
            "author": event.author,
            "node": node,
            "route": route,
            "text": event_text[:300],
        }
        trace.append(record)
        if on_event:
            on_event(record)

    final_session = await runner.session_service.get_session(
        app_name=app_name, user_id="developer", session_id=session.id
    )
    return RunResult(
        state=dict(final_session.state),
        trace=trace,
        final_text=final_text,
        tool_outputs=tool_outputs,
        llm_calls=dict(calls),
        tokens=tokens,
        seconds=round(time.perf_counter() - started, 2),
    )


def run_agent(agent, text: str, on_event: OnEvent | None = None) -> RunResult:
    """Синхронна обгортка: Streamlit виконує скрипт без активного циклу asyncio."""
    return asyncio.run(run_agent_async(agent, text, on_event=on_event))
