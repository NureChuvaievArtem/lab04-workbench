"""Експортери артефактів етапу Конструювання: Draft PR, .http, Playwright і нотатка Obsidian."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


def slugify(title: str) -> str:
    """Формує безпечне ім'я файла (кирилиця/латиниця, цифри, пробіли, дефіси)."""
    cleaned = re.sub(r"[^\w\s-]", "", title or "", flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", cleaned)[:80] or "smartlease-pr"


def to_draft_pr_md(state: dict, fallback_report: str = "") -> str:
    """Повертає Markdown-артефакт Draft Pull Request для етапу PR Review."""
    pr = state.get("pr_draft") or {}
    return str(pr.get("markdown") or state.get("report") or fallback_report).strip() + "\n"


def to_http_suite(state: dict) -> str:
    """Повертає готовий файл tests.http для локальної перевірки API SmartLease."""
    impl = state.get("implementation") or {}
    pr = state.get("pr_draft") or {}
    raw = str(pr.get("http_suite") or impl.get("http_suite") or "").strip()
    if not raw:
        return ""
    jira_key = pr.get("jira_key") or state.get("jira_key") or "SL-NEW"
    header = f"### SmartLease API Verification Suite ({jira_key})\n"
    return header + raw + "\n"


def to_playwright_spec(state: dict) -> str:
    """Повертає готовий файл e2e.spec.ts для перевірки UI в Playwright."""
    impl = state.get("implementation") or {}
    pr = state.get("pr_draft") or {}
    raw = str(pr.get("playwright_spec") or impl.get("playwright_spec") or "").strip()
    if not raw:
        return ""
    if "import " not in raw:
        raw = "import { test, expect } from '@playwright/test';\n\n" + raw
    return raw + "\n"


def to_vault_note(
    jira_key: str,
    title: str,
    report: str,
    run_id: str,
    reviewer: str,
) -> str:
    """Формує Markdown-нотатку з frontmatter та іменем рецензента для сховища."""
    tags = "[smartlease, construction, draft-pr, approved]"
    return (
        f"---\n"
        f"tags: {tags}\n"
        f"jira_key: \"{jira_key}\"\n"
        f"title: \"{title}\"\n"
        f"source: \"workbench run {run_id}\"\n"
        f"approved_by: \"{reviewer}\"\n"
        f"updated: {date.today().isoformat()}\n"
        f"---\n\n"
        f"{report.strip()}\n"
    )


def save_to_vault(
    vault: Path, note_text: str, title: str, folder: str = "Inbox"
) -> Path:
    """Зберігає нотатку лише в підкаталог Inbox сховища і ніколи не перезаписує наявну."""
    vault_root = vault.resolve()
    target_dir = (vault_root / folder).resolve()
    if not target_dir.is_relative_to(vault_root):
        raise ValueError("Цільовий каталог виходить за межі сховища Obsidian")
    target_dir.mkdir(parents=True, exist_ok=True)

    base = slugify(title)
    path = target_dir / f"{base}.md"
    n = 2
    while path.exists():
        path = target_dir / f"{base} ({n}).md"
        n += 1
    path.write_text(note_text, encoding="utf-8")
    return path
