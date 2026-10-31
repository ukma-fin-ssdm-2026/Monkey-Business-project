## [0.1.3] - 2026-10-31

### Refactoring:

- Закріплено GitHub Action `peaceiris/actions-gh-pages` на повному SHA
  `84c30a85c19949d7eee79c4ff27748b70285e453`.
  **Техніка:** Pin Dependency Version.

## [0.1.2] - 2026-10-31

### Refactoring:

- Видалено непотрібний параметр `scope="function"` із залежності
  репозиторіїв у `src/api/db.py`.
  **Техніка:** Simplify Method Call.

## [0.1.1] - 2026-10-31

### Refactoring:

- Прибрано fallback-пароль PostgreSQL із Docker Compose та залишено
  обов'язкову змінну середовища `POSTGRES_PASSWORD`.
  **Техніка:** Externalize Configuration.
- Додано регресійні перевірки, що секрет не зберігається в Compose або CI.
  **Техніка:** Characterization Test.