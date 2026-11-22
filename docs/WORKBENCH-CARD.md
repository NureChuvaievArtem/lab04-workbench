# WORKBENCH-CARD: Робоче місце Full-Stack розробника SmartLease

## 1. Мета й аудиторія
- **Етап ЖЦ ПЗ:** 4 — Конструювання ПЗ (*Implementation / Construction*).
- **Роль користувача:** Full-Stack розробник платформи оренди нерухомості **SmartLease** (.NET 10 Modular Monolith + PostgreSQL 17 + React/TypeScript).
- **Задача, яку прискорює робоче місце:** перетворення постановки Jira-задачі на узгоджений пакет конструювання — покроковий план модульних змін, специфікацію коду, набір HTTP-перевірок (`tests.http`), наскрізний тест (`e2e.spec.ts`), автоматичні результати статичного лінту та паралельного код-/QA-рев'ю з опорою на корпоративні ADR та інваріанти бази знань.
- **Очікуваний ефект:** скорочення часу на підготовку плану реалізації й Draft PR, уникнення міжмодульних порушень та дефектів безпеки (IDOR, Outbox, дедуплікація) до передачі задачі в PR Review / QA.

## 2. Архітектура та шари
Застосунок побудовано за 4-шаровою архітектурою зі строгим відокремленням UI від агентів і сховища даних:

| Шар | Модуль(і) | Відповідальність |
| --- | --- | --- |
| Інтерфейс користувача | `streamlit_app.py` | 3 вкладки (`Питання до бази знань`, `Команда агентів`, `Історія і метрики`), прогрес у `st.status`, кешування сервісу `@st.cache_resource`, форми, ліміт `MAX_TEAM_RUNS = 10`, шлюз підтвердження `Human-in-the-loop`. Не імпортує `app.*` чи `kb.*` напряму. |
| Сервісний шар | `workbench/service.py` (`WorkbenchService`), `workbench/runner.py` | Єдиний фасад бізнес-сценаріїв (`ask()`, `run_team()`, `save_result()`, `rate()`, `obsidian_url()`), переклад `[[Нотатка#Розділ]]` у `obsidian://`, виявлення непідтверджених посилань, синхронний міст до ADK (`run_agent()`). |
| Агенти та інтеграція БЗ | `app/kb_assistant.py`, `app/agent.py`, `app/nodes.py`, `app/agents.py`, `app/schemas.py` | Чат-асистент БЗ з інструментами `search_knowledge` / `read_note` та МАС-граф конструювання з детермінованим вузлом `retrieve_context`. |
| Дані, індекс та експорт | `kb/*`, `workbench/exporters.py`, `workbench/storage.py` | Векторний індекс ChromaDB (`smartlease_kb`, 49 фрагментів, 16 нотаток Obsidian), журнал SQLite (`workbench.db`), експорт `draft_pr.md`, `tests.http`, `e2e.spec.ts` та збереження в `Inbox/`. |

## 3. Інтеграція бази знань та МАС
- **Точка входу БЗ у МАС:** вузол-функція `retrieve_context` у `app/agent.py`, що викликається одразу після `intake_jira` (параметр `use_kb_agent=False` у `build_service()`). Пошук виконується без додаткового виклику LLM через векторний індекс `ChromaDB` (фільтр відстані `KB_MAX_DISTANCE = 0.28`, `gemini-embedding-001`) та записується у стан графа `kb_context` із метаданими `<fragment source="[[...]]" path="...">`.
- **Повернення результатів (Human-in-the-loop):** погоджений звіт Draft PR може бути записаний у папку `Inbox/` сховища Obsidian **лише** через `WorkbenchService.save_result()` після заповнення імені рецензента та явного підтвердження чекбоксом. Існуючі нотатки ніколи не перезаписуються (`_2`, `_3`, ...), а шлях перевіряється на вихід за межі сховища (`ValueError`).
- **Перевірка джерел у чаті:** `WorkbenchService.ask()` звіряє всі згадки `[[Нотатка#Розділ]]` у фінальній відповіді з тегами `source="[[...]]"` у фактичних виводах інструментів. Підтверджені посилання стають клікабельними `obsidian://`, а непідтверджені виводяться окремим попередженням.

