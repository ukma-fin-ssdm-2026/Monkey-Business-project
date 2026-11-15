# Сирі дані CI/CD

Використання ШІ: Codex — скрипт збору, перерахунок і перевірка даних. Попередній ручний розрахунок збережено в `evidence/manual-baseline/`.

Дані з GitHub Actions API; [методика та відтворення](README.md), [автоматичний результат](metrics-auto.md). Час: UTC.

Один рядок — один коміт. Черга — до першого job; виконання — інтервал від першого job до завершення врахованих workflow. Він може містити внутрішні очікування.

| № | Коміт | PR | Перший коміт PR | Запуск завершено | Черга, хв | Виконання, хв | Статус | Докази |
|---|---|---|---|---|---:|---:|---|---|
| 1 | [`b3df7da`](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/commit/b3df7da390c04499bf68b262202cba56ca43d650) | [#158](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/pull/158) | 18.10 21:10:45 | 18.10 21:14:25 | 0.00 | 0.03 | red | [39166938505](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/39166938505); [39166938512](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/39166938512) |
| 2 | [`a0d990b`](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/commit/a0d990b05b18420ea4784dbcc99d61c282c15b77) | [#160](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/pull/160) | 19.10 17:15:18 | 23.10 19:00:04 | 0.03 | 1.00 | green | [40007759942](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/40007759942); [40007760059](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/40007760059); [40007760118](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/40007760118) |
