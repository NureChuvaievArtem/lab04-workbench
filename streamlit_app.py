"""Робоче місце розробника SmartLease: база знань (ЛР 2) + МАС етапу Конструювання (ЛР 3).

Запуск: uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from workbench.service import WorkbenchService, build_service

MAX_TEAM_RUNS = 10

NODE_LABELS = {
    "intake_jira": "Валідація Jira-запиту",
    "retrieve_context": "Пошук архітектурних правил у БЗ",
    "requirements_planner": "Оцінка вимог і формування плану",
    "readiness_gate": "Перевірка готовності вимог",
    "implementer": "Генерація змін коду, .http та Playwright тестів",
    "lint_and_policy_check": "Статичний лінт і перевірка політики безпеки",
    "code_reviewer": "Рев'ю безпеки й модульного моноліту",
    "qa_suite_reviewer": "Перевірка .http API та Playwright покриття",
    "reviews": "Синхронізація паралельних рецензій (JoinNode)",
    "pr_gate": "Консолідація вердиктів і контроль циклу",
    "build_draft_pr": "Формування пакета Draft Pull Request",
    "build_clarification_report": "Підготовка списку запитань уточнення",
    "reject": "Відхилення некоректного запиту",
}

st.set_page_config(
    page_title="Робоче місце розробника SmartLease",
    page_icon="🛠️",
    layout="wide",
)


@st.cache_resource
def cached_service() -> WorkbenchService:
    return build_service()


def get_service() -> WorkbenchService | None:
    if "service" in st.session_state:
        return st.session_state["service"]
    try:
        return cached_service()
    except Exception as exc:
        st.error(f"Не вдалося запустити сервіс: {exc}")
        st.info(
            "Перевірте файл .env (GEMINI_API_KEY, OBSIDIAN_VAULT, CHROMA_PERSIST_DIR) "
            "та індекс бази знань ЛР 2."
        )
        return None


service = get_service()
if service is None:
    st.stop()

state = st.session_state
state.setdefault("messages", [])
state.setdefault("team_runs", 0)

tab_ask, tab_team, tab_history = st.tabs(
    ["Питання до бази знань", "Команда агентів", "Історія і метрики"]
)

# ------------------------------------------------------------------ Вкладка 1: БЗ
with tab_ask:
    for message in state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Запитайте про архітектуру, Outbox, модулі або SLA SmartLease")
    if question:
        state.messages.append({"role": "user", "content": question})
        with st.status("Агент шукає в базі знань…", expanded=False) as status:
            def log_kb(event: dict) -> None:
                if event["author"] != "user" and event["text"]:
                    status.write(f"{event['author']}: {event['text'][:90]}")

            answer = service.ask(question, on_event=log_kb)
            status.update(label="Відповідь готова", state="complete")

        sources_md = "\n".join(f"- [{s['label']}]({s['url']})" for s in answer.sources)
        content = answer.linked_text + (
            f"\n\n**Фрагменти, знайдені агентом:**\n{sources_md}" if sources_md else ""
        )
        if answer.invalid_citations:
            content += (
                "\n\n:warning: Посилання без підтвердження: "
                + ", ".join(answer.invalid_citations)
            )
        state.messages.append({"role": "assistant", "content": content})
        st.rerun()

# ------------------------------------------------------------- Вкладка 2: Команда
with tab_team:
    with st.form("team_form"):
        request = st.text_area(
            "Опис Jira-задачі для етапу Конструювання",
            height=120,
            placeholder=(
                "SL-142: Реалізувати POST /api/viewings для бронювання перегляду квартири "
                "з анти-спам лімітом 3/доба, формою React та .http і Playwright тестами."
            ),
        )
        submitted = st.form_submit_button(
            "Запустити команду",
            disabled=state.team_runs >= MAX_TEAM_RUNS,
        )

    if submitted and request.strip():
        state.team_runs += 1
        with st.status("Команда агентів працює (орієнтовно 20–45 с)…", expanded=True) as status:
            def show_step(event: dict) -> None:
                base = event["node"].split("@")[0]
                if base in NODE_LABELS:
                    route = f" → {event['route']}" if event["route"] else ""
                    elapsed = f"[{event['t']:.1f} с] " if "t" in event else ""
                    status.write(f"{elapsed}{NODE_LABELS[base]}{route}")

            state.last_run = service.run_team(request.strip(), on_event=show_step)
            status.update(label="Готово", state="complete", expanded=False)

    run = state.get("last_run")
    if run:
        cols = st.columns(4)
        cols[0].metric("Чернеток", run.result.state.get("drafts", "—"))
        cols[1].metric("Викликів LLM", sum(run.result.llm_calls.values()))
        cols[2].metric("Токенів", run.result.tokens)
        cols[3].metric("Час, с", run.result.seconds)

        st.markdown(run.report)

        if run.http_suite or run.playwright_spec:
            with st.expander("Попередній перегляд тестових артефактів (.http і Playwright)"):
                if run.http_suite:
                    st.code(run.http_suite, language="http")
                if run.playwright_spec:
                    st.code(run.playwright_spec, language="typescript")

        c1, c2, c3 = st.columns(3)
        slug_key = run.jira_key.lower()
        c1.download_button(
            "Завантажити draft_pr.md",
            run.pr_md,
            file_name=f"{slug_key}_draft_pr.md",
        )
        if run.http_suite:
            c2.download_button(
                "Завантажити tests.http",
                run.http_suite,
                file_name=f"{slug_key}_tests.http",
            )
        if run.playwright_spec:
            c3.download_button(
                "Завантажити e2e.spec.ts",
                run.playwright_spec,
                file_name=f"{slug_key}_e2e.spec.ts",
            )

        st.subheader("Перевірка людиною (Human-in-the-loop)")
        reviewer = st.text_input("Ваше ім'я (рецензент)")
        confirmed = st.checkbox(
            "Я перевірив план, код, .http/Playwright тести та результати рев'ю"
        )
        if st.button(
            "Зберегти в Obsidian (Inbox)",
            disabled=not (confirmed and reviewer.strip()),
        ):
            saved_path = service.save_result(run, reviewer)
            st.success(f"Збережено в Inbox: {saved_path.name}. Переіндексуйте базу знань за потреби.")

        rating = st.feedback("thumbs", key=f"rate_{run.run_id}")
        if rating is not None:
            service.rate(run.run_id, positive=bool(rating))

# ------------------------------------------------------------- Вкладка 3: Історія
with tab_history:
    summary = service.history.summary()
    mcols = st.columns(4)
    mcols[0].metric("Запусків", summary["runs"] or 0)
    mcols[1].metric("Сер. викликів LLM", round(summary["avg_calls"] or 0, 1))
    mcols[2].metric("Сер. час, с", round(summary["avg_seconds"] or 0, 1))
    share = summary["positive_share"]
    mcols[3].metric("Позитивних оцінок", "—" if share is None else f"{share:.0%}")

    rows = service.history.list()
    if rows:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, hide_index=True)
        st.caption(
            "Примітка: колонка saved_path заповнюється після підтвердження збереження в Obsidian (Inbox)."
        )
        st.download_button(
            "Експорт CSV",
            frame.to_csv(index=False),
            file_name="runs.csv",
            mime="text/csv",
        )
    else:
        st.caption("Запусків ще немає.")

# Бічна панель відображається наприкінці, щоб лічильник врахував поточний запуск
with st.sidebar:
    st.header("Робоче місце розробника")
    st.caption("Етап ЖЦ ПЗ: 4 — Конструювання (SmartLease)")
    st.metric("Запусків команди в сесії", f"{state.team_runs} / {MAX_TEAM_RUNS}")
    st.caption(f"Сховище Obsidian: {service.vault_name or 'не налаштовано'}")
