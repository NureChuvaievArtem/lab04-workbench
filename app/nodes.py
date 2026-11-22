"""Детерміновані вузли SDLC-графа SmartLease (валідація, лінт, гейти, Draft PR)."""

from __future__ import annotations

import re
from typing import Any

from google.adk import Context, Event
from google.genai import types

MAX_ROUNDS = 3
MIN_REQUEST_CHARS = 15

JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
HTTP_VERB_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(?:https?://\S+)?/", re.IGNORECASE
)
SECRET_LEAK_RE = re.compile(
    r"(AIza[0-9A-Za-z_-]{10,}|sk-[0-9A-Za-z]{12,}|\b(?:password|secret|api_key)\s*=\s*[\"'][^\"']{4,}[\"'])",
    re.IGNORECASE,
)
RAW_SQL_INTERP_RE = re.compile(
    r"(?:f|\$)\"[^\"]*\b(?:SELECT|INSERT|UPDATE|DELETE)\b[^\"]*\{", re.IGNORECASE
)


def extract_jira_key(text: str) -> str:
    """Витягує ключ Jira issue зі вхідного запиту або повертає SL-NEW."""
    match = JIRA_KEY_RE.search(text or "")
    return match.group(1) if match else "SL-NEW"


def _make_text_event(text: str, route: str | None = None) -> Event:
    kwargs: dict[str, Any] = {
        "output": text,
        "content": types.Content(role="model", parts=[types.Part(text=text)]),
    }
    if route is not None:
        kwargs["route"] = route
    return Event(**kwargs)


def intake_jira(ctx: Context, node_input: str) -> Event:
    """Перевіряє Jira-вхід, ініціалізує стан сесії та відсікає порожні запити."""
    raw_text = (node_input or "").strip()
    word_chars = re.findall(r"[0-9A-Za-zА-Яа-яІіЇїЄєҐґ]", raw_text)
    if len(raw_text) < MIN_REQUEST_CHARS or len(word_chars) < 8:
        ctx.state["request"] = raw_text
        ctx.state["jira_key"] = extract_jira_key(raw_text)
        ctx.state["drafts"] = 0
        ctx.state["round"] = 0
        ctx.state["stop_reason"] = "invalid_input"
        return Event(
            route="reject",
            output="Запит занадто короткий або не містить опису Jira-задачі.",
        )

    jira_key = extract_jira_key(raw_text)
    ctx.state["request"] = raw_text
    ctx.state["jira_key"] = jira_key
    ctx.state["drafts"] = 0
    ctx.state["round"] = 0
    ctx.state["lint_errors"] = ""
    ctx.state["lint_passed"] = False
    ctx.state["review_feedback"] = ""
    ctx.state["stop_reason"] = ""
    ctx.state.setdefault("kb_context", "NOT_FOUND: no knowledge base")
    return Event(route="ok", output=raw_text)


def reject(ctx: Context) -> Event:
    """Формує фінальне повідомлення при відхиленні некоректного Jira-запиту."""
    jira_key = ctx.state.get("jira_key", "SL-NEW")
    report = (
        f"# Відхилено запит ({jira_key})\n\n"
        "Опис Jira issue занадто короткий (менше 15 змістовних символів). "
        "Додайте мету задачі, очікувану поведінку API/UI та критерії приймання."
    )
    ctx.state["stop_reason"] = "invalid_input"
    ctx.state["report"] = report
    return _make_text_event(report)


def readiness_gate(ctx: Context) -> Event:
    """Перевіряє готовність вимог до етапу конструювання перед генерацією коду."""
    plan = ctx.state.get("plan") or {}
    status = plan.get("readiness_status", "ready")
    score = int(plan.get("readiness_score", 4))
    if status == "needs_clarification" or score <= 1:
        ctx.state["stop_reason"] = "needs_clarification"
        return Event(route="clarify", output="needs_clarification")
    return Event(route="ok", output="ready")


def build_clarification_report(ctx: Context) -> Event:
    """Формує звіт із уточненнями, якщо Jira-вимоги не готові до розробки."""
    plan = ctx.state.get("plan") or {}
    jira_key = plan.get("jira_key") or ctx.state.get("jira_key", "SL-NEW")
    title = plan.get("title", "Уточнення вимог Jira issue")
    questions = plan.get("clarification_questions") or [
        "Уточніть критерії приймання, ролі доступу та очікувані HTTP-статуси."
    ]
    q_md = "\n".join(f"- {q}" for q in questions)
    report = (
        f"# Потрібне уточнення Jira issue: [{jira_key}] {title}\n\n"
        f"**Readiness score:** {plan.get('readiness_score', 1)}/5 (`needs_clarification`)\n\n"
        f"## Запитання до постановки задачі\n{q_md}\n"
    )
    ctx.state["stop_reason"] = "needs_clarification"
    ctx.state["report"] = report
    return _make_text_event(report)


