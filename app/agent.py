"""Граф Workflow ADK 2.x для SDLC SmartLease із вузлом контексту ЛР 2."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv
from google.adk import Context, Workflow
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.models.base_llm import BaseLlm
from google.adk.workflow import JoinNode
from google.genai import types

from .agents import build_agents
from .kb_connector import build_kb_researcher, make_kb_search
from .nodes import (
    build_clarification_report,
    build_draft_pr,
    intake_jira,
    lint_and_policy_check,
    pr_gate,
    readiness_gate,
    reject,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
KbSearch = Callable[[str], str]


def gemini(model_name: str | None = None) -> Gemini:
    """Повертає налаштовану модель Gemini з retry-політикою для лімітів API."""
    return Gemini(
        model=model_name or MODEL,
        retry_options=types.HttpRetryOptions(
            attempts=6,
            initial_delay=2.0,
            max_delay=15.0,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    )


def build_workflow(
    model: BaseLlm | str,
    kb_search: KbSearch | None = None,
    *,
    use_kb_agent: bool = False,
) -> Workflow:
    """Будує SDLC-граф SmartLease із детермінованим RAG-вузлом retrieve_context."""
    a = build_agents(model)
    reviews = JoinNode(name="reviews")

    def retrieve_context(ctx: Context, node_input: str):
        """Детермінований RAG-крок: правила SmartLease з бази знань до планувальника."""
        request = ctx.state.get("request", "")
        ctx.state["kb_context"] = (
            kb_search(request) if kb_search else "NOT_FOUND: no knowledge base"
        )
        return node_input

    context_node = (
        build_kb_researcher(model, kb_search)
        if (use_kb_agent and kb_search is not None)
        else retrieve_context
    )

    return Workflow(
        name="smartlease_sdlc",
        description="SDLC-конвеєр SmartLease (Конструювання): Jira -> БЗ -> План -> Код/Тести -> Лінт & Рев'ю -> Draft PR.",
        max_concurrency=2,
        edges=[
            ("START", intake_jira),
            (intake_jira, {"ok": context_node, "reject": reject}),
            (context_node, a["requirements_planner"]),
            (a["requirements_planner"], readiness_gate),
            (
                readiness_gate,
                {"ok": a["implementer"], "clarify": build_clarification_report},
            ),
            (a["implementer"], lint_and_policy_check),
            (
                lint_and_policy_check,
                {
                    "ok": (a["code_reviewer"], a["qa_suite_reviewer"]),
                    "fix": a["implementer"],
                    "max_reached": build_draft_pr,
                },
            ),
            (a["code_reviewer"], reviews),
            (a["qa_suite_reviewer"], reviews),
            (reviews, pr_gate),
            (pr_gate, {"revise": a["implementer"], "publish": build_draft_pr}),
        ],
    )


root_agent = build_workflow(gemini(), kb_search=make_kb_search(), use_kb_agent=False)

app = App(
    root_agent=root_agent,
    name="app",
)
