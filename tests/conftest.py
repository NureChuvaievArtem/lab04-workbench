"""Фікстури офлайн-тестів: тестове сховище, Chroma на HashEmbedder та WorkbenchService."""

from __future__ import annotations

import shutil
from pathlib import Path

import chromadb
import pytest

from app.agent import build_workflow
from app.kb_assistant import build_kb_assistant
from kb.embedder import HashEmbedder
from kb.store import KnowledgeStore
from kb.tools import KnowledgeTools, index_vault
from tests.fixtures import CODE_APPROVE, IMPL_GOOD, PLAN_GOOD, QA_APPROVE
from tests.scripted import ScriptedLlm, ToolCallingLlm
from workbench.service import WorkbenchService
from workbench.storage import HistoryStore


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    target = tmp_path / "kb-vault"
    shutil.copytree(Path(__file__).parent / "vault", target)
    return target


@pytest.fixture
def kb_tools(vault: Path, tmp_path: Path) -> KnowledgeTools:
    embedder = HashEmbedder()
    store = KnowledgeStore(
        collection_name="test_kb",
        client=chromadb.PersistentClient(path=str(tmp_path / "chroma")),
    )
    index_vault(vault, store, embedder)
    return KnowledgeTools(store, vault, embedder=embedder, top_k=3, max_distance=0.95)


@pytest.fixture
def service(kb_tools: KnowledgeTools, vault: Path, tmp_path: Path) -> WorkbenchService:
    team_model = ScriptedLlm(
        model="scripted",
        loop=True,
        script={
            "smartlease_requirements_planner": [PLAN_GOOD],
            "smartlease_implementer": [IMPL_GOOD],
            "smartlease_code_reviewer": [CODE_APPROVE],
            "smartlease_qa_suite_reviewer": [QA_APPROVE],
        },
    )
    kb_model = ToolCallingLlm(
        model="scripted",
        calls=[("search_knowledge", {"query": "анти-спам переглядів"})],
        answer=(
            "Авторизований Tenant може подати не більше 3 заявок за 24 години "
            "[[Регламент бронювання переглядів#Анти-спам ліміт]]."
        ),
    )
    return WorkbenchService(
        team_agent=build_workflow(
            team_model, kb_search=kb_tools.search_knowledge, use_kb_agent=False
        ),
        kb_agent=build_kb_assistant(kb_model, kb_tools),
        history=HistoryStore(tmp_path / "history.db"),
        vault=vault,
        vault_name="kb-vault",
    )
