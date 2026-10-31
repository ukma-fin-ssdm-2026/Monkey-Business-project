# Трекер підготовки до технічних співбесід

## Короткий опис

Інструмент для систематизації пошуку роботи та підготовки до співбесід. В основі - Канбан-дошка, де користувач додає вакансії та переміщує їх між етапами: Відгук, Скринінг, Технічне інтерв'ю, Офер. Система дозволяє зберігати вимоги вакансії, прикріплювати посилання на тестові завдання та вести нотатки з фідбеком від рекрутерів.

## CI Status
[![CI Test](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/workflows/ci.yml)

## Документація API
**[GitHub Pages](https://ukma-fin-ssdm-2026.github.io/Monkey-Business-project/)**

## Запуск

Детальні інструкції щодо розгортання компонентів:
- **Бекенд та База даних:** [src/api/README.md](src/api/README.md)
- **Фронтенд:** [src/frontend/README.md](src/frontend/README.md)

Для успішного надсилання запрошень менторам через `docker-compose.yml` необхідний токен API. Отримайте його на сайті Mailtrap.io у налаштуваннях вашого Inboxes/API та додайте в .env або експортуйте як змінну середовища перед запуском:
`export MAILTRAP_API_TOKEN="ваш_токен"`

## Команда

| Ім'я | GitHub | Роль (Lab 8) |
|---|---|---|
| Nikita Dyshlyuk | [@mytec0l](https://github.com/mytec0l) | Testing Engineer |
| Nazar Sydorchuk | [@punguiin](https://github.com/punguiin) | Code & Security Analyst |
| Oleksii Volik | [@saoleksii](https://github.com/saoleksii) | Refactoring Lead |
| Mykola Vashchenko | [@MykolaVashchenko](https://github.com/MykolaVashchenko) | Release manager |

## Стратегія розробки
Використовуємо GitHub Flow: зміни в `main` вносяться лише через Pull Request з проходженням CI та щонайменше одним схваленням. Стандарт кодування, обов'язкові інструменти, кроки огляду коду та критерії готовності описано в [політиці якості та огляду коду](./TeamCharter.md#5-політика-якості-та-огляду-коду).

## Артефакти вимог
- [Міні-ТЗ (Project Description)](Project-Description.md)
- [Вимоги до системи (FR та NFR)](./docs/requirements/requirements.md) — функціональні та нефункціональні вимоги (ISO 25010)
- [Користувацькі історії](./docs/requirements/user-stories.md) — користувацькі історії з критеріями прийняття (INVEST)
- [Матриця простежуваності (RTM)](./docs/requirements/rtm.md) — зв'язок User Stories → FR → NFR → Test Cases

## Артефакти архітектури
- [Архітектурний огляд](./docs/architecture/high-level-design.md) — обраний архітектурний стиль, ключові компоненти системи
- [Матриця простежуваності архітектури](./docs/architecture/traceability-matrix.md) — зв'язок вимог (FR/NFR/US) → компонент → проєктне рішення (ADR) → метод верифікації
- [Модель даних](./docs/architecture/data-model.md) — ER-модель, персональні та чутливі дані
- [Модель загроз (STRIDE)](./docs/architecture/threat-model.md) — ризики за схемою STRIDE та контрзаходи
- UML-діаграми (`./docs/architecture/uml/`):
  - [Діаграма компонентів](./docs/architecture/uml/component-diagram.png)
  - [Діаграма послідовності](./docs/architecture/uml/sequence-diagram.png)
  - [Діаграма розгортання](./docs/architecture/uml/deployment-diagram.png)
  - [ER-модель даних](./docs/architecture/uml/data-model.puml) ([*рендер*](./docs/architecture/uml/data-model.png))
- Архітектурні рішення (ADR):
  - [ADR-001: Frontend-архітектура (React + PWA)](./docs/architecture/decisions/ADR-001.md)
  - [ADR-002: Backend та база даних (FastAPI + PostgreSQL)](./docs/architecture/decisions/ADR-002.md)
  - [ADR-003: Система моніторингу (Prometheus + Grafana)](./docs/architecture/decisions/ADR-003.md)

## Артефакти API
- [Код API з анотаціями](./src/api/) — код API з анотаціями для автогенерації
- [OpenAPI специфікація](./docs/api/openapi-generated.yaml) — автоматично згенерована специфікація OpenAPI
- [Проєктні рішення (API Design)](./docs/api/api-design.md) — документація проєктних рішень
- [Атрибути якості](./docs/api/quality-attributes.md) — атрибути якості
- [Swagger UI](./docs/api/index.html) — сторінка Swagger UI

## Артефакти якості коду
- [Звіт огляду коду](./docs/code-quality/review-report.md) — огляд коду команди Spectrum і порівняння з ШІ-оглядом
- [Статичний аналіз](./docs/code-quality/static-analysis.md) — black, flake8, bandit, detect-secrets і Dependabot: результати, знахідки та рішення
- [Прогрес реалізації](./docs/code-quality/progress.md) — структура коду та реалізовані компоненти бекенду
- [Політика якості та огляду коду](./TeamCharter.md#5-політика-якості-та-огляду-коду) — стандарт кодування, обов'язкові інструменти, кроки огляду, Definition of Done
- Конфігурація перевірок: [`.pre-commit-config.yaml`](./.pre-commit-config.yaml), [`.flake8`](./.flake8), [`pyproject.toml`](./pyproject.toml), [`static-analysis.yml`](./.github/workflows/static-analysis.yml)

## Тестування — Лаб06

- [Модульні тести](./tests/) і [HTML-звіт покриття](./coverage.xml).
- [Стратегія тестування](./docs/testing/testing-strategy.md) та [журнал налагодження](./docs/testing/debugging-log.md).
- Запуск із кореня: `python -m pytest`; генерує HTML/XML і перевіряє поріг 70% для всього `src/api` з урахуванням гілок.

## Валідація — Лаб07

- [План тестування](./docs/validation/test-plan.md) — сценарії TP-01–TP-14, власники, вимоги й команди запуску.
- [Журнал оглядів і результатів](./docs/validation/review-log.md) — відгук команди Spectrum, внесені зміни, огляд ШІ-коду та результати TP-03/TP-04.
- [Матриця простежуваності](./docs/requirements/rtm.md) і [JUnit-звіт локального прогону](./docs/validation/pytest-results.xml).
- [CI для порядку карток із PostgreSQL](./.github/workflows/lab07-card-order.yml).

## Документи проєкту
- [TeamCharter.md](./TeamCharter.md) — командний статут
- [Project-Description.md](./Project-Description.md) — опис проєкту
- [docs/TaskWorkflow.md](./docs/TaskWorkflow.md) — робочий процес завдань (issues)

## Використання ШІ
- **Інструмент:** Gemini
- **Застосування:** допомога у структуруванні розділів, оформленні Markdown-таблиць та підборі чітких, лаконічних формулювань для опису проєкту
- **Верифікація:** посилання, ролі учасників та зміст опису повністю перевірені й затверджені командою вручну

Оновлення для Лабораторної роботи 5:
- **Інструмент:** Claude
- **Застосування:** оновлення таблиці ролей і додавання розділу «Артефакти якості коду»
- **Верифікація:** наявність усіх файлів за посиланнями перевірено в репозиторії; ролі звірено з авторством артефактів Лабораторної роботи 5