def validate_implementation_bundle(impl: dict[str, Any]) -> list[str]:
    """Детермінований статичний лінт та перевірка структури .http і Playwright тестів."""
    errors: list[str] = []
    if not impl or not isinstance(impl, dict):
        return ["Пакет імплементації порожній або має невалідну структуру."]

    backend = [str(x).strip() for x in (impl.get("backend_changes") or []) if str(x).strip()]
    frontend = [str(x).strip() for x in (impl.get("frontend_changes") or []) if str(x).strip()]
    if not backend and not frontend:
        errors.append("Відсутні зміни для backend_changes або frontend_changes.")

    snippets = str(impl.get("code_snippets") or "").strip()
    if len(snippets) < 20:
        errors.append("code_snippets надто короткий (потрібен приклад коду >= 20 символів).")

    http_suite = str(impl.get("http_suite") or "")
    if not HTTP_VERB_RE.search(http_suite):
        errors.append(
            "http_suite не містить валідних HTTP-запитів формату METHOD /path (наприклад GET /api/...)."
        )

    pw_spec = str(impl.get("playwright_spec") or "")
    if "test(" not in pw_spec or ("expect(" not in pw_spec and "page." not in pw_spec):
        errors.append(
            "playwright_spec має містити Playwright тест із test(...) та page./expect(...)."
        )

    combined = "\n".join([snippets, http_suite, pw_spec])
    if SECRET_LEAK_RE.search(combined):
        errors.append("Порушення безпеки: виявлено потенційний захардкоджений секрет/пароль.")
    if "eval(" in combined:
        errors.append("Порушення лінту: заборонено використання eval().")
    if RAW_SQL_INTERP_RE.search(snippets):
        errors.append("Порушення безпеки: небезпечна інтерполяція рядка в SQL-запиті.")

    return errors


def lint_and_policy_check(ctx: Context) -> Event:
    """Детерміновано перевіряє пакет змін перед викликом паралельних рев'юерів."""
    drafts = int(ctx.state.get("drafts", 0)) + 1
    ctx.state["drafts"] = drafts
    ctx.state["round"] = drafts

    impl = ctx.state.get("implementation") or {}
    errors = validate_implementation_bundle(impl)
    if errors:
        joined = "; ".join(errors)
        ctx.state["lint_passed"] = False
        ctx.state["lint_errors"] = joined
        if drafts < MAX_ROUNDS:
            return Event(route="fix", output=joined)
        ctx.state["stop_reason"] = "max_drafts"
        return Event(route="max_reached", output=f"max_drafts_lint: {joined}")

    ctx.state["lint_passed"] = True
    ctx.state["lint_errors"] = ""
    return Event(route="ok", output="lint_ok")


def pr_gate(ctx: Context) -> Event:
    """Агрегує вердикти code_reviewer та qa_suite_reviewer і контролює ліміт ітерацій."""
    code_rev = ctx.state.get("code_review") or {}
    qa_rev = ctx.state.get("qa_review") or {}
    drafts = int(ctx.state.get("drafts", 1))

    code_ok = code_rev.get("verdict") == "approve"
    qa_ok = qa_rev.get("verdict") == "approve"

    if code_ok and qa_ok:
        ctx.state["stop_reason"] = "approved"
        ctx.state["review_feedback"] = ""
        return Event(route="publish", output="approved")

    feedback_parts: list[str] = []
    for item in code_rev.get("issues") or []:
        feedback_parts.append(f"[Code Issue] {item}")
    for item in code_rev.get("required_fixes") or []:
        feedback_parts.append(f"[Code Fix] {item}")
    for item in qa_rev.get("missing_http_cases") or []:
        feedback_parts.append(f"[Missing .http] {item}")
    for item in qa_rev.get("missing_playwright_cases") or []:
        feedback_parts.append(f"[Missing Playwright] {item}")
    for item in qa_rev.get("required_fixes") or []:
        feedback_parts.append(f"[QA Fix] {item}")

    feedback = "\n".join(feedback_parts) or "Доопрацюйте код і тести зауваженнями рев'ю."
    ctx.state["review_feedback"] = feedback

    if drafts < MAX_ROUNDS:
        return Event(route="revise", output=feedback)

    ctx.state["stop_reason"] = "max_drafts"
    return Event(route="publish", output="max_drafts")


