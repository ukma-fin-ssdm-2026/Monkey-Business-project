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

## Продакшн-білд (Azure Static Web Apps)

```bash
VITE_API_BASE_URL=https://<адреса-API> npm run build
```

`public/staticwebapp.config.json` потрапляє в `dist/` і переписує невідомі
маршрути (`/board/...`, `/invitations/...`) на `index.html`, щоб оновлення
сторінки не давало 404 у `BrowserRouter`. API на іншому origin має дозволяти
CORS для адреси фронтенду.

## Вибір дошки

Після входу чи реєстрації сторінка `/board/setup` бере список дошок з
`GET /v1/boards`. Якщо дошка одна (типовий кандидат одразу після реєстрації),
вона відкривається автоматично; інакше користувач обирає її зі списку.
Обраний `board_id` зберігається в `localStorage`, окремо для кожного
користувача. Ручний ввід `board_id` лишився для адміністратора, якому
список чужих дошок не повертається.

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
