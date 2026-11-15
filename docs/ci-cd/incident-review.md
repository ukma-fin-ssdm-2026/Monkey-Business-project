# Окремий інцидент main: 18–23 жовтня 2026

Використання ШІ: Codex — збір API-доказів, перевірка git diff і підготовка blameless-аналізу.

Це **історичний приклад поза основним періодом 01–14 листопада**. Він не додається до листопадових 25 змін і не замінює `н/д` для їхнього recovery time.

## Подія й підтверджена причина

Після злиття [PR #158](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/pull/158), SHA `b3df7da390c04499bf68b262202cba56ca43d650`, два workflow на `main` завершилися збоєм:

| Workflow | Run ID | Job ID | Завершення, UTC | Джерело |
|---|---|---|---|---|
| CI | 39166938505 | 117791740249 | 18.10.2026 21:14:25 | [Запуск](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/39166938505) |
| Static analysis | 39166938512 | 117791739998 | 18.10.2026 21:14:25 | [Запуск](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/39166938512) |

GitHub annotations для обох jobs повідомляють: job не запущено через невдалі платежі облікового запису **або** потребу підвищити spending limit. Повний текст збережено в [incident-api.json](evidence/incident-api.json), `runs[].jobs[].annotations`. Повідомлення не дозволяє вибрати одну з цих двох причин, тому точнішу причину оплати не стверджуємо.

В обох jobs `steps = []`. Отже, це **інфраструктурна відмова запуску перевірок**, а не підтверджений дефект застосунку чи падіння тесту. Двосекундний інтервал `started_at`–`completed_at` — службові timestamps API, не час виконання тестів.

Запит job logs повертає HTTP 404 на log storage; це явно записано у `failure_log` для кожного job. Для цього інциденту доказом причини є annotations GitHub. Відсутні логи не відтворювалися й не замінювалися вигаданим уривком.

## Як main повернулася до зеленого стану

Наступний набір запусків `push` на `main` — SHA `a0d990b05b18420ea4784dbcc99d61c282c15b77`, злитий через [PR #160](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/pull/160). Усі враховані workflow стали зеленими:

| Workflow | Run ID | Посилання |
|---|---|---|
| CI | 40007759942 | [Запуск](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/40007759942) |
| Static analysis | 40007760118 | [Запуск](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/40007760118) |
| Generate and Deploy API Docs | 40007760059 | [Запуск](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/actions/runs/40007760059) |

Останній job завершився **23.10.2026 19:00:04 UTC**. До цього між двома SHA немає інших `push`-запусків main у зібраному API-вікні. Compare API підтверджує, що зелений SHA є нащадком червоного.

```text
recovery = 2026-10-23 19:00:04Z - 2026-10-18 21:14:25Z
         = 4 дні 21 год 45 хв 39 с
         = 7065,65 хв
```

У київському часі того періоду це **19.10 00:14:25 → 23.10 22:00:04** (UTC+3 до переходу на зимовий час). Інтервал значно перевищує орієнтир 60 хвилин з умови лабораторної. API не показує, коли команда почала розслідування, тому весь інтервал не називаємо активним часом ремонту.

У [порівнянні комітів](https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/compare/b3df7da390c04499bf68b262202cba56ca43d650...a0d990b05b18420ea4784dbcc99d61c282c15b77) workflow `ci.yml`, `static-analysis.yml`, `deploy-api-docs.yml` змінюють `runs-on: ubuntu-latest` на `runs-on: [self-hosted, linux]`. Це усуває залежність цих запусків від GitHub-hosted runner, на якому виникла зафіксована відмова. У PR також змінено тестові значення й schema example; причинного твердження про них для цього інциденту без логів не робимо.

Локальна перевірка виправлення:

```bash
git diff b3df7da a0d990b -- .github/workflows/
```

## Уроки без пошуку винних

Цей випадок не доводить, що дефект коду пройшов PR-перевірки. Перевірки не отримали доступ до runner; наявні докази не дають підстав оцінювати поведінку конкретного учасника чи тогочасні налаштування branch protection.

| Спостереження | Пропозиція | Відповідальний |
|---|---|---|
| Jobs не стартують, runner-конфігурація є спільною залежністю | Перевіряти runner labels під час review workflow та додати runbook перевірки доступності runner | @mytec0l |
| Main стала зеленою лише через майже 5 діб | Визначити відповідального за pipeline, сповіщення про червоний main і ціль реагування/відновлення | @punguiin, @mytec0l |
| Детальні логи недоступні, але annotations збереглися | Архівувати job metadata, annotations і доступні failure excerpts під час наступного інциденту | @mytec0l |

## Відтворення доказів

Початковий збір обмежено двома станами main: червоним 18 жовтня і наступним зеленим 23 жовтня. Це допоміжний інтервал для інциденту, не репрезентативне вікно для основної частоти розгортань.

```powershell
.\.venv\Scripts\python.exe scripts/calculate_ci_metrics.py --from 2026-10-18T21:00:00 --to 2026-10-23T19:07:35 --timezone UTC --git-auth --evidence docs/ci-cd/evidence/incident-api.json --output docs/ci-cd/evidence/incident-results
```

Повторний підрахунок зі збережених доказів:

```powershell
.\.venv\Scripts\python.exe scripts/calculate_ci_metrics.py --offline --evidence docs/ci-cd/evidence/incident-api.json --output docs/ci-cd/evidence/incident-results
```

Повні результати допоміжного розрахунку: [JSON](evidence/incident-results/metrics-auto.json). Для зарахування відеочастини лабораторної потрібно особисто пояснити цей або інший реальний інцидент; відео цим документом не замінюється.
