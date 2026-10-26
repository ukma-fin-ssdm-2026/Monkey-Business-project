# План тестування — Monkey Business

**Обсяг:** тестуємо права ментора та відкликання доступу, створення й упорядкування карток, посилання і коментарі; після взаємного огляду додано редагування картки (FR-008) та запрошення ментора (FR-012); окремо — SEC-3 та сценарій PERF-4. Поза обсягом: AI-асистент, нагадування, аналітика, підтримка, повний набір адміністративних функцій, доставка справжніх email та інші NFR.

**Критерії виходу:** план містить сценарії з критеріями прийняття, власниками та зв’язками з RTM; зауваження взаємного огляду враховано в плані й review-log.md; реалізовані тести погодженого обсягу проходять у CI, немає відкритих критичних дефектів цього обсягу; сукупне покриття рядків і гілок API ≥80% — ціль стратегії після додавання інтеграційних тестів, критичних модулів зі стратегії ≥95%; базовий CI-поріг — 70%.

**Ризики:** найвищий пріоритет — несанкціонована зміна даних ментором або доступ після відкликання; далі — втрата порядку карток через однакові індекси й незбереження змін у PostgreSQL; потім — невалідні дані та повільне оновлення інтерфейсу.

| № | Компонент/функція | Рівень тесту | Тип (позитивний/негативний) | Очікуваний результат / критерій прийняття | Власник | Вимога (ID з rtm.md) |
|---|---|---|---|---|---|---|
| TP-01 | Доступ ментора: `auth.require_board_access` | Модульний | Негативний | Для ментора з прийнятим запрошенням виклик із `write=True` породжує `ForbiddenError`; методи запису репозиторіїв не викликаються. HTTP-код на цьому рівні не перевіряється. | Mykola Vashchenko | FR-014, US-002 |
| TP-02 | Доступ ментора: `mentors.revoke_mentor` | Інтеграційний | Негативний | Передумова: ментор читає картки дошки з 200. Власник викликає `DELETE /v1/boards/{board_id}/mentors/{mentor_id}` → 204; наступний `GET /v1/boards/{board_id}/cards` із тим самим JWT ментора → 403. У новій сесії БД статус запрошення — `revoked`. | Mykola Vashchenko | FR-015, US-002 |
| TP-03 | Порядок карток: `cards.move_card` | Модульний | Позитивний | У сховищі-дублі є картки A, B, C одного етапу з індексами 0, 1, 2. Перемістити C на позицію 0. Після операції порядок — C, A, B, індекси — 0, 1, 2; жодна картка не втрачена й не має спільної позиції з іншою. | Nikita Dyshlyuk | FR-005, US-005 |
| TP-04 | Порядок карток: `POST .../cards/{card_id}/move` | Інтеграційний | Позитивний | На етапі S1 є A(0), B(1), на S2 — C(0). Власник переносить B у S2 на позицію 0 → 200. Нові HTTP-запити повертають для S1 порядок A, для S2 — B, C; у новій сесії PostgreSQL для S2 збережено індекси 0, 1. | Nikita Dyshlyuk | FR-004, FR-005, US-005 |
| TP-05 | Створення картки: `schemas.CardCreate` | Модульний | Негативний | При `company="   "`, валідній `position` і чинному UUID етапу конструктор схеми породжує `ValidationError` для `company`; об'єкт картки не створюється. Еквівалентне розбиття: рядок лише з пробілів. | Nazar Sydorchuk | FR-007, US-007 |
| TP-06 | Створення картки: `cards.create_card` | Інтеграційний | Позитивний | Власник надсилає `POST /v1/boards/{board_id}/cards` із `company="Acme"`, `position="Python Developer"` та етапом цієї дошки → 201 і UUID картки. Повторний GET → 200 з тими самими полями; нова сесія БД бачить рівно одну нову картку на цій дошці. | Nazar Sydorchuk | FR-007, US-007 |
| TP-07 | Посилання: `schemas.CardLinkCreate` | Модульний | Негативний | Для `url="not-a-url"` конструктор схеми породжує `ValidationError` для `url`; невалідне посилання не потрапляє до функції збереження. Перевіряється схема HTTP-ресурсу, а не окремий `validate_vacancy_url`. | Oleksii Volik | FR-009, US-003 |
| TP-08 | Посилання: `card_links.create_link` | Інтеграційний | Позитивний | Власник додає `https://example.com/task` до наявної картки через `POST /v1/boards/{board_id}/cards/{card_id}/links` → 201. Наступний GET списку → 200 і нове посилання. | Oleksii Volik | FR-009, US-003 |
| TP-09 | Коментарі: `schemas.CommentCreate` | Модульний | Негативний | Для `content="   "` конструктор схеми породжує `ValidationError`; порожній після очищення коментар не може бути збережений. | Nazar Sydorchuk | FR-013, US-008 |
| TP-10 | Коментарі: `comments.create_comment` | Інтеграційний | Позитивний | Ментор із прийнятим запрошенням надсилає непорожній коментар через `POST /v1/boards/{board_id}/cards/{card_id}/comments` → 201. GET → 200 з цим текстом, `author_id` ментора й часом створення; запис існує в новій сесії БД. Картка кандидата не змінюється. | Nazar Sydorchuk | FR-013, FR-014, US-008 |
| TP-11 | Безпека: заборона зміни карток ментором | Інтеграційний, нефункціональний | Негативний | Параметризований кейс: ментор із доступом на читання надсилає валідні PATCH картки, DELETE картки та POST її переміщення. Усі 3 із 3 запитів → 403; у БД не змінено поля, етап, позицію, кількість карток. До кожного варіанта відновлюється однакова фікстура. Частка успішно заборонених дій — 100%, кількість змін — 0. | Mykola Vashchenko | SEC-3, FR-014, US-002 |
| TP-12 | Продуктивність: збереження й відображення даних картки | Системний, нефункціональний | Позитивний | Кандидат додає коректне посилання в UI. Від натискання «Додати» до успішної відповіді API та видимого посилання минає ≤300 мс, без перезавантаження сторінки; повторний GET підтверджує збереження. Виконати 30 вимірюваних додавань з унікальними URL; кожне має вкластися в поріг. | Oleksii Volik | PERF-4, FR-009, US-003 |
| TP-13 | Редагування картки власником: `cards.update_card` | Модульний | Позитивний | Власник змінює `position` на `Senior Backend Engineer`; повернена картка та запис репозиторію містять нове значення. ID, дошка, етап, компанія та позиція в етапі залишаються попередніми. | Nikita Dyshlyuk | FR-008, US-007 |
| TP-14 | Запрошення ментора: `mentors.invite_mentor` | Модульний | Позитивний | Власник запрошує нову email-адресу: створено обліковий запис ролі `mentor`, запрошення зі статусом `pending` і непорожнім токеном; поштовий дублер отримав саме цю адресу та токен. Справжня доставка email поза обсягом. | Mykola Vashchenko | FR-012, US-002 |

