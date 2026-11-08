<!--
## Використання ШІ
- **Інструмент:** Copilot.
- **Застосування:** підготовка reliability report, опис виправлень R1–R3 і
  R5–R8, режимів відмовлення, відновлення та доказів тестування.
- **Верифікація:** автор переглянув зміст звіту, статуси ризиків і фактичні
  результати backend та frontend тестів.
- **Доповнення за допомогою Codex:** уточнення класифікації R1–R9, аналіз
  і виправлення R10, тести та докази для бонусу health check.
- **Доповнення за допомогою Claude Code:** код «до/після» для R1–R3 з
  коміту `ff49c50`, розділ «Використані патерни надійності», статус R10
  і повторний прогін тестів 08.11.2026. Фрагменти звірено з поточним кодом,
  результати прогону скопійовано з фактичного виводу.
-->

# Reliability Report — Lab 09

## Обсяг і підхід

Під час reliability scavenger hunt знайдено десять ризиків у backend і
frontend. Для кожного ризику зафіксовано ланцюг `fault → error → failure`,
критичність і статус. R1–R3 були виправлені командним комітом `ff49c50`.
На попередньому етапі додано виправлення R5–R8 і frontend-тести для цих змін.

Під час повторного аналізу виявлено залишковий ризик R5: дедлайн не охоплює
читання тіла відповіді. R10 виправлено у `8553240` (PR #217). Усі
результати перевірок нижче отримано повторним прогоном 08.11.2026.
Оцінки критичності та умови активації для всіх десяти ризиків наведено у
[scavenger-hunt.md](scavenger-hunt.md#критерії-критичності-та-перевірка-аналітика).
Fault тут означає дефект у коді; зовнішній збій описаний окремо як умова.

## Зведення ризиків

| Ризик | Компонент | Критичність | Статус | Основний режим |
|---|---|---:|---|---|
| R1 | Підключення та доступ до БД | Висока | Виправлено у `ff49c50` | Швидка відмова |
| R2 | Надсилання запрошення через Mailtrap | Висока | Виправлено у `ff49c50` | Швидка відмова |
| R3 | Блокування входу після невдалих спроб | Висока | Виправлено у `ff49c50` | Безпечна відмова |
| R4 | Широкий `except Exception` у валідації URL | Середня | Відкрито | Чітка помилка валідації |
| R5 | Frontend `fetch` без тайм-ауту | Висока | Частково виправлено у `c5ed992`; читання тіла поза дедлайном | Швидка відмова |
| R6 | Некоректний JSON у відповіді API | Середня | Виправлено у `c5ed992` | Швидка відмова |
| R7 | Необмежена пагінація карток | Висока | Виправлено у `c5ed992` | Швидка відмова |
| R8 | Помилки links/notes/mentors як порожні дані | Середня | Виправлено у `c5ed992` | Безпечна деградація |
| R9 | Неповна перевірка JSON у MCP login | Середня | Відкрито | Чітка помилка інтеграції |
| R10 | Запис OpenAPI YAML зупиняє startup API | Висока | Виправлено у `8553240` | Безпечна деградація |

## Виправлені ризики R1–R3

### R1 — відмова БД

**До:** підключення не мало повного набору обмежень очікування, помилки
SQLAlchemy могли перетворюватися на сирий 500, а `/health` не перевіряв БД.

```python
# src/api/db.py
return sessionmaker(create_engine(database_url(), pool_pre_ping=True))

# src/api/main.py
def health() -> dict:
    return {"status": "ok"}
```

**Після:** додано `connect_timeout`, `statement_timeout` і `pool_timeout`,
обробник `SQLAlchemyError` із безпечною відповіддю `503`, а health endpoint
повертає `503` зі статусом `unhealthy`, якщо БД недоступна.

```python
# src/api/db.py: кожне очікування на БД обмежене
engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    pool_timeout=POOL_TIMEOUT_SECONDS,  # 5 с
    connect_args={
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,  # 3 с
        "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",  # 5000 мс
    },
)

# src/api/errors.py, handle_database_error: тимчасовий збій → 503, решта → 500
if isinstance(exc, (OperationalError, PoolTimeoutError)):
    logger.error("Database unavailable [%s]: %s", request_id, exc)
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
else:
    logger.exception("Database error [%s]", request_id)
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

# src/api/main.py
def health() -> JSONResponse:
    if not db.database_is_available():  # SELECT 1
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "checks": {"database": "unavailable"}},
        )
    return JSONResponse({"status": "ok", "checks": {"database": "ok"}})
```

- **Умова:** БД недоступна або операція надто довга.
- **Fault:** немає явних обмежень підключення/SQL-запиту, обробника
  `SQLAlchemyError` і перевірки БД у старому `/health`.
- **Error:** ресурси зайняті очікуванням; помилка драйвера не перетворена на
  узгоджену API-відповідь, а стан health не відображає залежність.
- **Failure:** без захисту користувач отримав би сирий 500 або моніторинг
  помилково бачив би сервіс як здоровий.
- **Рішення:** швидка відмова; система повертає контрольований `503`, а
  моніторинг бачить unhealthy. Після відновлення БД наступний health check
  повертає `200`.

**Тести:** `tests/reliability/test_database_failure.py` перевіряє ін'єкцію
відмови БД, формат помилки, health check і обмежені тайм-аути.

### R2 — відмова Mailtrap

**До:** відсутній токен і помилки провайдера могли породити сирий 500 або
розкрити URL, inbox ID і текст відповіді Mailtrap.

```python
# src/api/routers/mentors.py, _send_invitation_email
if not MAILTRAP_API_TOKEN:
    raise RuntimeError(
        "MAILTRAP_API_TOKEN не задано — email не може бути відправлено. "
        "Додайте змінну в .env і перезапустіть контейнер."
    )
...
except Exception as e:
    details = ""
    if hasattr(e, "response") and e.response is not None:
        details = f" Деталі API: {e.response.text}"
    raise ServiceUnavailableError(
        f"Не вдалося надіслати запрошення на {email}: {e}.{details}"
    ) from e
```

**Після:** додано `ServiceUnavailableError`, нейтральне повідомлення для
клієнта і вузький catch лише для `MailtrapError` та мережевих помилок.
Внутрішня помилка нашого коду не маскується як відмова провайдера.

```python
# src/api/routers/mentors.py, _send_invitation_email
if not MAILTRAP_API_TOKEN:
    logger.error(
        "MAILTRAP_API_TOKEN is not set, invitation email for board %s "
        "was not sent; add it to .env and restart the container",
        board_id,
    )
    raise ServiceUnavailableError(EMAIL_UNAVAILABLE_MESSAGE)
...
# Лише відмови провайдера й мережі; помилка нашого коду лишається 500.
except (mt.MailtrapError, requests.RequestException) as e:
    logger.warning(
        "Mailtrap failed to send invitation for board %s: %s", board_id, e
    )
    raise ServiceUnavailableError(EMAIL_UNAVAILABLE_MESSAGE) from e
```

- **Умова:** Mailtrap недоступний, повертає помилку або відсутній токен.
- **Fault:** широкий `except Exception`, вставка сирого тексту провайдера
  у відповідь і недоменний `RuntimeError` за відсутності токена.
- **Error:** внутрішні деталі включені в клієнтську помилку або виняток
  обходить узгоджений формат API.
- **Failure до виправлення:** запрошення не створюється; користувач отримує
  сирий 500 або технічні деталі Mailtrap. Контрольований 503 — поведінка після.
- **Рішення:** швидка відмова; транзакція не підтверджує запрошення без
  успішного email. Після відновлення Mailtrap власник може повторити операцію.

**Тести:** `tests/reliability/test_invitation_email_failure.py` інжектує
timeout, connection error і authorization error Mailtrap, а також перевіряє
відсутність токена та безпечне логування.

> Це виправлення не заявляється як ідемпотентність зовнішнього виклику:
> Mailtrap не підтримує idempotency key, тому бонус із retry для
> ідемпотентного зовнішнього виклику не реалізовувався.

### R3 — вічне блокування входу

**До:** лічильник невдалих спроб губився через rollback транзакції, а
«тимчасове» блокування не мало часу завершення.

```python
# src/api/auth.py
def _register_failed_attempt(user: User, repos: Repositories) -> None:
    user.failed_login_attempts += 1
    repos.users.save(user)  # у транзакції запиту, яку відповідь 401 відкочує

def login(payload: LoginRequest, repos: Repos) -> TokenResponse:
    user = repos.users.get_by_email(str(payload.email).lower())
    if user is not None and user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        raise ForbiddenError("Обліковий запис тимчасово заблоковано")  # без терміну
    ...
```

**Після:** додано атомарну реєстрацію невдалої спроби, `locked_until` і
15-хвилинне вікно блокування. Після його завершення доступ відновлюється
автоматично.

```python
# src/api/auth.py, login
if user.locked_until is not None:
    locked_until = user.locked_until.replace(
        tzinfo=user.locked_until.tzinfo or timezone.utc
    )
    if locked_until > now:
        raise _locked_error(locked_until)
    attempts.reset(user.id)  # блокування минуло: нове вікно спроб

# Один UPDATE ... RETURNING у власній транзакції (SqlLoginAttemptRepository),
# тому rollback запиту не скидає лічильник, а паралельні спроби не губляться.
attempt = attempts.register_attempt(
    user.id, lock_at=MAX_FAILED_ATTEMPTS, lock_until=now + LOCKOUT_DURATION
)
if attempt > MAX_FAILED_ATTEMPTS:
    raise _locked_error(None)
if not _verify_password(payload.password, user.password_hash):
    raise UnauthorizedError("Невірний email або пароль")
```

- **Умова:** повторні неправильні паролі або паралельні спроби входу.
- **Fault:** немає терміну завершення блокування; лічильник оновлюється
  неатомарно та відкочується разом із невдалим запитом.
- **Error:** лічильник і стан блокування не відповідають фактичним спробам.
- **Failure:** легітимний користувач назавжди втрачає доступ або захист від
  brute force не працює.
- **Рішення:** безпечна відмова з обмеженим часом; під час lockout повертається
  `403`, після завершення вікна правильний пароль знову приймається.

**Тести:** `tests/reliability/test_login_lockout.py` перевіряє rollback,
межу спроб, активне й прострочене блокування та відмову до перевірки пароля.

## Виправлені ризики R5–R8

### R5 — frontend timeout

**До:**

```typescript
res = await fetch(`${API_BASE}${path}`, {
  method,
  headers,
  body: body !== undefined ? JSON.stringify(body) : undefined,
});
```

Завислий API-запит міг залишити екран у стані завантаження без дедлайну.

**Після:** у спільному `client.ts` створюється `AbortController`, таймер
обмежений `API_REQUEST_TIMEOUT_MS = 10_000`, а `AbortError` перетворюється на
безпечне повідомлення. Таймер очищається в `finally`.

- **Умова:** зовнішній API або проксі перестає відповідати.
- **Fault:** клієнтський `fetch` не мав дедлайну й скасування запиту.
- **Error:** promise `fetch` залишається pending.
- **Failure:** UI зависає і користувач не отримує результату.
- **Рішення:** швидка відмова після 10 секунд. Користувач бачить повідомлення
  про перевищення часу. Повтор читання можливий після відновлення API;
  перед повтором запису треба з'ясувати, чи сервер уже виконав попередню дію.

**Залишок:** таймер очищається після `fetch`, до `res.text()`. Тому 10 секунд
обмежують очікування заголовків, але не всього тіла; потрібне окреме
доопрацювання дедлайну й тест зависання тіла. У цій зміні frontend не змінено.

**Тест:** frontend reliability test імітує abort та перевіряє безпечне
повідомлення про timeout.

### R6 — некоректний JSON

**До:**

```typescript
const text = await res.text();
const data = text ? JSON.parse(text) : undefined;
```

HTML від reverse proxy або пошкоджене тіло відповіді викликали необроблений
`SyntaxError`.

**Після:** `JSON.parse` обгорнуто в `try/catch`; для не-JSON відповіді
повертається контрольована помилка з HTTP-статусом.

- **Умова:** сервер повертає не JSON.
- **Fault:** `JSON.parse` викликається без обробки помилки розбору.
- **Error:** парсер породжує `SyntaxError`.
- **Failure:** користувач бачить технічне повідомлення парсера замість
  зрозумілої причини невдалого запиту.
- **Рішення:** швидка відмова з повідомленням `Запит не вдався: HTTP ...`;
  повтор можливий після відновлення сервера.

**Тест:** frontend reliability test передає HTML із `502` і перевіряє
контрольовану помилку.

### R7 — необмежена пагінація

**До:**

```typescript
while (true) {
  const page = await api.listCards(boardId, limit, offset);
  all.push(...page.items);
  if (all.length >= page.pagination.total || page.items.length === 0) break;
  offset += limit;
}
```

Повтор сторінки за скінченного сталого `total` призводив до дублікатів.
Зростаючий або некоректний `total` міг спричинити незавершуване завантаження;
незалежного обмеження кількості сторінок не було.

**Після:** додано максимум 1000 сторінок, `Set` отриманих ID карток, перевірку
прогресу, обробку передчасно порожньої сторінки та контрольовані помилки.

- **Умова:** API повертає повторну сторінку або неправильну метаінформацію.
- **Fault:** цикл без незалежного ліміту й перевірки прогресу рахує дублікати
  як нові картки.
- **Error:** накопичені дублікати або не досягається умова завершення.
- **Failure:** дошка показує дублікати чи надто довго / без кінця завантажується.
- **Рішення:** швидка відмова; завантаження припиняється з поясненням, а
  користувач може повторити після виправлення API.

**Тест:** frontend reliability test повертає одну й ту саму сторінку двічі та
перевіряє помилку відсутності прогресу і лише два виклики API.

### R8 — silent fallback для залежних даних

**До:**

```typescript
api.listLinks(boardId, card.id).catch(() => setLinks([]));
api.listNotes(boardId, card.id).catch(() => setNotes([]));
api.listMentors(boardId).catch(() => setMentors([]));
```

Помилка була невідмінною від справді порожнього списку.

**Після:** додано окремі `linksError`, `notesError` і `mentorsError`,
логування без секретів, повідомлення в UI та кнопку «Повторити». Порожній
стан показується лише після успішної відповіді. Cleanup `useEffect` не дає
старому запиту перезаписати стан після зміни картки.

- **Умова:** залежний API-виклик завершується помилкою.
- **Fault:** catch підміняє відмову порожнім масивом без окремого стану помилки.
- **Error:** дані недоступні, але старий код перетворював це на `[]`.
- **Failure:** користувач приймає неповні дані за правильний стан.
- **Рішення:** безпечна деградація; основна картка доступна, проблемний блок
  явно позначений, а відновлення виконується через retry.

**Тест:** frontend reliability test інжектує відмову links, notes і mentors,
перевіряє три alert-повідомлення, три кнопки retry і відсутність хибних
повідомлень про порожні списки.

## R10 — файловий збій під час запуску API

**Код:** [src/api/main.py](../../src/api/main.py), `lifespan` та
`save_openapi_spec`. **Категорії:** A, B. **Критичність:** висока — через
допоміжний експорт недоступний весь API після запуску.

**До:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    save_openapi_spec(app)
    yield
```

- **Умова:** `EACCES`, `EROFS`, `ENOSPC` або файл замість каталогу експорту.
- **Fault:** необов'язковий файловий експорт без обробки `OSError` стоїть
  перед завершенням startup.
- **Error:** файловий виняток перериває `lifespan` до `yield`.
- **Failure:** сервіс не запускається; користувачі не можуть виконати жодну
  API-операцію, а моніторинг не отримує відповіді `/health`.

**Після:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        save_openapi_spec(app)
    except OSError:
        logger.warning(
            "OpenAPI YAML export failed; API startup continues with in-memory schema",
            exc_info=True,
        )
    yield
```

**Чому безпечна деградація:** YAML — допоміжна копія документації, він не
потрібний для обробки запитів. Користувач отримує звичайні API-відповіді,
`/openapi.json` і `/api-docs` доступні зі схемою в пам'яті. Оператор бачить
warning із причиною. Файл може бути відсутнім, старим або неповним після
помилки запису; під час такого збою джерелом схеми є `/openapi.json`.

**Відновлення:** відновити права/місце/шлях і повторити експорт командою
`python -m src.api.main` або перезапустити застосунок. Автоматичних повторів
запису немає. Явний експорт для CI завершується помилкою при `OSError`,
а програмні помилки генерації схеми не приховуються під час startup.

**Тести:** [test_startup_file_failure.py](../../tests/reliability/test_startup_file_failure.py).
Три ін'єкції файлових помилок перевіряють доступність health, схеми,
Swagger UI та маршруту входу, warning і відновлення експорту на наступному
старті. Граничний випадок — файл замість каталогу. Дві захисні перевірки
підтверджують, що помилка схеми та помилка явного експорту залишаються видимими.

## Використані патерни надійності

| Патерн | Де застосовано | Що дає |
|---|---|---|
| Guard clause | R2: відсутній `MAILTRAP_API_TOKEN` → `ServiceUnavailableError` до звернення до Mailtrap. R3: перевірка `locked_until` і номера спроби до перевірки пароля | Некоректний стан зупиняється до дорогої або небезпечної операції |
| Вузький catch | R1: окремий обробник `SQLAlchemyError` — `OperationalError` і pool timeout дають `503`, інші помилки БД — `500`. R2: лише `MailtrapError` і `requests.RequestException`. R6: лише помилка `JSON.parse`. R10: лише `OSError` під час експорту YAML | Перехоплюється тільки очікуваний збій; дефект власного коду не маскується під відмову залежності |
| Тайм-аут | R1: `connect_timeout` 3 с, `statement_timeout` 5 с, `pool_timeout` 5 с. R5: `AbortController` з `API_REQUEST_TIMEOUT_MS = 10_000` | Очікування на БД і API обмежене в часі; воркер, слот пулу чи екран не зависають |
| Обмеження циклу й спроб | R7: `MAX_CARD_PAGES = 1000`. R3: не більше 5 перевірок пароля за вікно блокування | Некоректна відповідь чи brute force не спричиняють необмеженого споживання ресурсів |
| Перевірка вхідних даних і відповідей | R6: не-JSON тіло дає контрольовану помилку з HTTP-статусом. R7: `Set` отриманих ID, помилка на сторінці без нових карток і на порожній сторінці до досягнення `total` | Пошкоджена або суперечлива відповідь не перетворюється на хибні дані в UI |
| Fallback / безпечна деградація | R8: окремий стан помилки й кнопка «Повторити» замість `[]`. R10: API стартує без YAML-файлу, схема віддається з пам'яті | Основна функція працює, а збій допоміжної частини видно користувачу чи в лозі |
| Безпечне значення | R1: `database_is_available()` повертає `False` при `SQLAlchemyError` або без `DATABASE_URL`, тож `/health` — `unhealthy`. R3: блокування має термін `locked_until` (15 хв) замість безстрокового | За сумнівного стану система обирає варіант, що не вводить в оману і не блокує назавжди |
| Логування без витоку деталей | R1, R2: текст драйвера чи провайдера — лише в лозі (`logger.error`/`logger.warning`), клієнт отримує нейтральне повідомлення і `request_id` (CWE-209). R8: `console.error` для кожної відмови. R10: `logger.warning(..., exc_info=True)` | Збій можна діагностувати, а клієнт не бачить хостів, SQL чи відповідей Mailtrap |
| Атомарна операція | R3: `register_attempt` — один `UPDATE ... RETURNING` у власній транзакції | Rollback запиту не скидає лічильник, паралельні спроби отримують різні номери |
| Health check | R1: `/health` виконує `SELECT 1` і повертає `503 unhealthy`, якщо БД недоступна | Моніторинг бачить реальний стан залежності, а не лише живий процес |

Retry з backoff не застосовувався: єдиний зовнішній виклик із побічним
ефектом (Mailtrap) не ідемпотентний, тому автоматичний повтор міг би надіслати
кілька листів (див. примітку в R2).

## Відкриті ризики

### R4 — широкий catch у валідації URL

Наразі відкрито. Широке перехоплення може маскувати програмні дефекти під
помилку невалідного URL. Наступне виправлення має звузити catch до очікуваних
винятків і зберегти безпечне відхилення зовнішнього вводу.

- **Fault → error → failure:** широкий catch → внутрішній дефект стає
  `False` → користувач не може зберегти коректний URL.
- **Очікувана реакція:** відхиляти некоректний ввід, діагностувати програмний
  дефект; повтор коректного запиту після виправлення валідатора.

### R9 — неповна перевірка JSON у MCP login

Наразі відкрито. HTTP-статус уже перевіряється; бракує перевірки JSON і
структури токена після HTTP 200.

- **Fault → error → failure:** пряме `response.json()["access_token"]` без
  валідації → токен не отриманий, виникає виняток → MCP-операція не виконується.
- **Очікувана реакція:** чітка помилка інтеграції; повтор входу після
  відновлення коректної відповіді API.

### R5 — читання тіла відповіді поза тайм-аутом

Залишається відкритим після виправлення очікування заголовків. Потрібно
поширити дедлайн на `res.text()` і перевірити тестом: заголовки вже отримані,
тіло не завершується → запит скасовано → UI виходить зі стану очікування.

## Докази перевірки

Повторний прогін 08.11.2026 на `main` (`386f517`, після злиття R10):

```text
$ .venv/bin/python -m pytest tests/reliability --no-cov -q
25 passed in 2.02s

$ .venv/bin/python -m pytest tests/reliability tests/test_main.py --no-cov -q
29 passed in 2.64s

$ cd src/frontend
$ npm run test:unit -- --run
 Test Files  2 passed (2)
      Tests  16 passed (16)

$ npm run build
✓ built in 889ms
```

Frontend-тести розміщені в `src/frontend/tests/reliability.test.tsx`, оскільки
вони використовують Vitest, jsdom і React Testing Library. Backend-тести
залишаються в `tests/reliability/` і перевіряють R1–R3 та R10.

До виправлення R10 чотири тести відтворювали збій запуску API. Після
виправлення всі **29 тестів** із `tests/reliability` та `tests/test_main.py`
пройшли, включно з 6 сценаріями R10 і перевіркою відновлення health check.
Файлові збої перевірено ін'єкцією помилок, БД — через SQLite у пам'яті.

## Висновок

Обрані ризики R5 і R7 отримали fail-fast захист, R8 — graceful degradation,
а R6 — контрольовану обробку пошкодженої відповіді. Командний мінімум
reliability-тестів виконано: backend suite покриває R1–R3, frontend suite
покриває R5–R8 у зазначених межах. R10 захищає запуск API від файлового збою.
Відкритими лишаються R4, R9 та залишок R5 щодо тіла відповіді.

## Бонуси

### Перевірка здоров'я сервісу

**Технічна частина реалізована й перевірена.** Health check уже був частиною
командного виправлення R1; поточний внесок — перевірка коду, додатковий тест
відновлення та зібрані докази.

| Доказ | Реалізація / перевірка |
|---|---|
| Перевірка критичної залежності | [db.py](../../src/api/db.py), `database_is_available`: відкриває сесію та виконує `SELECT 1` |
| Зрозумілий статус | [main.py](../../src/api/main.py), `health`: `200 {"status":"ok","checks":{"database":"ok"}}` або `503 {"status":"unhealthy","checks":{"database":"unavailable"}}` |
| Ін'єкція відмови | [test_database_failure.py](../../tests/reliability/test_database_failure.py), `test_health_reports_unhealthy_when_database_is_down`: дублер сесії кидає `OperationalError` |
| Відновлення | `test_health_recovers_after_database_outage`: одним клієнтом перевіряє `200 → 503 → 200`, без рестарту API, без витоку деталей драйвера |
| Відсутня конфігурація | `test_health_reports_unhealthy_without_database_url`: залежність позначається недоступною |
| Обмеження очікування | `test_every_wait_on_database_is_bounded`: перевіряє налаштовані connect/query/pool timeout; це не вимірювання реального часу збою |
| Результат | Зазначений вище локальний прогін: усі 29 тестів пройшли |

Для окремої демонстрації: `python -m pytest tests/reliability/test_database_failure.py -k health --no-cov -v`.
У цьому Windows-середовищі за потреби додати `--basetemp` із новим тимчасовим
підкаталогом `.pytest_cache`, оскільки системний pytest Temp недоступний.

**Обсяг перевірки:** БД є спільною критичною залежністю основних API-операцій.
Mailtrap використовується для запрошень і не перевіряється `/health`; `ok`
означає готовність API та доступність БД, а не гарантію доставки листів чи
наявності всіх таблиць. Health check не надсилає тестових листів.
