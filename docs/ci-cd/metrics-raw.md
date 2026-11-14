# Сирі дані CI/CD

Розгортання – зелений запуск на `main`. Враховано `CI`, `Static analysis`, `Lab07 card ordering`, `Lab08 characterization tests` і умовний `Generate and Deploy API Docs` (коли він запускався за `paths`). Коміт зелений, якщо всі workflow для нього завершилися успішно. Єдина основна вибірка: 01.11–14.11.2026 за Києвом, 23 commit-level записи.

| № | Коміт | PR | Перший коміт PR | Запуск завершено | Черга, хв | Виконання, хв | Статус | Примітка |
|---|-------|----|-----------------|------------------|-----------|---------------|--------|----------|
| 1 | `124ce67` | #194 | 01.11 02:04 | 01.11 12:03 | 0.0 | 0.9 | ✅ | CI; Lab07 card ordering; Static analysis |
| 2 | `268e753` | #195 | 01.11 18:47 | 01.11 19:10 | 0.1 | 13.8 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Static analysis |
| 3 | `cdd0b9e` | #196 | 01.11 19:07 | 01.11 20:03 | 3.0 | 13.9 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Lab08 characterization tests; Static analysis |
| 4 | `4eb3035` | #197 | 01.11 19:55 | 01.11 20:20 | 6.0 | 10.9 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Lab08 characterization tests; Static analysis |
| 5 | `3184d4f` | #198 | 01.11 21:45 | 02.11 00:56 | 26.3 | 103.2 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Lab08 characterization tests; Static analysis |
| 6 | `6820501` | #199 | 01.11 22:07 | 02.11 03:14 | 54.1 | 21.9 | ✅ | CI; Lab07 card ordering; Static analysis |
| 7 | `15044a9` | #200 | 01.11 22:57 | 02.11 03:34 | 54.1 | 38.9 | ✅ | CI; Lab07 card ordering; Static analysis |
| 8 | `e16c784` | #201 | 02.11 08:59 | 02.11 09:03 | 0.0 | 1.9 | ✅ | CI; Lab07 card ordering; Static analysis |
| 9 | `69056e0` | #202 | 02.11 09:31 | 02.11 09:48 | 0.0 | 1.9 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Static analysis |
| 10 | `072ddd9` | #216 | 07.11 09:38 | 07.11 11:24 | 0.0 | 1.0 | ✅ | CI; Lab07 card ordering; Lab08 characterization tests; Static analysis |
| 11 | `cedc6ec` | #217 | 07.11 16:44 | 07.11 16:55 | 0.0 | 1.1 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Static analysis |
| 12 | `62d9cb1` | #219 | 07.11 16:19 | 07.11 17:46 | 0.0 | 1.0 | ✅ | CI; Lab07 card ordering; Static analysis |
| 13 | `386f517` | #218 | 07.11 17:34 | 07.11 17:48 | 0.1 | 1.5 | ✅ | CI; Lab07 card ordering; Lab08 characterization tests; Static analysis |
| 14 | `4f6d9ba` | #220 | 08.11 18:18 | 08.11 18:50 | 0.0 | 1.1 | ✅ | CI; Lab07 card ordering; Static analysis |
| 15 | `cc55e0e` | #221 | 08.11 18:30 | 08.11 18:50 | 0.0 | 1.0 | ✅ | CI; Lab07 card ordering; Static analysis |
| 16 | `3bcb7b5` | #222 | 08.11 18:40 | 08.11 18:51 | 0.0 | 1.2 | ✅ | CI; Lab07 card ordering; Static analysis |
| 17 | `3f6bee8` | #223 | 08.11 21:24 | 08.11 21:39 | 0.0 | 1.0 | ✅ | CI; Lab07 card ordering; Static analysis |
| 18 | `a8e1c94` | #224 | 08.11 23:05 | 08.11 23:10 | 0.0 | 1.4 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Lab08 characterization tests; Static analysis |
| 19 | `7c83291` | #225 | 08.11 23:18 | 08.11 23:30 | 0.0 | 1.1 | ✅ | CI; Lab07 card ordering; Static analysis |
| 20 | `8c86e19` | #226 | 08.11 23:36 | 08.11 23:43 | 0.0 | 2.8 | ✅ | CI; Generate and Deploy API Docs; Lab07 card ordering; Static analysis |
| 21 | `dbca9b6` | #227 | 09.11 00:17 | 09.11 00:32 | 2.3 | 3.8 | ✅ | CI; Lab07 card ordering; Static analysis |
| 22 | `5c85e94` | #229 | 09.11 09:24 | 09.11 15:09 | 0.0 | 1.1 | ✅ | CI; Lab07 card ordering; Static analysis |
| 23 | `64475b5` | #230 | 09.11 10:08 | 09.11 15:11 | 0.8 | 1.9 | ✅ | CI; Lab07 card ordering; Static analysis |

Черга – час від створення commit-triggered run до старту першого job; виконання – від старту першого job до завершення останнього врахованого workflow. Значення округлено до 0,1 хв. Для lead time використано повні ISO-часи з API, а не округлені значення таблиці.
