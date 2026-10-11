# Tech Interview Board — Frontend

React + TypeScript (Vite) клієнт для API з `src/api/*.py`

## Запуск

```bash
cd src/frontend
npm install
npm run dev
```

Відкрити http://localhost:5173. Бекенд (з docker compose) має працювати на
http://localhost:3000.

## Важливе обмеження API, з яким працює фронтенд

API поки не має ендпоінта "мої дошки" (`src/api/README.md`: *"Окремого
ендпоінта для отримання board_id поки немає"*). Тому після входу фронтенд
просить ввести `board_id` вручну (сторінка `/board/setup`) і зберігає його
лише в `localStorage` браузера, окремо для кожного користувача. Кандидат
може знайти свій `board_id` командою з README бекенду:

```bash
docker compose exec db psql -U interview_board -d interview_board \
  -c "select b.id from boards b join users u on u.id = b.owner_id where u.email = 'you@example.com'"
```

Це єдине місце, де фронтенд "доповнює" відсутню функціональність — і робить
це повністю на своєму боці, без жодної зміни API.

## Що реалізовано

- Реєстрація/вхід (JWT Bearer, токен у `localStorage`).
- Канбан-дошка: етапи-колонки, drag-and-drop карток між етапами та в межах
  етапу (`@hello-pangea/dnd`), переміщення викликає `POST .../cards/{id}/move`.
- Створення/перейменування/видалення етапів (409, якщо в етапі є картки —
  показується повідомленням, без обходу перевірки бекенду).
- Створення, редагування (назва компанії/посади, URL вакансії, вимоги,
  дедлайн, нагадування, статус) і видалення карток.
- Посилання на тестові завдання та нотатки/фідбек до картки (додавання,
  видалення).
- Розмежування прав на UI: роль `mentor` бачить дошку в режимі лише
  перегляду (без drag-and-drop, форм додавання/редагування) — так само, як
  це обмежує сам API (`require_board_access`, `CandidateOrAdmin`).
- Єдиний показ помилок API (`ErrorResponse.error.message`) для кожної дії.

## Структура

```
src/
  api/        — типи (1:1 зі schemas.py) і fetch-клієнт з обробкою ErrorResponse
  context/    — AuthContext (токен, користувач, обраний board_id)
  components/ — StageColumn, CardItem, CardModal, NewCardForm, ProtectedRoute
  pages/      — LoginPage, RegisterPage, BoardSetupPage, BoardPage
```
