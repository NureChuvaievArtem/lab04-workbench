"""Unit-тести експортерів артефактів та безпечного запису в сховище."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures import IMPL_GOOD
from workbench.exporters import (
    save_to_vault,
    slugify,
    to_draft_pr_md,
    to_http_suite,
    to_playwright_spec,
)


def test_exports_draft_pr_http_and_playwright() -> None:
    impl = json.loads(IMPL_GOOD)
    state = {
        "jira_key": "SL-142",
        "implementation": impl,
        "report": "# draft: [SL-142] Viewing booking",
        "pr_draft": {"jira_key": "SL-142", "markdown": "# draft: [SL-142] Viewing booking"},
    }
    assert to_draft_pr_md(state).startswith("# draft: [SL-142]")
    http_txt = to_http_suite(state)
    assert "POST http://localhost:5000/api/viewings" in http_txt
    pw_txt = to_playwright_spec(state)
    assert "import { test, expect }" in pw_txt
    assert "tenant books apartment viewing" in pw_txt


def test_save_to_vault_never_overwrites_existing_note(tmp_path: Path) -> None:
    p1 = save_to_vault(tmp_path, "first", "SL-142: Перегляд квартири")
    p2 = save_to_vault(tmp_path, "second", "SL-142: Перегляд квартири")
    assert p1.parent.name == "Inbox"
    assert p1.name == "SL-142 Перегляд квартири.md"
    assert p2.name == "SL-142 Перегляд квартири (2).md"
    assert p1.read_text(encoding="utf-8") == "first"
    assert p2.read_text(encoding="utf-8") == "second"


def test_save_to_vault_blocks_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_to_vault(tmp_path, "bad", "hack", folder="../outside")
    assert slugify("!!!") == "smartlease-pr"
