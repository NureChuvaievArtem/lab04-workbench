"""Pydantic-схеми контрактів даних між вузлами SDLC-графа SmartLease."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequirementsAndPlan(BaseModel):
    """Оцінка готовності Jira issue та план реалізації фічі SmartLease."""

    jira_key: str = Field(description="Ідентифікатор Jira issue, наприклад SL-142.")
    title: str = Field(description="Коротка назва задачі / майбутнього PR.")
    readiness_status: Literal["ready", "needs_clarification"] = Field(
        description="Статус готовності вимог до конструювання."
    )
    readiness_score: int = Field(
        ge=1,
        le=5,
        description="Оцінка повноти й чіткості вимог від 1 (незрозуміло) до 5 (чітко).",
    )
    clarification_questions: list[str] = Field(
        default_factory=list,
        description="Перелік уточнювальних запитань, якщо вимоги неповні.",
    )
    acceptance_criteria: list[str] = Field(
        description="Конкретні критерії приймання для перевірки коду і тестів."
    )
    affected_modules: list[str] = Field(
        description="Модулі SmartLease (наприклад Properties, Bookings, Leases, Identity, Web)."
    )
    implementation_steps: list[str] = Field(
        description="Послідовні технічні кроки реалізації Backend (.NET) і Frontend (React)."
    )
    test_plan: list[str] = Field(
        description="План перевірки: сценарії .http для API та Playwright e2e для UI."
    )


class ImplementationBundle(BaseModel):
    """Пакет змін розробника: бекенд/фронтенд, сніпети, .http та Playwright тести."""

    jira_key: str = Field(description="Ідентифікатор Jira issue.")
    branch_name: str = Field(
        description="Назва Git-гілки у форматі feat/sl-xxx-short-name."
    )
    summary: str = Field(description="Стислий технічний опис запропонованих змін.")
    backend_changes: list[str] = Field(
        description="Зміни в модулях C# / .NET 10 та міграціях PostgreSQL."
    )
    frontend_changes: list[str] = Field(
        description="Зміни в React / TypeScript компонентах, хуках і маршрутах."
    )
    code_snippets: str = Field(
        description="Ключовий фрагмент коду або псевдо-диф реалізації (C# / TS)."
    )
    http_suite: str = Field(
        description="Набір HTTP-запитів формату .http для локальної перевірки API."
    )
    playwright_spec: str = Field(
        description="Playwright TypeScript сценарій (.spec.ts) для перевірки фронтенду."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Припущення та посилання на знайдені фрагменти бази знань.",
    )


class CodeReviewReport(BaseModel):
    """Висновок незалежного код-рев'ю щодо архітектури SmartLease і безпеки."""

    verdict: Literal["approve", "revise"] = Field(
        description="Вердикт код-рев'ю: approve або revise."
    )
    security_score: int = Field(
        ge=1,
        le=5,
        description="Оцінка безпеки (авторизація, валідація, IDOR) від 1 до 5.",
    )
    architecture_score: int = Field(
        ge=1,
        le=5,
        description="Оцінка відповідності модульному моноліту та БД від 1 до 5.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Виявлені дефекти чи архітектурні зауваження.",
    )
    required_fixes: list[str] = Field(
        default_factory=list,
        description="Конкретні виправлення, потрібні перед Draft PR.",
    )


class QaVerificationReport(BaseModel):
    """Висновок QA-рев'ювера щодо покриття .http API та Playwright UI тестами."""

    verdict: Literal["approve", "revise"] = Field(
        description="Вердикт QA-верифікації: approve або revise."
    )
    http_coverage_score: int = Field(
        ge=1,
        le=5,
        description="Повнота набору .http запитів для беку від 1 до 5.",
    )
    playwright_coverage_score: int = Field(
        ge=1,
        le=5,
        description="Повнота Playwright e2e сценаріїв для фронту від 1 до 5.",
    )
    missing_http_cases: list[str] = Field(
        default_factory=list,
        description="Непокриті API-кейси (помилки 400/401/403/404, граничні умови).",
    )
    missing_playwright_cases: list[str] = Field(
        default_factory=list,
        description="Непокриті UI-сценарії користувача у Playwright.",
    )
    required_fixes: list[str] = Field(
        default_factory=list,
        description="Конкретні доповнення до .http або Playwright тестів.",
    )


class SoloResult(BaseModel):
    """Еквівалентна єдина схема результату для baseline solo-агента."""

    jira_key: str = Field(description="Ідентифікатор Jira issue.")
    title: str = Field(description="Назва задачі та Draft PR.")
    readiness_status: Literal["ready", "needs_clarification"] = Field(
        description="Оцінка готовності вимог."
    )
    implementation_steps: list[str] = Field(
        description="План реалізації задачі."
    )
    backend_changes: list[str] = Field(
        description="Перелік змін бекенду SmartLease."
    )
    frontend_changes: list[str] = Field(
        description="Перелік змін фронтенду SmartLease."
    )
    http_suite: str = Field(
        description="Локальний набір .http тестів для API."
    )
    playwright_spec: str = Field(
        description="Playwright тест-сценарій (.spec.ts) для фронтенду."
    )
    review_notes: list[str] = Field(
        default_factory=list,
        description="Нотатки самоперевірки щодо безпеки та якості.",
    )
    pr_title: str = Field(description="Заголовок Draft Pull Request.")
    pr_body: str = Field(description="Текст опису Draft Pull Request.")
