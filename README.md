# Трекер підготовки до технічних співбесід

## Короткий опис

Інструмент для систематизації пошуку роботи та підготовки до співбесід. В основі - Канбан-дошка, де користувач додає вакансії та переміщує їх між етапами: Відгук, Скринінг, Технічне інтерв'ю, Офер. Система дозволяє зберігати вимоги вакансії, прикріплювати посилання на тестові завдання та вести нотатки з фідбеком від рекрутерів.

## CI Status
[![CI Test](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/workflows/ci.yml)

## Команда

| Ім'я | GitHub | Роль |
|---|---|---|
| Nikita Dyshlyuk | [@mytec0l](https://github.com/mytec0l) | Documentation Lead |
| Nazar Sydorchuk | [@punguiin](https://github.com/punguiin) | Requirements Lead |
| Oleksii Volik | [@saoleksii](https://github.com/saoleksii) | Quality Lead |
| Mykola Vashchenko | [@MykolaVashchenko](https://github.com/MykolaVashchenko) | Traceability Lead |

## Стратегія розробки
Використовуємо GitHub Flow: зміни в `main` вносяться лише через Pull Request з проходженням CI та щонайменше одним схваленням.

## Артефакти вимог
- [Вимоги до системи (FR та NFR)](./docs/requirements/requirements.md) — функціональні та нефункціональні вимоги (ISO 25010)
- [Користувацькі історії](./docs/requirements/user-stories.md) — користувацькі історії з критеріями прийняття (INVEST)
- [Матриця простежуваності (RTM)](./docs/requirements/rtm.md) — зв'язок User Stories → FR → NFR → Test Cases

## Документи
- [TeamCharter.md](./TeamCharter.md) — командний статут
- [Project-Description.md](./Project-Description.md) — опис проєкту
- [docs/TaskWorkflow.md](./docs/TaskWorkflow.md) — робочий процес завдань (issues)