def build_draft_pr(ctx: Context) -> Event:
    """Детерміновано формує артефакт Draft Pull Request зі стану сесії."""
    plan = ctx.state.get("plan") or {}
    impl = ctx.state.get("implementation") or {}
    code_rev = ctx.state.get("code_review") or {}
    qa_rev = ctx.state.get("qa_review") or {}

    jira_key = impl.get("jira_key") or plan.get("jira_key") or ctx.state.get("jira_key", "SL-NEW")
    title = plan.get("title") or "SmartLease Feature Update"
    branch = impl.get("branch_name") or f"feat/{jira_key.lower()}-update"
    drafts = int(ctx.state.get("drafts", 0))
    stop_reason = ctx.state.get("stop_reason") or "approved"
    lint_passed = bool(ctx.state.get("lint_passed", False))
    lint_errors = ctx.state.get("lint_errors", "")

    pr_title = f"draft: [{jira_key}] {title}"
    backend_md = "\n".join(f"- {c}" for c in (impl.get("backend_changes") or ["—"]))
    frontend_md = "\n".join(f"- {c}" for c in (impl.get("frontend_changes") or ["—"]))
    ac_md = "\n".join(f"- {c}" for c in (plan.get("acceptance_criteria") or ["—"]))
    steps_md = "\n".join(f"{i}. {s}" for i, s in enumerate(plan.get("implementation_steps") or ["—"], 1))
    assumptions_md = "\n".join(f"- {a}" for a in (impl.get("assumptions") or ["Не вказано"]))

    code_verdict = code_rev.get("verdict", "n/a")
    qa_verdict = qa_rev.get("verdict", "n/a")
    lint_mark = "x" if lint_passed else " "
    code_mark = "x" if code_verdict == "approve" else " "
    qa_mark = "x" if qa_verdict == "approve" else " "

    pr_markdown = f"""# {pr_title}

**Jira Issue:** `{jira_key}` | **Branch:** `{branch}` | **Status:** `{stop_reason}` (drafts: {drafts}/{MAX_ROUNDS})

## 1. Оцінка вимог та критерії приймання
- **Readiness:** `{plan.get("readiness_status", "ready")}` ({plan.get("readiness_score", "-")}/5)
- **Модулі SmartLease:** {", ".join(plan.get("affected_modules") or ["SmartLease"])}

{ac_md}

## 2. План та опис змін
{impl.get("summary", "")}

### Кроки реалізації
{steps_md}

### Backend (.NET Modular Monolith / PostgreSQL)
{backend_md}

### Frontend (React / TypeScript)
{frontend_md}

### Ключовий фрагмент коду
```csharp
{impl.get("code_snippets", "").strip()}
```

## 3. Локальні тести: Backend HTTP Suite & Frontend Playwright
### `tests.http`
```http
{impl.get("http_suite", "").strip()}
```

### `e2e.spec.ts`
```typescript
{impl.get("playwright_spec", "").strip()}
```

## 4. Результати верифікації та чекліст Draft PR
- [{lint_mark}] Детермінований лінт і політика безпеки {"(OK)" if lint_passed else f"(FAIL: {lint_errors})"}
- [{code_mark}] Code Review (`{code_verdict}` — security {code_rev.get("security_score", "-")}/5, architecture {code_rev.get("architecture_score", "-")}/5)
- [{qa_mark}] QA Suite Review (`{qa_verdict}` — HTTP {qa_rev.get("http_coverage_score", "-")}/5, Playwright {qa_rev.get("playwright_coverage_score", "-")}/5)

### Припущення та використаний контекст БЗ
{assumptions_md}
"""

    ctx.state["pr_draft"] = {
        "jira_key": jira_key,
        "pr_title": pr_title,
        "branch_name": branch,
        "stop_reason": stop_reason,
        "drafts": drafts,
        "lint_passed": lint_passed,
        "code_verdict": code_verdict,
        "qa_verdict": qa_verdict,
        "http_suite": impl.get("http_suite", ""),
        "playwright_spec": impl.get("playwright_spec", ""),
        "markdown": pr_markdown,
    }
    ctx.state["report"] = pr_markdown
    return _make_text_event(pr_markdown)
