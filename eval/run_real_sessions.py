"""Виконує >= 10 справжніх запусків робочого місця на реальній БЗ SmartLease і Gemini (крок 12)."""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from workbench.service import build_service  # noqa: E402

ASK_QUERIES = [
    "Як працює патерн Transactional Outbox і дедуплікація подій у SmartLease?",
    "Які обмеження міжмодульної взаємодії діють у модульному моноліті SmartLease?",
    "Які умови повернення гарантійного депозиту орендарю в модулі Finance?",
    "Які вимоги SLA встановлено для аварійних заявок Emergency в Maintenance?",
    "Як у системі SmartLease налаштована автентифікація і ролі користувачів?",
]

TEAM_TASKS = [
    "SL-142: Реалізувати бронювання перегляду квартири POST /api/viewings лише для Tenant, статус Active, ліміт <= 3/доба, форма React, .http і Playwright тести.",
    "SL-148: Додати скасування договору оренди PATCH /api/leases/{id}/cancel з перевіркою власника або орендаря (захист від IDOR), аудит у PostgreSQL та модалкою в React.",
    "SL-151: Додати розумні сповіщення про оренду і гнучкі бонусні знижки в SmartLease якомога швидше.",
    "SL-155: Додати фільтрацію каталогу оголошень GET /api/listings (ціна, кімнати, тварини, пагінація) та синхронізацію URL у React з .http і Playwright.",
    "SL-160: Додати ідемпотентний платіжний webhook POST /api/payments/webhook з дедуплікацією та відображенням бейджа Paid на сторінці рахунків.",
]


def run_with_retry(fn, label: str, attempts: int = 3):
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            print(f"[WARN {label} attempt {i}/{attempts}] {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            if i == attempts:
                raise
            time.sleep(10 * i)


def main() -> None:
    db_path = ROOT / "workbench.db"
    if db_path.exists():
        db_path.unlink()

    svc = build_service()
    summary_details = []

    for idx, q in enumerate(ASK_QUERIES, 1):
        print(f"[ASK {idx}/5] {q[:70]}...", flush=True)
        ans = run_with_retry(lambda q=q: svc.ask(q), f"ask_{idx}")
        positive = bool(ans.sources) and not ans.invalid_citations
        svc.rate(ans.run_id, positive=positive)
        print(
            f"  -> id={ans.run_id} sources={len(ans.sources)} invalid={len(ans.invalid_citations)} "
            f"calls={sum(ans.result.llm_calls.values())} tok={ans.result.tokens} t={ans.result.seconds}s rate={int(positive)}",
            flush=True,
        )
        summary_details.append({
            "kind": "ask",
            "run_id": ans.run_id,
            "sources": [s["label"] for s in ans.sources],
            "invalid_citations": ans.invalid_citations,
            "rated": int(positive),
        })
        time.sleep(4)

    for idx, task in enumerate(TEAM_TASKS, 1):
        print(f"[TEAM {idx}/5] {task[:70]}...", flush=True)
        run = run_with_retry(lambda t=task: svc.run_team(t), f"team_{idx}")
        positive = run.stop_reason in {"approved", "needs_clarification"}
        svc.rate(run.run_id, positive=positive)
        print(
            f"  -> id={run.run_id} jira={run.jira_key} stop={run.stop_reason} "
            f"calls={sum(run.result.llm_calls.values())} tok={run.result.tokens} t={run.result.seconds}s rate={int(positive)}",
            flush=True,
        )
        summary_details.append({
            "kind": "team",
            "run_id": run.run_id,
            "jira_key": run.jira_key,
            "stop_reason": run.stop_reason,
            "drafts": run.result.state.get("drafts", 0),
            "has_http": bool(run.http_suite),
            "has_pw": bool(run.playwright_spec),
            "rated": int(positive),
        })
        time.sleep(5)

    rows = svc.history.list(limit=100)
    csv_path = ROOT / "eval" / "real_runs.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    agg = svc.history.summary()
    (ROOT / "eval" / "real_summary.json").write_text(
        json.dumps({"summary": agg, "details": summary_details}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\n=== REAL RUNS SUMMARY ===")
    print(agg)
    print(f"Exported CSV -> {csv_path}")


if __name__ == "__main__":
    main()
