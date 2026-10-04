# Трекер підготовки до технічних співбесід

## Короткий опис

Інструмент для систематизації пошуку роботи та підготовки до співбесід. В основі - Канбан-дошка, де користувач додає вакансії та переміщує їх між етапами: Відгук, Скринінг, Технічне інтерв'ю, Офер. Система дозволяє зберігати вимоги вакансії, прикріплювати посилання на тестові завдання та вести нотатки з фідбеком від рекрутерів.

## CI Status
[![CI Test](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/workflows/ci.yml)

## Документація API
**[GitHub Pages](https://ukma-fin-ssdm-2026.github.io/Monkey-Business-project/)**

## Команда

| Ім'я | GitHub | Роль (Lab 4) |
|---|---|---|
| Nikita Dyshlyuk | [@mytec0l](https://github.com/mytec0l) | Integration Lead |
| Nazar Sydorchuk | [@punguiin](https://github.com/punguiin) | Quality Lead |
| Oleksii Volik | [@saoleksii](https://github.com/saoleksii) | Documentation Lead |
| Mykola Vashchenko | [@MykolaVashchenko](https://github.com/MykolaVashchenko) | Backend Lead / API Design Lead |

## Стратегія розробки
Використовуємо GitHub Flow: зміни в `main` вносяться лише через Pull Request з проходженням CI та щонайменше одним схваленням.

## Артефакти вимог
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

## Документи
- [TeamCharter.md](./TeamCharter.md) — командний статут
- [Project-Description.md](./Project-Description.md) — опис проєкту
- [docs/TaskWorkflow.md](./docs/TaskWorkflow.md) — робочий процес завдань (issues)

## Використання ШІ
- **Інструмент:** Gemini
- **Застосування:** допомога у структуруванні розділів, оформленні Markdown-таблиць та підборі чітких, лаконічних формулювань для опису проєкту
- **Верифікація:** посилання, ролі учасників та зміст опису повністю перевірені й затверджені командою вручну
