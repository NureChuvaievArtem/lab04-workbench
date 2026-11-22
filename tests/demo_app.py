"""Демонстраційний режим без ключа API: підмінні моделі й лексичні ембединги.

Запуск: PYTHONPATH=. uv run streamlit run tests/demo_app.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import chromadb
import streamlit as st

from app.agent import build_workflow
from app.kb_assistant import build_kb_assistant
from kb.embedder import HashEmbedder
from kb.store import KnowledgeStore
from kb.tools import KnowledgeTools, index_vault
from tests.fixtures import CODE_APPROVE, IMPL_GOOD, PLAN_GOOD, QA_APPROVE
from tests.scripted import ScriptedLlm, ToolCallingLlm
from workbench.service import WorkbenchService
from workbench.storage import HistoryStore

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def demo_service() -> WorkbenchService:
    tmp = Path(tempfile.mkdtemp(prefix="smartlease_demo_"))
    vault = tmp / "kb-vault"
    shutil.copytree(ROOT / "tests" / "vault", vault)
    embedder = HashEmbedder()
    store = KnowledgeStore(
        collection_name="demo_kb",
        client=chromadb.PersistentClient(path=str(tmp / "chroma")),
    )
    index_vault(vault, store, embedder)
    tools = KnowledgeTools(store, vault, embedder=embedder, top_k=3, max_distance=0.95)

    team_model = ScriptedLlm(
        model="demo",
        loop=True,
        script={
            "smartlease_requirements_planner": [PLAN_GOOD],
            "smartlease_implementer": [IMPL_GOOD],
            "smartlease_code_reviewer": [CODE_APPROVE],
            "smartlease_qa_suite_reviewer": [QA_APPROVE],
        },
    )

    class DemoKb(ToolCallingLlm):
        async def generate_content_async(self, llm_request, stream=False):
            last = llm_request.contents[-1].parts[0] if llm_request.contents else None
            if not self.calls and not (last and last.function_response):
                self.calls = [("search_knowledge", {"query": "переглядів ліміт"})]
            async for item in super().generate_content_async(llm_request, stream):
                yield item

    kb_model = DemoKb(
        model="demo",
        answer=(
            "Згідно з правилами SmartLease, Tenant може подати не більше 3 заявок "
            "на перегляд житла протягом 24 годин [[Регламент бронювання переглядів#Анти-спам ліміт]]."
        ),
    )

    return WorkbenchService(
        team_agent=build_workflow(
            team_model, kb_search=tools.search_knowledge, use_kb_agent=False
        ),
        kb_agent=build_kb_assistant(kb_model, tools),
        history=HistoryStore(tmp / "history.db"),
        vault=vault,
        vault_name="kb-vault",
    )


st.session_state.setdefault("service", demo_service())
exec((ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
