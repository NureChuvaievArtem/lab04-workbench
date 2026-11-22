"""Готові SmartLease JSON-фікстури для офлайн-тестів та демо-режиму."""

from __future__ import annotations

import json

PLAN_GOOD = json.dumps(
    {
        "jira_key": "SL-142",
        "title": "Бронювання перегляду квартири з анти-спам лімітом",
        "readiness_status": "ready",
        "readiness_score": 5,
        "clarification_questions": [],
        "acceptance_criteria": [
            "POST /api/viewings доступний лише для ролі Tenant",
            "Статус оголошення має бути Active, інакше 400 Bad Request",
            "Не більше 3 заявок за 24 години, інакше 429 Too Many Requests",
        ],
        "affected_modules": ["Bookings", "Properties", "Web"],
        "implementation_steps": [
            "Створити CreateViewingCommandHandler у модулі Bookings",
            "Додати перевірку статусу Active через контракт Properties",
            "Реалізувати ViewingBookingForm у React + Playwright e2e тести",
        ],
        "test_plan": [
            "POST /api/viewings (201, 400, 401, 429) у tests.http",
            "Playwright: бронювання перегляду та валідація форми",
        ],
    },
    ensure_ascii=False,
)

IMPL_GOOD = json.dumps(
    {
        "jira_key": "SL-142",
        "branch_name": "feat/sl-142-viewings-booking",
        "summary": "Додано POST /api/viewings з анти-спам лімітом <= 3/доба, формою React, tests.http та Playwright тестами.",
        "backend_changes": [
            "Bookings/Endpoints/ViewingsController.cs: POST /api/viewings [Authorize(Roles = \"Tenant\")]",
            "Bookings/Application/CreateViewingHandler.cs: перевірка Active та ліміту 3 заявки за 24 год",
        ],
        "frontend_changes": [
            "web/src/features/viewings/ViewingBookingForm.tsx: форма вибору дати й часу перегляду",
        ],
        "code_snippets": (
            "app.MapPost(\"/api/viewings\", async (CreateViewingCmd cmd, ISender sender) =>\n"
            "    Results.Created($\"/api/viewings/{cmd.ListingId}\", await sender.Send(cmd))).RequireAuthorization();"
        ),
        "http_suite": (
            "### 1. Успішне бронювання (201)\n"
            "POST http://localhost:5000/api/viewings\n"
            "Authorization: Bearer {{tenant_token}}\n"
            "Content-Type: application/json\n\n"
            "{\"listingId\": \"d3b07384-d113-4ec6-a418-47d0d0825310\", \"viewingTime\": \"2026-12-01T14:00:00Z\"}\n\n"
            "### 2. Перевищення ліміту (429)\n"
            "POST http://localhost:5000/api/viewings\n"
            "Authorization: Bearer {{tenant_token}}\n"
        ),
        "playwright_spec": (
            "import { test, expect } from '@playwright/test';\n\n"
            "test('tenant books apartment viewing', async ({ page }) => {\n"
            "  await page.goto('/properties/d3b07384');\n"
            "  await page.click('button:has-text(\"Забронювати\")');\n"
            "  await expect(page.locator('.success-message')).toBeVisible();\n"
            "});\n"
        ),
        "assumptions": ["Дотримано [[Регламент бронювання переглядів#Анти-спам ліміт]]"],
    },
    ensure_ascii=False,
)

CODE_APPROVE = json.dumps(
    {
        "verdict": "approve",
        "security_score": 5,
        "architecture_score": 5,
        "issues": [],
        "required_fixes": [],
    },
    ensure_ascii=False,
)

QA_APPROVE = json.dumps(
    {
        "verdict": "approve",
        "http_coverage_score": 5,
        "playwright_coverage_score": 5,
        "missing_http_cases": [],
        "missing_playwright_cases": [],
        "required_fixes": [],
    },
    ensure_ascii=False,
)
