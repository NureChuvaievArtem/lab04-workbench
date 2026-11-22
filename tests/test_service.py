"""Офлайн-тести сервісного шару WorkbenchService без звернень до API."""

from __future__ import annotations

import pytest


def test_team_uses_kb_context_and_builds_exports(service) -> None:
    events = []
    run = service.run_team(
        "SL-142: Бронювання перегляду квартири з анти-спам лімітом.",
        on_event=events.append,
    )
    assert run.jira_key == "SL-142"
    assert run.stop_reason == "approved"
    assert run.http_suite.startswith("### SmartLease API")
    assert "test('tenant books apartment viewing'" in run.playwright_spec
    assert "<fragment" in run.result.state["kb_context"]
    assert any(e["node"].startswith("retrieve_context") for e in events)
    assert service.history.get(run.run_id)["stop_reason"] == "approved"


def test_ask_returns_verified_obsidian_sources(service) -> None:
    answer = service.ask("Який анти-спам ліміт для переглядів?")
    assert answer.invalid_citations == []
    assert any(s["url"].startswith("obsidian://open?vault=kb-vault&file=") for s in answer.sources)
    assert "obsidian://open?vault=kb-vault" in answer.linked_text


def test_save_result_requires_reviewer_and_writes_inbox(service) -> None:
    run = service.run_team("SL-142: Бронювання перегляду квартири з анти-спам лімітом.")
    with pytest.raises(ValueError):
        service.save_result(run, reviewer="   ")

    path = service.save_result(run, reviewer="Чуваєв А. О.")
    assert path.parent.name == "Inbox"
    content = path.read_text(encoding="utf-8")
    assert 'approved_by: "Чуваєв А. О."' in content
    assert service.history.get(run.run_id)["saved_path"] == str(path)