## Виконання та докази

| Тест | Реалізація / команда | Стан |
|---|---|---|
| TP-01 | `tests/test_mentor_access_unit.py::test_tp01_invited_mentor_write_access_is_forbidden_and_nothing_is_written`; `python -m pytest tests/test_mentor_access_unit.py --no-cov -v` | Пройдено локально: `ForbiddenError`, жоден репозиторій запису не викликано; контроль — той самий ментор читає. |
| TP-02 | `tests/integration/test_mentor_access_integration.py::test_revoked_mentor_loses_access_and_status_is_persisted`; команда нижче | Пройдено локально на PostgreSQL 16: DELETE → 204, GET від ментора → 403, статус `revoked` у новій сесії БД. |
| TP-03 | `tests/test_card_order.py::test_tp03_reorder_preserves_all_cards[TP-03]`; `python -m pytest tests/test_card_order.py --no-cov -v` | Локально пройдено; додаткові регресії перевіряють рух в обох напрямках, незмінну позицію, вихід за довжину списку, перенесення між етапами та відмову в доступі. |
| TP-04 | `tests/test_card_order_postgres.py::test_tp04_move_between_stages_commits_order`; команда нижче | Пройдено локально та в CI на PostgreSQL 16: POST → 200, GET обох етапів, перевірка в новій сесії БД. |
| TP-13 | `tests/test_card_order.py::test_tp13_owner_updates_card_without_changing_order` | Пройдено; результати в [журналі](review-log.md). |
| TP-14 | `tests/test_mentor_access_unit.py::test_tp14_owner_invites_new_email_creates_mentor_and_pending_invitation`; `tests/test_mentors.py::test_invite_mentor_creates_account_and_pending_invitation` | Пройдено локально: роль `mentor`, запрошення `pending` з непорожнім токеном, лист на цю адресу з цим токеном. |
| TP-05 | `tests/test_schemas.py::test_card_create_rejects_whitespace_only_company`; `python -m pytest tests/test_schemas.py --no-cov -v` | Пройдено; параметризовано трьома представниками класу «лише пробільні символи». |
| TP-06 | `tests/integration/test_cards_integration.py::test_owner_creates_card_that_persists`; команда нижче | Пройдено локально на PostgreSQL 16 і 17: POST → 201, GET повертає ті самі поля, нова сесія БД бачить рівно одну картку. У CI — `lab07-card-order.yml`. |
| TP-09 | `tests/test_comments.py::test_create_comment_rejects_blank_content_at_schema_level` | Пройдено; `ValidationError` лише для `content`. |
| TP-10 | `tests/integration/test_comments_integration.py::test_mentor_comment_persists_and_leaves_card_unchanged`; команда нижче | Пройдено локально на PostgreSQL 16 і 17: ментор із прийнятим запрошенням → 201, GET власника, запис у новій сесії БД, рядок картки не змінено. У CI — `lab07-card-order.yml`. |
| TP-11 | `tests/integration/test_mentor_access_integration.py::test_mentor_with_read_access_cannot_change_card[patch]`, `[delete]`, `[move]`; команда нижче | Пройдено локально на PostgreSQL 16: 3 із 3 запитів → 403, картка і кількість карток не змінені. |

Локальний запуск у PowerShell після встановлення залежностей:

```powershell
docker run --detach --name monkey-lab07-postgres --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=monkey_lab07 --publish 127.0.0.1:55432:5432 postgres:16
$env:TEST_DATABASE_URL = 'postgresql+psycopg://postgres@127.0.0.1:55432/monkey_lab07'
python -m pytest tests/test_card_order.py tests/test_card_order_postgres.py tests/integration --no-cov -v
python -m pytest
docker stop monkey-lab07-postgres
```

Перед запуском тестів PostgreSQL має бути готовий приймати з’єднання. Якщо контейнер уже створено, використайте `docker start monkey-lab07-postgres`. TP-04 працює в окремій схемі `lab07_<uuid>`; CI запускає його зі службою PostgreSQL.

**Використання ШІ:** Codex — тести TP-03/TP-04 і TP-13, виправлення порядку карток, CI та документація. Перевірка: pytest, PostgreSQL 16, black, flake8, bandit і detect-secrets; результати наведено в [журналі](review-log.md).
