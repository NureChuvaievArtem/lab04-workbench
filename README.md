# lab04-workbench — Робоче місце розробника SmartLease

Лабораторна робота № 4 з курсу «Штучний інтелект у програмній інженерії» (ХНУРЕ, ПЗПІ-23-3).
Вебзастосунок Streamlit об'єднує базу знань SmartLease (ЛР 2) та мультиагентну SDLC-команду (ЛР 3) для **Етапу 4 «Конструювання ПЗ»**: чат із БЗ із посиланнями `obsidian://`, запуск команди агентів із живим прогресом (`st.status`), експорт артефактів (`draft_pr.md`, `tests.http`, `e2e.spec.ts`), збереження погодженого результату в `Inbox/` (`Human-in-the-loop`) та SQLite-журнал метрик з експортом у CSV.

## Запуск
```bash
uv sync --dev
cp .env.example .env            # задати GEMINI_API_KEY, OBSIDIAN_VAULT, CHROMA_PERSIST_DIR
uv run streamlit run streamlit_app.py
```

## Демонстраційний режим (без ключа API) та тести
```bash
PYTHONPATH=. uv run streamlit run tests/demo_app.py
uv run pytest -v
```
