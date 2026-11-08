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
- **Виправлення R4, R9 і залишку R5 (Claude Code):** код, тести та розділ
  «Виправлені ризики R4, R9 і залишок R5». Новий тест R5 перевірено на старому
  `client.ts` — він зависав до тайм-ауту; на новому проходить.
- **Бонус «обов'язкова перевірка PR» (Claude Code):** job `reliability-tests`
  у `ci.yml` і розділ із доказами; команди job прогнано локально.
-->

# Reliability Report — Lab 09

## Обсяг і підхід

Під час reliability scavenger hunt знайдено десять ризиків у backend і
frontend. Для кожного ризику зафіксовано ланцюг `fault → error → failure`,
критичність і статус. R1–R3 були виправлені командним комітом `ff49c50`.
На попередньому етапі додано виправлення R5–R8 і frontend-тести для цих змін.

Під час повторного аналізу виявлено залишковий ризик R5: дедлайн не охоплював
читання тіла відповіді. R10 виправлено у `8553240` (PR #217). На останньому
етапі (гілка `fix/reliability-r4-r5-r9`) закрито R4, R9 і залишок R5, тож
відкритих ризиків серед R1–R10 немає. Усі результати перевірок нижче
отримано прогоном 08.11.2026.
Оцінки критичності та умови активації для всіх десяти ризиків наведено у
[scavenger-hunt.md](scavenger-hunt.md#критерії-критичності-та-перевірка-аналітика).
Fault тут означає дефект у коді; зовнішній збій описаний окремо як умова.

## Зведення ризиків

| Ризик | Компонент | Критичність | Статус | Основний режим |
|---|---|---:|---|---|
| R1 | Підключення та доступ до БД | Висока | Виправлено у `ff49c50` | Швидка відмова |
| R2 | Надсилання запрошення через Mailtrap | Висока | Виправлено у `ff49c50` | Швидка відмова |
| R3 | Блокування входу після невдалих спроб | Висока | Виправлено у `ff49c50` | Безпечна відмова |
| R4 | Широкий `except Exception` у валідації URL | Середня | Виправлено (`fix/reliability-r4-r5-r9`) | Безпечне відхилення вводу; дефект — швидка відмова |
| R5 | Frontend `fetch` без тайм-ауту | Висока | Виправлено: заголовки у `c5ed992`, тіло у `fix/reliability-r4-r5-r9` | Швидка відмова |
| R6 | Некоректний JSON у відповіді API | Середня | Виправлено у `c5ed992` | Швидка відмова |
| R7 | Необмежена пагінація карток | Висока | Виправлено у `c5ed992` | Швидка відмова |
| R8 | Помилки links/notes/mentors як порожні дані | Середня | Виправлено у `c5ed992` | Безпечна деградація |
| R9 | Неповна перевірка JSON у MCP login | Середня | Виправлено (`fix/reliability-r4-r5-r9`) | Швидка відмова |
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

**Залишок (закрито пізніше):** у `c5ed992` таймер очищався після `fetch`,
до `res.text()`, тому 10 секунд обмежували лише очікування заголовків.
Виправлення описано в розділі «Виправлені ризики R4, R9 і залишок R5».

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

## Виправлені ризики R4, R9 і залишок R5

### R4 — широкий catch у валідації URL

**До:**

```python
# src/api/validators.py, validate_vacancy_url
try:
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False
    return _is_safe_host(parsed.hostname)
except Exception:
    return False
```

**Після:** у `try` лишився тільки розбір URL, перехоплюється лише
`ValueError` (саме його `urlparse` кидає для `http://[::1`), і відхилення
логується. Перевірка схеми та хоста винесена за межі `try`.

```python
try:
    parsed = urlparse(cleaned)
    hostname = parsed.hostname
except ValueError as exc:
    logger.info("Rejected unparsable vacancy URL: %s", exc)
    return False
if parsed.scheme.lower() not in ALLOWED_SCHEMES:
    return False
return _is_safe_host(hostname)
```

- **Fault:** `except Exception` охоплював і розбір вводу, і власну логіку
  валідатора.
- **Error:** програмний дефект (наприклад, `AttributeError` у перевірці
  хоста) перетворювався на `False`.
- **Failure:** користувач не може зберегти коректне посилання й отримує
  «невалідний URL», а команда не має жодного сліду дефекту.
- **Рішення:** два режими. Для зовнішнього вводу — безпечна відмова:
  некоректний URL відхиляється звичайною помилкою валідації. Для дефекту
  коду — швидка відмова: виняток доходить до глобального обробника (500 з
  `request_id` і traceback у лозі), тому його видно й можна виправити.
- **Відновлення:** користувач виправляє URL; дефект валідатора виправляє
  команда за логом, після чого коректний запит проходить.

**Тести:** [test_url_validator.py](../../tests/reliability/test_url_validator.py) —
граничні непарсовані URL (`http://[::1`, `https://[` тощо) відхиляються й
логуються; ін'єкція збою підміняє `_is_safe_host` на функцію з
`AttributeError` і перевіряє, що виняток не маскується (на старому коді
цей тест падає, бо повертається `False`).

### R9 — неповна перевірка відповіді MCP login

**До:**

```python
# src/api/mcp_server.py, LoginAuth._login
if response.status_code != 200:
    raise RuntimeError(...)
return response.json()["access_token"]
```

**Після:** перевірка винесена в `_extract_access_token`: тіло має бути
JSON-об'єктом, а `access_token` — непорожнім рядком. Інакше — `RuntimeError`
з однаковим зрозумілим повідомленням і запис у лог без тіла відповіді
(воно може містити токен).

```python
try:
    payload = response.json()
except ValueError as exc:  # JSONDecodeError — підклас ValueError
    logger.error("MCP login returned HTTP 200 with a non-JSON body ...")
    raise RuntimeError(LOGIN_RESPONSE_INVALID_MESSAGE) from exc
token = payload.get("access_token") if isinstance(payload, dict) else None
if not isinstance(token, str) or not token.strip():
    logger.error("MCP login returned HTTP 200 without ... access_token")
    raise RuntimeError(LOGIN_RESPONSE_INVALID_MESSAGE)
return token
```

- **Fault:** перевірявся лише HTTP-статус, структура тіла — ні.
- **Error:** `JSONDecodeError`/`KeyError`/`TypeError` або порожній токен,
  який далі пішов би в заголовок `Bearer `.
- **Failure:** MCP-інструмент падає з неструктурованим винятком або
  нескінченно отримує 401 з порожнім токеном.
- **Рішення:** швидка відмова. Без валідного токена жоден запит агента не
  може бути виконаний правильно, тому краще одразу зупинитися з чіткою
  помилкою інтеграції, ніж відправляти запити з недійсною автентифікацією.
- **Відновлення:** після виправлення API наступний виклик інструмента знову
  проходить `_login`; токен не кешується, доки не отримано валідний.

**Тести:** [test_mcp_login_response.py](../../tests/reliability/test_mcp_login_response.py) —
ін'єкція п'яти пошкоджених відповідей HTTP 200 (HTML, без токена, порожній
токен, число замість рядка, масив замість об'єкта). Перевіряється
повідомлення, наявність запису в лозі та відсутність тіла відповіді і в
помилці, і в лозі. Окремий тест підтверджує, що валідна відповідь повертає
токен.

### R5 — дедлайн на читання тіла відповіді

**До (`c5ed992`):** таймер очищався у `finally` одразу після `fetch`, тож
`await res.text()` виконувався вже без дедлайну.

**Після:** один `AbortController` і один таймер охоплюють і `fetch`, і
читання тіла; `clearTimeout` виконується лише після `res.text()`. Читання
тіла обгорнуто в `readBody`, яке змагається із `signal`, тому дедлайн
спрацьовує навіть там, де реалізація `fetch` не пов'язує потік тіла з
`signal`.

```typescript
try {
  res = await fetch(url, { ..., signal: controller.signal });  // AbortError → TIMEOUT_MESSAGE
  if (res.status === 204) return undefined as T;
  text = await readBody(res, controller.signal);                // AbortError → TIMEOUT_MESSAGE
} finally {
  window.clearTimeout(timeoutId);
}
```

- **Fault:** дедлайн не поширювався на читання тіла.
- **Error:** `res.text()` залишається pending, якщо сервер надіслав
  заголовки, але не завершив тіло.
- **Failure:** екран нескінченно показує завантаження.
- **Рішення:** швидка відмова через 10 с від початку запиту з тим самим
  повідомленням «API не відповів вчасно», що й для заголовків.
- **Відновлення:** повтор читання після відновлення API; для запису —
  спершу перевірити, чи сервер уже виконав дію.

**Тести:** у `src/frontend/tests/reliability.test.tsx` додано тест, де
`fetch` повертає 200 із `ReadableStream`, що ніколи не завершується; після
10 с очікується повідомлення про тайм-аут. На старому `client.ts` цей тест
зависає до тайм-ауту Vitest. Другий тест перевіряє, що тіло, яке прийшло
вчасно, повертається без змін.

## Використані патерни надійності

| Патерн | Де застосовано | Що дає |
|---|---|---|
| Guard clause | R2: відсутній `MAILTRAP_API_TOKEN` → `ServiceUnavailableError` до звернення до Mailtrap. R3: перевірка `locked_until` і номера спроби до перевірки пароля | Некоректний стан зупиняється до дорогої або небезпечної операції |
| Вузький catch | R1: окремий обробник `SQLAlchemyError` — `OperationalError` і pool timeout дають `503`, інші помилки БД — `500`. R2: лише `MailtrapError` і `requests.RequestException`. R6: лише помилка `JSON.parse`. R10: лише `OSError` під час експорту YAML. R4: лише `ValueError` від `urlparse`. R9: лише `ValueError` від `response.json()` | Перехоплюється тільки очікуваний збій; дефект власного коду не маскується під відмову залежності |
| Тайм-аут | R1: `connect_timeout` 3 с, `statement_timeout` 5 с, `pool_timeout` 5 с. R5: `AbortController` з `API_REQUEST_TIMEOUT_MS = 10_000` на весь обмін — заголовки й тіло | Очікування на БД і API обмежене в часі; воркер, слот пулу чи екран не зависають |
| Обмеження циклу й спроб | R7: `MAX_CARD_PAGES = 1000`. R3: не більше 5 перевірок пароля за вікно блокування | Некоректна відповідь чи brute force не спричиняють необмеженого споживання ресурсів |
| Перевірка вхідних даних і відповідей | R6: не-JSON тіло дає контрольовану помилку з HTTP-статусом. R7: `Set` отриманих ID, помилка на сторінці без нових карток і на порожній сторінці до досягнення `total`. R9: відповідь логіну має бути JSON-об'єктом із непорожнім рядком `access_token` | Пошкоджена або суперечлива відповідь не перетворюється на хибні дані в UI |
| Fallback / безпечна деградація | R8: окремий стан помилки й кнопка «Повторити» замість `[]`. R10: API стартує без YAML-файлу, схема віддається з пам'яті | Основна функція працює, а збій допоміжної частини видно користувачу чи в лозі |
| Безпечне значення | R1: `database_is_available()` повертає `False` при `SQLAlchemyError` або без `DATABASE_URL`, тож `/health` — `unhealthy`. R3: блокування має термін `locked_until` (15 хв) замість безстрокового | За сумнівного стану система обирає варіант, що не вводить в оману і не блокує назавжди |
| Логування без витоку деталей | R1, R2: текст драйвера чи провайдера — лише в лозі (`logger.error`/`logger.warning`), клієнт отримує нейтральне повідомлення і `request_id` (CWE-209). R8: `console.error` для кожної відмови. R10: `logger.warning(..., exc_info=True)`. R4: `logger.info` для відхиленого URL. R9: `logger.error` без тіла відповіді (може містити токен) | Збій можна діагностувати, а клієнт не бачить хостів, SQL чи відповідей Mailtrap |
| Атомарна операція | R3: `register_attempt` — один `UPDATE ... RETURNING` у власній транзакції | Rollback запиту не скидає лічильник, паралельні спроби отримують різні номери |
| Health check | R1: `/health` виконує `SELECT 1` і повертає `503 unhealthy`, якщо БД недоступна | Моніторинг бачить реальний стан залежності, а не лише живий процес |

Retry з backoff не застосовувався: єдиний зовнішній виклик із побічним
ефектом (Mailtrap) не ідемпотентний, тому автоматичний повтор міг би надіслати
кілька листів (див. примітку в R2).

## Відкриті ризики

Серед знайдених R1–R10 відкритих ризиків немає: R4, R9 і залишок R5
виправлено на останньому етапі (див. розділ вище). Свідомо не реалізовано:

- **Retry для Mailtrap (R2).** Виклик не ідемпотентний, автоматичний повтор
  міг би надіслати кілька листів; відновлення — ручний повтор власником.
- **Автоматичний повтор у frontend (R5).** Після тайм-ауту користувач сам
  вирішує, чи повторити; для запису спершу треба перевірити, чи дія вже
  виконана сервером.
- **Перевірка Mailtrap у `/health`.** Health check перевіряє лише БД, щоб не
  надсилати тестових листів (див. «Бонуси»).

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

Прогін 08.11.2026 після виправлення R4, R9 і залишку R5 (гілка
`fix/reliability-r4-r5-r9`):

```text
$ python -m pytest tests/reliability --no-cov -q
37 passed in 10.00s

$ python -m pytest tests/reliability tests/test_main.py --no-cov -q
41 passed in 11.89s

$ cd src/frontend
$ npm run test:unit -- --run
 Test Files  2 passed (2)
      Tests  18 passed (18)

$ npm run build
✓ built in 2.56s
```

Новий тест зависання тіла (R5) окремо запущено проти старого `client.ts`:
він не завершився за 3 с і впав за тайм-аутом Vitest, тобто відтворює
дефект. Тест R4 з ін'єкцією `AttributeError` на старому коді також падає,
бо `except Exception` повертав `False`.

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
reliability-тестів виконано: backend suite покриває R1–R4, R9 і R10,
frontend suite покриває R5–R8. R10 захищає запуск API від файлового збою.
R4 перестав маскувати дефекти валідатора, R9 дає чітку помилку інтеграції
замість сирого винятку, а дедлайн R5 тепер охоплює всю відповідь. Усі десять
знайдених ризиків закрито.

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

### Тести надійності як обов'язкова перевірка PR

| Доказ | Реалізація / перевірка |
|---|---|
| Окремий крок у CI | [ci.yml](../../.github/workflows/ci.yml), job `reliability-tests` з назвою **Reliability tests**, окремий від загального `build` |
| Що запускається | `python -m pytest tests/reliability --no-cov -v` (R1–R4, R9, R10, health check), далі `npx vitest run tests/reliability.test.tsx` (R5–R8) |
| Коли запускається | На кожен `pull_request` у `main` і `push` у `main`, без фільтра `paths`: обов'язкова перевірка, яку пропустив фільтр, лишилася б у стані «Expected — waiting» і блокувала б PR |
| Підсумок прогону | Крок «Add reliability summary» пише в Job Summary кількість тестів, падінь і помилок із JUnit-звіту |
| Обов'язковість | Settings → Branches → правило для `main` → **Require status checks to pass before merging** → `Reliability tests` |
| Прогін, де крок пройшов | TODO: посилання на прогін Actions |

**Чому `--no-cov`:** у `pyproject.toml` `addopts` вмикає поріг покриття 70 %.
Він має сенс для повного набору в job `build`, а не для підмножини
reliability-тестів, яка сама по собі покриває менше коду.

**Що це дає:** PR, який ламає будь-яку реакцію на збій (тайм-аут, 503 при
падінні БД, блокування входу, файловий збій під час старту), не можна
змерджити в `main`, навіть якщо загальне покриття лишається вище порогу.

Локальна перевірка команд job перед комітом (08.11.2026):

```text
$ python -m pytest tests/reliability --no-cov -q
37 passed

$ cd src/frontend && npx vitest run tests/reliability.test.tsx
 Test Files  1 passed (1)
      Tests  6 passed (6)
```