## 4. Експлуатаційні заходи безпеки
- **Мережева ізоляція:** `.streamlit/config.toml` фіксує `server.address = "localhost"`, `browser.gatherUsageStats = false`, `server.maxUploadSize = 5`, `client.toolbarMode = "viewer"`.
- **Захист від Prompt Injection:** інструкції агентів (`app/kb_assistant.py`, `app/kb_connector.py`) явно наказують ігнорувати директиви всередині знайдених нотаток або тіла Jira-запиту; вхідні дані проходять детермінований лінт (`lint_and_policy_check`) і перевірку шляхів.
- **Обмеження ресурсів:** максимум 10 командних запусків за сесію (`MAX_TEAM_RUNS = 10` у `streamlit_app.py`), максимум 2 цикли доопрацювання в МАС (`pr_gate`), ліміт символів у `to_draft_pr_md` та відсутність автоматичного перезапису файлової системи поза `Inbox/`.
- **Безпека секретів і контейнера:** `.env` і `workbench.db` виключені з git та архіву через `.gitignore`; у `Dockerfile` застосунок працює від непривілейованого користувача `appuser` з окремими томами `/vault`, `/chroma_data`, `/data`.

## 5. Артефакти експорту та їх передача
1. **`{jira_key}_draft_pr.md`** — опис Draft Pull Request (архітектурна прив'язка, міграція, ендпоінти, чекліст безпеки) для Stage 5 (PR Review / Team Lead).
2. **`{jira_key}_tests.http`** — декларативний набір HTTP-запитів (`@baseUrl`, сценарії `201/200` та `403/409` помилок) для миттєвого прогону у VS Code REST Client / Rider.
3. **`{jira_key}_e2e.spec.ts`** — каркас Playwright-тесту (`import { test, expect } from '@playwright/test'`) для Stage 5/6 (QA Automation).
4. **Нотатка в Obsidian `Inbox/`** — артефакт накопичення інженерного досвіду з YAML frontmatter (`status: draft`, `reviewer`, `run_id`, `created`).

## 6. Результати перевірки та 10 реальних сесій
- **Автотести (`uv run pytest -v`):** `13 passed, 1 skipped` (усі 13 модульних, сервісних та `AppTest` UI тестів пройдено без реальної моделі за допомогою `ToolCallingLlm` і `ScriptedLlm`; E2E Playwright у базовому WSL пропущено через відсутність системної бібліотеки `libnspr4.so`).
- **Наскрізний Playwright E2E (`tests/e2e/test_playwright_demo.py`, крок 14):** пройдено (`1 passed in 4.10s`) із браузера Windows Chrome проти `tests/demo_app.py` (перевірено вкладку БЗ, генерацію та блокування `Зберегти в Obsidian (Inbox)` до підтвердження людиною, експорт у журналі).
- **10 реальних запусків (`eval/run_real_sessions.py` на моделі `gemini-3.5-flash-lite`):**
  - 5 запитів до БЗ (`ask`) + 5 запусків команди (`run_team`: `SL-142`, `SL-148`, `SL-151`, `SL-155`, `SL-160`);
  - всього викликів / середнє: `3.0` виклики LLM за запуск, `26.78 с` середній час, `43 843` токенів сумарно, частка позитивних оцінок `90%` (`9/10`; у одному запиті до БЗ виявлено 1 непідтверджену підсекцію `invalid_citations`, 4/5 командних запусків затверджено як `approved` і 1 валідно зупинено на `needs_clarification` для неконкретного `SL-151`);
  - результати збережено у `eval/real_runs.csv` та `eval/real_summary.json`.

## 7. Юзабіліті-оцінювання (SUS)
- Скрипт розрахунку `eval/sus.py` реалізовано та перевірено модульним тестом `tests/unit/test_sus.py`.
- На демонстраційних контрольних даних `eval/sus_example.csv` (3 відповіді: `77.5`, `70.0`, `85.0`) утиліта повертає `SUS mean = 77.5` (рівень «Добре»).
- **Стан польового тестування:** сесію з 3 незалежними користувачами та реальними CSV-анкетами не сфабриковано; після розгортання користувачем анкети зберігаються в окремий CSV і підраховуються командою `uv run python -m eval.sus <file.csv>`.

## 8. Запуск і відтворення
```bash
# 1. Встановлення залежностей та налаштування .env
uv sync --extra dev

# 2. Локальний запуск Streamlit-застосунку
uv run streamlit run streamlit_app.py

# 3. Автотести без витрати токенів API та E2E-перевірка
uv run pytest -v
```
Контейнерний запуск (крок 15, non-root `appuser`):
```bash
docker build -t smartlease-workbench .
docker run -p 8501:8501 --env-file .env \
  -v /path/to/kb-vault:/vault \
  -v /path/to/chroma_data:/chroma_data \
  smartlease-workbench
```
